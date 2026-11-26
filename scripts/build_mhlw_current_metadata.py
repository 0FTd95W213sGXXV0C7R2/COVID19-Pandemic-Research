#!/usr/bin/env python3
"""Review held weekly definitions and build the active, fail-closed crosswalk."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

from audit_mhlw_early_pdfs import AUDIT, JST, ROOT, compact, csv_rows, fetch

REVIEW = AUDIT / "definition_review"
OUT = AUDIT / "early_pdf_audit"
META = ROOT / "data/metadata/rebuild_2026/scarce_resource/mhlw_resource_quality"
ARCHIVE = "https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html"
ACTIVE = META / "active_crosswalk.json"
HISTORICAL = META / "variable_crosswalk.csv"

# The scopes below distinguish a heading or contextual mention from a definition.
QUESTIONS = {
    "secured_bed_occupancy_rate": ("使用率|重症|確保病床", "分母は確保病床。入院確定者を含む入院者数を分子とする明示、および重症の同一基準・対象病床を確認する"),
    "secured_room_occupancy_rate": ("居室|宿泊", "分母は確保居室。待機者や施設種別を含む分子が明示されているか確認する"),
    "total_inpatients": ("入院者数|在院者数|入院確定", "見出しや療養者合計の構成要素だけでは、実入院・入院確定者、臨時施設、院外の算入範囲を特定できない"),
    "home_care_patients": ("自宅療養|新規陽性", "自宅療養等の集計境界、推計の開始週、直接集計との使い分けを確認する"),
    "total_severe_patients": ("重症|国基準|東京都", "国の集計基準と自治体別基準の適用先を確認し、分母の病床カテゴリに対応づける"),
    "total_moderate_II_patients": ("中等症|重症", "中等症Ⅱの判定基準と自治体別例外を確認する"),
    "secured_capacity_occupancy_rate": ("確保定員|臨時の医療施設", "注14の療養者数が、注10の広い施設内訳か、注11・13の病床・居室のいずれにも属さない施設に限るかを確認する"),
    "hotel_accommodation_patients": ("宿泊療養|居室", "宿泊施設での入院待機・臨時施設を含める境界を確認する"),
    "social_welfare_facility_patients": ("社会福祉施設|自宅療養", "社会福祉施設等の範囲および他の療養区分との重複を確認する"),
}


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def by_key(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_active_crosswalk():
    """Analysis entry point. Missing or mismatched review inputs invalidate the release."""
    registry = json.loads(ACTIVE.read_text(encoding="utf-8"))
    for item, digest in registry["sha256"].items():
        if sha(ROOT / item) != digest:
            raise ValueError(f"Active MHLW release is stale: {item}")
    rows = csv_rows(ROOT / registry["crosswalk"])
    return by_key(rows, "variable_id")


def analysis_allowed(row, value_status):
    return row["analysis_gate"] in {"descriptive", "available_prefectures"} and value_status in {"numeric", "reported_zero"}


def same_analysis_definition(left, right):
    """Gate comparisons without treating differing definition periods as one series."""
    return (analysis_allowed(left, "numeric") and analysis_allowed(right, "numeric")
            and bool(left["definition_id"]) and left["definition_id"] == right["definition_id"])


def pdf_pairs():
    """Pair an official PDF link with the Excel link in the same archive entry."""
    with urlopen(ARCHIVE, timeout=20) as response:
        html = response.read().decode("utf-8")
    found = {}
    last_pdf = ""
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        url = urljoin(ARCHIVE, href)
        if not url.startswith("https://www.mhlw.go.jp/content/"):
            continue
        if url.lower().endswith(".pdf"):
            last_pdf = url
        elif url.lower().endswith(".xlsx") and last_pdf:
            found[url] = last_pdf
            last_pdf = ""
    return found


def get_pdf_text(url, private):
    result = fetch({"url": url, "observation_date": "", "archive_label": ""}, private)
    plain = ""
    if result["status"] == "downloaded":
        try:
            path = private / url.rsplit("/", 1)[-1]
            plain = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True).stdout.decode()
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            result.update(status="text_failed", error=str(exc))
    return result, plain


def header_date_matches(text, expected):
    day = datetime.fromisoformat(expected)
    header = compact("\n".join(text.splitlines()[:6]))
    return re.search(rf"(?<!\d)0?{day.month}月0?{day.day}日0時", header) is not None


def review_held(evidence, headers, private):
    held = [row for row in evidence.values() if row["definition_status"] == "hold"]
    archive_error = ""
    try:
        links = pdf_pairs()
    except (OSError, ValueError) as exc:
        links, archive_error = {}, str(exc)
    urls = sorted({links.get(row["source_url"], row["comparison_pdf_url"]) for row in held})
    with ThreadPoolExecutor(max_workers=8) as pool:
        retrieved = dict(zip(urls, pool.map(lambda url: get_pdf_text(url, private), urls)))
    fields = ("url", "final_url", "retrieved_at_jst", "http_status", "mime", "format", "bytes", "sha256", "status", "error")
    write_csv(OUT / "definition_pdf_manifest.csv", [{key: result[key] for key in fields} for result, _ in retrieved.values()])
    notes = {}
    for entry in csv_rows(AUDIT / "footnotes.csv"):
        if entry["kind"] == "cell_text" and re.match(r"注\d+:", compact(entry["text"])):
            notes.setdefault((entry["source_path"], entry["sheet"]), []).append(entry)
    output = []
    for row in held:
        key = row["variable_id"]
        header = headers[key]
        pattern, requirement = QUESTIONS[row["concept"]]
        sources = [entry for entry in notes.get((header["source_path"], row["sheet"]), [])
                   if re.search(pattern, compact(entry["text"])) and not re.search(r"修正|訂正", entry["text"])]
        url = links.get(row["source_url"], row["comparison_pdf_url"])
        result, text = retrieved[url]
        same_week = result["status"] == "downloaded" and header_date_matches(text, row["observation_date"])
        matched = [entry for entry in sources if compact(entry["text"]) in compact(text)] if text else []
        output.append(dict(variable_id=key, concept=row["concept"], era=row["era"], observation_date=row["observation_date"],
            excel_url=row["source_url"], sheet=row["sheet"], header_cells=row["header_cells"],
            relevant_excel_note_cells="|".join(entry["cell"] for entry in sources),
            relevant_excel_note_numbers="|".join(re.match(r"注(\d+):", compact(entry["text"]))[1] for entry in sources),
            pdf_url=url, pdf_status=result["status"], pdf_scope="same_week" if same_week else "representative_or_unverified",
            matched_full_note_cells="|".join(entry["cell"] for entry in matched), archive_error=archive_error,
            required_confirmation=requirement, outcome="hold"))
    write_csv(OUT / "held_definition_followup.csv", output)
    return output, retrieved


def build():
    old = by_key(csv_rows(HISTORICAL), "variable_id")
    evidence = by_key(csv_rows(REVIEW / "definition_evidence.csv"), "variable_id")
    decisions = by_key(csv_rows(REVIEW / "adoption_decisions.csv"), "definition_id")
    held = by_key(csv_rows(OUT / "held_definition_followup.csv"), "variable_id")
    expected_held = {key for key, row in evidence.items() if row["definition_status"] == "hold"}
    if expected_held != held.keys() or any(row["outcome"] != "hold" for row in held.values()):
        raise ValueError("Hold review does not cover the current review")
    if {key for key, row in old.items() if row["source_system"] == "weekly"} != evidence.keys():
        raise ValueError("Weekly evidence must cover exactly the historical weekly variables")
    merged = []
    for key, prior in old.items():
        current = evidence.get(key)
        row = dict(prior)
        row.update(definition_id="", definition_status="unreviewed_gmis", adoption_status="別系統・保留",
                   analysis_gate="hold", definition_reason="週次調査の採用判定の対象外", source_url="",
                   sheet="", header_cells="", note_cells="", note_numbers="", context_pdf_url="",
                   usable_period_policy="同一definition_idと適用期間内のみ")
        if current:
            decision = decisions[current["definition_id"]]
            for field in ("concept", "severity", "definition", "numerator", "denominator", "definition_id",
                          "definition_status", "source_url", "sheet", "header_cells", "note_cells", "note_numbers"):
                row[field] = current[field]
            gate = {"採用可・期間内の記述分析": "descriptive", "条件付き・数値ありの都道府県のみ": "available_prefectures"}
            row.update(status="保留" if key in held else current["definition_status"],
                       adoption_status="保留" if key in held else decision["status"],
                       analysis_gate="hold" if key in held else gate.get(decision["status"], "hold"),
                       definition_reason=held[key]["required_confirmation"] if key in held else current["reason"],
                       context_pdf_url=held[key]["pdf_url"] if key in held else current["comparison_pdf_url"],
                       evidence="|".join(filter(None, [current["header_cells"], current["note_cells"]])))
            if key in held:
                row.update(definition="不明", numerator="不明" if current["numerator"] != "対象外" else "対象外",
                           denominator="不明" if current["denominator"] != "対象外" else "対象外")
        merged.append(row)
    path = META / "variable_crosswalk_candidate_v2.csv"
    write_csv(path, merged)
    dependencies = [path, HISTORICAL, REVIEW / "definition_evidence.csv", REVIEW / "adoption_decisions.csv", OUT / "held_definition_followup.csv"]
    release = {"release": "weekly_candidate_v2", "crosswalk": str(path.relative_to(ROOT)),
               "status_precedence": ["held_definition_followup", "definition_evidence", "adoption_decisions", "historical_metadata"],
               "sha256": {str(dependency.relative_to(ROOT)): sha(dependency) for dependency in dependencies}}
    ACTIVE.write_text(json.dumps(release, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return old, evidence, load_active_crosswalk()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--integrate-only", action="store_true", help="Reuse the saved hold review without Internet access")
    args = parser.parse_args()
    started = datetime.now(JST).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.integrate_only:
        if not args.private_dir or args.private_dir.resolve().is_relative_to(ROOT):
            parser.error("--private-dir outside the repository is required")
        private = args.private_dir.resolve()
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        review_held(by_key(csv_rows(REVIEW / "definition_evidence.csv"), "variable_id"),
                    by_key(csv_rows(META / "column_headers.csv"), "variable_id"), private)
    old, evidence, active = build()
    held = csv_rows(OUT / "held_definition_followup.csv")
    manifest = csv_rows(OUT / "definition_pdf_manifest.csv")
    tests = {
        "same_variable_identity": active.keys() == old.keys(),
        "all_778_held_remain_unusable": len(held) == 778 and all(not analysis_allowed(active[row["variable_id"]], "numeric") for row in held),
        "old_known_conflicts_overridden": sum(old[row["variable_id"]]["definition"] != "不明" for row in held) == 72
            and all(active[row["variable_id"]]["definition"] == "不明" for row in held),
        "reviewed_severity_takes_priority": active["2023-05-10:1:K"]["severity"] == "severe",
        "required_sources_present": all(row["excel_url"] and row["pdf_url"] and row["required_confirmation"] for row in held),
        "no_automatic_gmis_join": all(row["analysis_gate"] == "hold" for row in active.values() if row["source_system"] == "gmis"),
        "dash_and_blank_blocked": all(not analysis_allowed(row, "dash") and not analysis_allowed(row, "blank") for row in active.values()),
        "version_pointer_and_hashes_validated": len(load_active_crosswalk()) == len(active),
        "different_eras_cannot_be_joined": not same_analysis_definition(active["2021-06-02:1:F"], active["2021-12-22:1:D"]),
        "same_governed_definition_can_be_compared": same_analysis_definition(active["2021-06-02:1:F"], active["2021-06-09:1:F"]),
        "allow_numeric_for_supported_variable": analysis_allowed(active["2021-06-02:1:F"], "numeric"),
    }
    report = dict(started_at_jst=started, finished_at_jst=datetime.now(JST).isoformat(timespec="seconds"),
        rows=len(active), weekly=len(evidence), held=len(held),
        pdf_files=len(manifest), pdf_downloaded=sum(row["status"]=="downloaded" for row in manifest),
        same_week_occurrences=sum(row["pdf_scope"]=="same_week" for row in held),
        matching_context_note_occurrences=sum(bool(row["matched_full_note_cells"]) for row in held),
        tests=tests)
    (OUT / "integration_validation.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return all(tests.values())


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

#!/usr/bin/env python3
"""Independent XLSX/XML verification and source-based definition review."""
import argparse
import csv
import hashlib
import json
import posixpath
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/audits/mhlw/resource_quality_20261126"
OUT = AUDIT / "definition_review"
BASE = ROOT / "data/processed/rebuild_2026/scarce_resource"
META = ROOT / "data/metadata/rebuild_2026/scarce_resource/mhlw_resource_quality"
ARCHIVE = "https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html"
JST = ZoneInfo("Asia/Tokyo")
PDF_SUPPORT = {
    "early": ("2021-01-13", "https://www.mhlw.go.jp/content/10900000/000721102.pdf", "MHLW_FOOTNOTE_EARLY_20210113_20261126.md"),
    "2021": ("2021-06-23", "https://www.mhlw.go.jp/content/10900000/000872286.pdf", "MHLW_FOOTNOTE_2021_2022_COMPARISON_20261126.md"),
    "2022": ("2022-12-21", "https://www.mhlw.go.jp/content/10900000/001029801.pdf", "MHLW_FOOTNOTE_2021_2022_COMPARISON_20261126.md"),
    "may": ("2023-05-10", "https://www.mhlw.go.jp/content/001143141.pdf", "MHLW_FOOTNOTE_PRIMARY_COMPARISON_20261126.md"),
    "oct": ("2024-03-27", "https://www.mhlw.go.jp/content/001238243.pdf", "MHLW_FOOTNOTE_PRIMARY_COMPARISON_20261126.md"),
}
DASHES = {"－", "ー", "-", "―", "–", "—", "−", "‐"}
NOTE = re.compile(r"^注(\d+):")
REVISION = re.compile(r"\(?\d{1,2}月\d{1,2}日(?:付け?)?(?:修正)?\)?|^注\d+:")
DETAIL = re.compile(r"について|訂正|差替|差し替|誤り|県|都の|道の|府の")


def read(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save(name, fields, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields.split(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or ""))


def group(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def slot(when):
    for boundary, era in (("2023-10-04", "oct"), ("2023-05-10", "may"),
                          ("2021-12-22", "2022"), ("2021-06-02", "2021")):
        if when >= boundary:
            return era
    return "early"


def xml_sheets(path):
    """Read cached values directly from OPC parts, including shared/inline strings."""
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        paths = {item.get("Id"): item.get("Target") for item in relationships}
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")):
                strings.append("".join(t.text or "" for t in item.findall("{*}t") + item.findall("{*}r/{*}t")))
        for sheet in workbook.findall("{*}sheets/{*}sheet"):
            identity = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
            target = paths[identity]
            part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            tree = ET.fromstring(archive.read(part))
            cells = {}
            for cell in tree.findall("{*}sheetData/{*}row/{*}c"):
                kind = cell.get("t", "n")
                value = cell.findtext("{*}v") or ""
                if kind == "s":
                    value = strings[int(value)]
                if kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall("{*}is/{*}t") + cell.findall("{*}is/{*}r/{*}t"))
                cells[cell.get("r")] = (kind, value, cell.find("{*}f") is not None)
            yield sheet.get("name"), cells


def verify_value(row, source):
    kind, raw, formula = source
    exported = row["raw_value"]
    numeric = row["numeric_value"]
    if kind == "n" and raw:
        try:
            value = Decimal(raw)
            # The prior reader exports Python binary float renderings for decimals.
            same = bool(numeric) and (Decimal(numeric) == value or float(numeric) == float(value))
            return same and exported == numeric and row["value_status"] == ("reported_zero" if value == 0 else "numeric")
        except (ValueError, InvalidOperation):
            return False
    if kind == "b":
        raw = "True" if raw == "1" else "False"
    expected = ("excel_error" if kind == "e" else "formula_cache_missing" if formula and not raw
                else "blank" if not raw.strip() else "dash" if raw.strip() in DASHES
                else "annotated_value" if re.match(r"注\d+", norm(raw)) else "text")
    return raw == exported and not numeric and expected == row["value_status"]


def verify_sources(headers, manifest, panel, notes):
    exported = group(panel, lambda row: headers[row["variable_id"]]["source_path"])
    note_groups = group(notes, lambda row: row["source_path"])
    differences = []
    checked_values = checked_notes = checked_dates = 0
    for path, rows in sorted(exported.items()):
        sheets = dict(xml_sheets(ROOT / path))
        title_sheet, title_cell = manifest[path]["date_evidence"].rsplit("!", 1)
        source_title = norm(sheets[title_sheet].get(title_cell, ("", "", False))[1])
        source_date = re.search(r"(\d{1,2})月(\d{1,2})日0時", source_title)
        expected_day = date.fromisoformat(manifest[path]["observation_date"])
        if not source_date or (int(source_date[1]), int(source_date[2])) != (expected_day.month, expected_day.day):
            differences.append(dict(path=path, sheet=title_sheet, cell=title_cell, check="date"))
        checked_dates += 1
        recorded_notes = {(note["sheet"], note["cell"]) for note in note_groups[path] if note["kind"] == "cell_text"}
        for name, cells in sheets.items():
            for coordinate, (_, raw, _) in cells.items():
                if NOTE.match(norm(raw)) and (name, coordinate) not in recorded_notes:
                    differences.append(dict(path=path, sheet=name, cell=coordinate, check="unlisted_numbered_note"))
        for row in rows:
            head = headers[row["variable_id"]]
            cells = sheets[head["sheet"]]
            coordinate = row["cell"]
            match = re.fullmatch(r"([A-Z]+)(\d+)", coordinate)
            lon = int(head["column"])
            alphabet = 0
            for character in match[1]:
                alphabet = alphabet * 26 + ord(character) - 64
            expected_region = norm(row["prefecture_code"] + row["prefecture"])
            region_found = expected_region in {norm(cells.get(f"{col}{match[2]}", ("", "", False))[1]) for col in "ABCD"}
            if not (alphabet == lon and region_found and row["observation_date"] == manifest[path]["observation_date"]
                    and verify_value(row, cells.get(coordinate, ("n", "", False)))):
                differences.append(dict(path=path, sheet=head["sheet"], cell=coordinate, check="series"))
            checked_values += 1
        for note in note_groups[path]:
            if note["kind"] != "cell_text":
                continue
            checked_notes += 1
            raw = sheets[note["sheet"]].get(note["cell"], ("", "", False))[1]
            if raw != note["text"]:
                differences.append(dict(path=path, sheet=note["sheet"], cell=note["cell"], check="note"))
    return checked_values, checked_notes, checked_dates, differences


def evidence_rules(era, column, heading):
    """Require both a field-specific heading and a contemporaneous corroborating note."""
    old_care = {
        "O": ("宿泊療養者数", "宿泊療養及び宿泊施設での入院待機者", "宿泊療養者と宿泊施設での入院待機者の数"),
        "T": ("自宅療養者数", "自宅療養及び自宅での入院待機者", "自宅療養者と自宅での入院待機者の数"),
        "U": ("社会福祉施設等療養者数", "社会福祉施設等療養及び社会福祉施設等での入院待機者", "社会福祉施設等療養者と同施設等での入院待機者の数"),
        "V": ("確認中の人数", "確認中の患者の合計", "PCR陽性者の療養状況が確認中の患者数"),
    }
    if era == "early" and column in old_care:
        label, token, meaning = old_care[column]
        if label in heading:
            return [(1, "死亡者を除いた者"), (2, token)], meaning
    secured = {
        "2021": {"F": ("(2)①-2", False), "M": ("(2)②-2", True)},
        "2022": {"D": ("(2)①-2", False), "M": ("(2)②-2", True)},
        "may": {"C": ("(1)①-2", False), "J": ("(1)②-2", True)},
        "oct": {"C": ("(1)①-2", False), "J": ("(1)②-2", False), "P": ("(1)③-2", True)},
    }
    if column in secured.get(era, {}) and "確保病床に入院している" in heading:
        token, severe = secured[era][column]
        qualifier = "重症" if severe else "中等症II" if era == "oct" and column == "J" else ""
        return [(5 if era in ("2021", "2022") else 4, "当該病床に入院している者"),
                (5 if era in ("2021", "2022") else 4, token)], f"調査票上の{qualifier}区分の確保病床内入院者数" if qualifier else "調査票の①区分における確保病床内入院者数"
    if era == "2022" and "に位置付けられた臨時の医療施設" in heading:
        meanings = {
            "E": ("入院している者数", "確保病床に位置付けられた臨時施設・入院待機施設の入院者数"),
            "I": ("の病床数", "確保病床に位置付けられた臨時施設・入院待機施設の病床数"),
            "N": ("入院している重症者数", "確保病床に位置付けられた臨時施設・入院待機施設の重症入院者数"),
            "R": ("の病床数", "確保病床に位置付けられた臨時施設・入院待機施設の重症者用病床数"),
            "U": ("宿泊している者数", "確保居室に位置付けられた臨時施設・入院待機施設の宿泊者数"),
            "Y": ("の居室数", "確保居室に位置付けられた臨時施設・入院待機施設の居室数"),
        }
        if column in meanings and meanings[column][0] in heading:
            return [(1, "確保居室に位置付けられた臨時の医療施設"), (10, "臨時の医療施設")], meanings[column][1]
    if era in ("may", "oct") and "確保病床外に入院している" in heading:
        groups = {"may": {"D": "", "K": "重症"}, "oct": {"D": "", "K": "中等症II", "Q": "重症"}}
        if column in groups[era]:
            qualifier = groups[era][column]
            marker = {"D": "(1)①-2", "K": "(1)②-2", "Q": "(1)③-2"}[column]
            return [(4, marker)], f"調査票の{qualifier or '①'}区分における確保病床外入院者数"
    return [], ""


def review_definitions(previous, headers, manifest, footnotes, source_errors):
    catalog = group(footnotes, lambda row: (row["source_path"], row["sheet"]))
    result = []
    for row in previous:
        key = row["variable_id"]
        head = headers[key]
        when, _, col = key.split(":")
        day = head["observation_date"]
        era = slot(day)
        path, sheet = head["source_path"], head["sheet"]
        sheet_notes = catalog[path, sheet]
        note_numbers = {}
        for note in sheet_notes:
            match = NOTE.match(norm(note["text"]))
            if match:
                note_numbers[match[1]] = note
        heading = norm(head["header_path"])
        requirements, meaning = evidence_rules(era, col, heading)
        evidence = []
        before = row["definition"] != "不明"
        status = "hold"
        reason = "対象・計数方法または分子分母の原資料根拠が不足"
        if before:
            cells = row["evidence"].split("|")
            evidence = [note for note in sheet_notes if note["cell"] in cells and NOTE.match(norm(note["text"]))]
            if evidence and all(norm(note["text"]) in norm(row["definition"]) for note in evidence):
                status = "confirmed_prior"
            elif "入院確定者数を含む" in heading and "入院確定者数を含む" in norm(row["definition"]):
                status = "confirmed_prior"
            reason = "既存定義の根拠を同週の原注記または明示見出しと照合"
        elif requirements and all(str(n) in note_numbers and norm(token) in norm(note_numbers[str(n)]["text"])
                                  for n, token in requirements):
            evidence = [note_numbers[str(n)] for n in sorted({n for n, _ in requirements})]
            status = "confirmed_new"
            reason = "見出しと同週注記から調査票上の集計対象を確認"
        concept, severity = row["concept"], row["severity"]
        if era == "may" and col == "K" and status == "confirmed_new":
            severity = "severe"
            reason += "。同区分の列順と2023-05-10 PDFの②-3で重症区分を確認"
        if era == "2022" and col == "U":
            concept = "temporary_facility_accommodation_patients"
        if era == "2022" and col == "R" and "重症者用" in heading:
            severity = "severe"
        if any(error["path"] == path and error["check"] == "note" for error in source_errors):
            status, reason = "hold", "原注記と既存抽出に差異あり"
        if concept == "unclassified" or not head["header_cells"]:
            status, reason = "hold", "列の用途を特定できる見出しが不足"
        if concept.endswith("_rate") and (row["numerator"] == "不明" or row["denominator"] == "不明"):
            status, reason = "hold", "同じ集計対象の分子・分母の列を特定できていない"
        # Remove typography and ordinal changes only. Keep layout eras separate.
        substantive_heading = re.sub(r"^\(\d+\)\d(?:[-ーｰ]\d+)?", "", heading.rsplit("/", 1)[-1])
        classification = (era, concept, severity, substantive_heading)
        if before:
            classification += (norm(row["definition"]).rstrip("。"),)
        definition_id = hashlib.sha256(json.dumps(classification, ensure_ascii=False).encode()).hexdigest()[:16]
        pdf_date, pdf, pdf_audit = PDF_SUPPORT[era]
        result.append(dict(variable_id=key, definition_id=definition_id, era=era, definition_status=status,
                           prior_definition_known=before, concept=concept, severity=severity, observation_date=day,
                           source_url=manifest[path]["source_url"], sheet=sheet, column=col,
                           header=head["header_path"].strip(), header_cells=head["header_cells"],
                           note_cells="|".join(item["cell"] for item in evidence),
                           note_numbers="|".join(NOTE.match(norm(item["text"]))[1] for item in evidence),
                           note_text=" | ".join(item["text"].strip() for item in evidence),
                           definition=(row["definition"].strip() if before else meaning) if status != "hold" else "不明",
                           numerator=row["numerator"], denominator=row["denominator"],
                           reason=reason, comparison_pdf_date=pdf_date, comparison_pdf_url=pdf,
                           comparison_audit="docs/audits/rebuild_2026/" + pdf_audit))
    save("definition_evidence.csv", "variable_id definition_id era definition_status prior_definition_known concept severity "
         "observation_date source_url sheet column header header_cells note_cells note_numbers note_text definition numerator "
         "denominator reason comparison_pdf_date comparison_pdf_url comparison_audit", result)
    return result


def continuous(days):
    periods = []
    prior = None
    for day in sorted(set(days)):
        current = date.fromisoformat(day)
        if prior is None or current - prior != timedelta(days=7):
            periods.append([day, day, 1])
        else:
            periods[-1][1] = day
            periods[-1][2] += 1
        prior = current
    return periods


def availability(review, panel_by_variable):
    classes = group(review, lambda row: row["definition_id"])
    metrics, periods, decisions, previous_groups = [], [], [], []
    for key, rows in sorted(classes.items()):
        totals = Counter()
        complete = []
        dates = {row["observation_date"] for row in rows}
        usable = 0
        for row in rows:
            values = panel_by_variable[row["variable_id"]]
            counts = Counter(value["value_status"] for value in values)
            numbers = counts["numeric"] + counts["reported_zero"]
            confirmed = row["definition_status"] != "hold"
            totals.update(counts)
            if confirmed:
                usable += numbers
                if numbers == 47:
                    complete.append(row["observation_date"])
            metrics.append(dict(definition_id=key, variable_id=row["variable_id"], observation_date=row["observation_date"],
                                expected=47, numeric=numbers, reported_zeros=counts["reported_zero"], dash=counts["dash"],
                                blank=counts["blank"] + counts["formula_cache_missing"], other=47-numbers-counts["dash"]-counts["blank"]-counts["formula_cache_missing"],
                                numeric_rate=numbers/47, missing_rate=(counts["dash"]+counts["blank"]+counts["formula_cache_missing"])/47,
                                definition_confirmed=int(confirmed)))
        confirmed = sum(row["definition_status"] != "hold" for row in rows)
        count = len(rows)*47
        numbers = totals["numeric"] + totals["reported_zero"]
        complete_periods = continuous(complete)
        population = rows[0]
        for start, finish, weeks in complete_periods:
            periods.append(dict(definition_id=key, start=start, end=finish, weeks=weeks))
        status = "保留"
        reason = "同一期間の根拠と数値がそろう列がない"
        if usable:
            status = "採用可・期間内の記述分析" if complete else "条件付き・数値ありの都道府県のみ"
            reason = "確定済み行の原公表値を使用。地域基準・報告ゼロ・注記の条件を確認"
        if population["concept"] == "stage":
            status, reason = "保留", "段階はカテゴリ。数値系列の判定対象外"
        if population["concept"] in {"total_severe_patients", "total_moderate_II_patients"}:
            status, reason = "保留", "重症度の地域別判定基準を要確認"
        decisions.append(dict(definition_id=key, concept=population["concept"], severity=population["severity"],
            era=population["era"], header=population["header"], first=min(dates), last=max(dates),
            listed_weeks=len(dates), absent_weeks=171-len(dates), occurrences=len(rows), confirmed_occurrences=confirmed,
            definition_rate=confirmed/len(rows), numeric_rate=numbers/count,
            missing_rate=(totals["dash"]+totals["blank"]+totals["formula_cache_missing"])/count,
            complete_weeks=len(set(complete)), longest_complete=max((period[2] for period in complete_periods), default=0),
            status=status, reason=reason))
        formerly_unknown = [row for row in rows if not row["prior_definition_known"]]
        if formerly_unknown:
            previous_groups.append(dict(definition_id=key, era=population["era"], concept=population["concept"],
                severity=population["severity"], columns="|".join(sorted({row["column"] for row in formerly_unknown})),
                first=min(row["observation_date"] for row in formerly_unknown), last=max(row["observation_date"] for row in formerly_unknown),
                unresolved_before=len(formerly_unknown),
                confirmed_after=sum(row["definition_status"] == "confirmed_new" for row in formerly_unknown),
                definition=next((row["definition"] for row in formerly_unknown if row["definition_status"] == "confirmed_new"), "不明")))
    save("weekly_availability.csv", "definition_id variable_id observation_date expected numeric reported_zeros dash blank other "
         "numeric_rate missing_rate definition_confirmed", metrics)
    save("continuous_periods.csv", "definition_id start end weeks", periods)
    save("adoption_decisions.csv", "definition_id concept severity era header first last listed_weeks absent_weeks occurrences "
         "confirmed_occurrences definition_rate numeric_rate missing_rate complete_weeks longest_complete status reason", decisions)
    save("formerly_unknown_types.csv", "definition_id era concept severity columns first last unresolved_before confirmed_after definition", previous_groups)
    return decisions, previous_groups


def national_review(panel_by_variable):
    output = []
    for row in read(AUDIT / "national_totals.csv"):
        if row["result"] == "match":
            continue
        counts = Counter(x["value_status"] for x in panel_by_variable[row["variable_id"]])
        confirmed_numeric = counts["numeric"] + counts["reported_zero"]
        reasons = []
        if counts["blank"] or counts["formula_cache_missing"]:
            reasons.append("missing")
        if counts["dash"]:
            reasons.append("dash")
        if row["result"] == "national_zero_incomplete":
            reasons.append("reported_national_zero_with_incomplete_prefectures")
        other = 47-confirmed_numeric-counts["blank"]-counts["formula_cache_missing"]-counts["dash"]
        if other:
            reasons.append("other_prefecture_value")
        if confirmed_numeric == 47:
            reasons.append("national_value_unavailable")
        output.append(dict(**row, dash_count=counts["dash"], missing_count=counts["blank"]+counts["formula_cache_missing"],
            reported_prefecture_zeros=counts["reported_zero"], other_count=other, reasons="|".join(reasons)))
    save("national_incomplete_review.csv", "source_path sheet cell variable_id national numeric_prefectures prefecture_sum result "
         "dash_count missing_count reported_prefecture_zeros other_count reasons", output)
    return output


def revision_review():
    revisions = read(AUDIT / "revisions.csv")
    output = []
    event_count = Counter()
    for (path, day), rows in sorted(group(revisions, lambda x: (x["source_path"], x["revision_date"])).items()):
        details = {}
        mentions = []
        note_events = {}
        for row in rows:
            content = norm(row["text"])
            cleaned = REVISION.sub("", content).strip("。・()")
            if DETAIL.search(cleaned) and not ("公表" in cleaned and "について" not in cleaned):
                event_id = hashlib.sha256(f"{path}|{day}|{cleaned}".encode()).hexdigest()[:16]
                duplicate = cleaned in details
                details[cleaned] = event_id
                if NOTE.match(content):
                    note_events[NOTE.match(content)[1]] = event_id
                output.append(dict(**row, event_ids=event_id, classification="duplicate_detail" if duplicate else "distinct_detail"))
                if not duplicate:
                    event_count["distinct_detailed_events"] += 1
            else:
                mentions.append(row)
        for index, row in enumerate(mentions):
            event_ids = "|".join(sorted(details.values()))
            dependency = re.search(r"注(\d+)の修正に基づき", norm(row["text"]))
            if dependency and dependency[1] in note_events:
                classification = "dependent_correction"
                event_ids = note_events[dependency[1]]
            elif len(details) == 1:
                classification = "duplicate_date_only"
            elif details:
                classification = "date_only_multiple_candidates"
            else:
                classification = "date_only_event" if index == 0 else "duplicate_date_only"
                event_ids = hashlib.sha256(f"{path}|{day}".encode()).hexdigest()[:16]
                if index == 0:
                    event_count["date_only_events"] += 1
            output.append(dict(**row, event_ids=event_ids, classification=classification))
    save("revision_event_review.csv", "source_path sheet cell observation_date publication_date revision_date text event_ids classification",
         [{**row, "text": row["text"].strip()} for row in output])
    return output, event_count


class ArchiveLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.link = None
        self.text = []
        self.rows = []

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.link = dict(attributes).get("href")
            self.text = []

    def handle_data(self, text):
        if self.link:
            self.text.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.link:
            label = "".join(self.text).strip()
            hit = re.search(r"2020年(\d{1,2})月(\d{1,2})日", norm(label))
            if hit and "/content/" in self.link and self.link.lower().endswith(".pdf"):
                day = date(2020, int(hit[1]), int(hit[2])).isoformat()
                if day < "2020-12-23" and "調査結果" in label:
                    self.rows.append((day, urljoin(ARCHIVE, self.link), label))
            self.link = None


def early_pdfs(archive_html):
    path = OUT / "pdf_only_2020_inventory.csv"
    fields = "observation_date url archive_label local_path acquisition_status required_check"
    try:
        if archive_html:
            html = archive_html.read_text(encoding="utf-8")
        else:
            with urlopen(ARCHIVE, timeout=20) as response:
                html = response.read().decode("utf-8")
        links = ArchiveLinks()
        links.feed(html)
        if not links.rows:
            raise ValueError("公式ページに対象アンカーが見つからない")
        source, error = "official_archive", ""
        candidates = sorted(set(links.rows))
    except (OSError, ValueError) as exc:
        source, error = "saved_inventory" if path.exists() else "unverified", str(exc)
        candidates = [(row["observation_date"], row["url"], row["archive_label"]) for row in read(path)] if path.exists() else []
    pdfs = []
    for candidate in ROOT.rglob("*.pdf"):
        with candidate.open("rb") as handle:
            if handle.read(5) == b"%PDF-":
                pdfs.append(candidate)
    inventory = []
    for day, url, label in candidates:
        basename = url.rsplit("/", 1)[-1]
        matches = [item for item in pdfs if item.name.endswith(basename)]
        inventory.append(dict(observation_date=day, url=url, archive_label=label,
            local_path="|".join(str(item.relative_to(ROOT)) for item in matches),
            acquisition_status="stored_pdf" if matches else "acquire",
            required_check="公式PDF本体・基準日時・表構造・脚注・初版と修正版の差分"))
    save(path.name, fields, inventory)
    save("pdf_only_2020_acquisition_queue.csv", fields, [row for row in inventory if row["acquisition_status"] == "acquire"])
    return inventory, source, error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-html", type=Path, help="Use a local copy of the official archive page")
    args = parser.parse_args()
    started = datetime.now(JST)
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {row["variable_id"]: row for row in read(META / "column_headers.csv")}
    manifest = {row["path"]: row for row in read(META / "raw_manifest.csv")}
    notes = [row for row in read(AUDIT / "footnotes.csv") if row["kind"] != "csv_preamble"]
    previous = [row for row in read(META / "variable_crosswalk.csv") if row["source_system"] == "weekly"]
    panel = read(BASE / "mhlw_weekly_prefecture_long.csv")
    by_variable = group(panel, lambda row: row["variable_id"])
    checked, checked_notes, checked_dates, errors = verify_sources(headers, manifest, panel, notes)
    save("independent_differences.csv", "path sheet cell check", errors)
    review = review_definitions(previous, headers, manifest, notes, errors)
    decisions, prior_groups = availability(review, by_variable)
    national = national_review(by_variable)
    revisions, event_counts = revision_review()
    pdfs, archive_source, archive_error = early_pdfs(args.archive_html)
    status_counts = Counter(row["definition_status"] for row in review)
    old_unknown = [row for row in review if not row["prior_definition_known"]]
    tests = {
        "xml_values_independently_match_all_rows": checked == len(panel) == 211124 and not any(x["check"] == "series" for x in errors),
        "each_variable_has_47_unique_prefectures": set(by_variable) == {row["variable_id"] for row in previous}
            and all(len(rows) == len({row["prefecture_code"] for row in rows}) == 47 for rows in by_variable.values()),
        "all_workbook_notes_independently_match": checked_notes == len(notes) == 5124 and not any(x["check"] == "note" for x in errors),
        "source_title_month_days_match": checked_dates == 171 and not any(x["check"] == "date" for x in errors),
        "all_numbered_source_notes_in_catalog": not any(x["check"] == "unlisted_numbered_note" for x in errors),
        "all_171_weeks_reviewed": len({row["observation_date"] for row in review}) == 171,
        "all_1672_originally_missing_definitions_classified": len(old_unknown) == sum(x["unresolved_before"] for x in prior_groups) == 1672,
        "new_confirmations_have_exact_source_evidence": bool(status_counts["confirmed_new"]) and all(
            x["note_cells"] and x["note_numbers"] and x["header_cells"] and x["source_url"] and x["definition"] != "不明"
            for x in review if x["definition_status"] == "confirmed_new"),
        "all_334_incomplete_national_comparisons_explained": len(national) == 334 and all(row["reasons"] for row in national),
        "all_260_revision_mentions_classified": len(revisions) == 260 and all(row["event_ids"] for row in revisions),
        "pdf_archive_inventory_available": bool(pdfs),
        "original_bytes_match_previous_sha256": all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == info["sha256"]
                                                    for path, info in manifest.items()),
    }
    result = dict(start_jst=started.isoformat(timespec="seconds"), end_jst=datetime.now(JST).isoformat(timespec="seconds"),
        xml_values_checked=checked, xml_notes_checked=checked_notes, xml_title_dates_checked=checked_dates, xml_differences=len(errors),
        weekly_columns=len(review), previous_known=len(review)-len(old_unknown), previous_unknown=len(old_unknown),
        formerly_unknown_types=len(prior_groups),
        formerly_unknown_types_with_confirmation=sum(row["confirmed_after"] > 0 for row in prior_groups),
        formerly_unknown_types_still_open=sum(row["unresolved_before"] > row["confirmed_after"] for row in prior_groups),
        formerly_unknown_still_open=sum(x["definition_status"] == "hold" for x in old_unknown),
        definition_status=dict(status_counts), national_reason_combinations=dict(Counter(row["reasons"] for row in national)),
        revision_classifications=dict(Counter(row["classification"] for row in revisions)), revision_events=dict(event_counts),
        adoption_status=dict(Counter(row["status"] for row in decisions)),
        archive_source=archive_source, archive_error=archive_error, archive_url=ARCHIVE,
        early_pdfs=len(pdfs), stored_pdfs=sum(row["acquisition_status"] == "stored_pdf" for row in pdfs), tests=tests)
    (OUT / "validation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return all(tests.values())


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

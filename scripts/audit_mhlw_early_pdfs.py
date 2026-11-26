#!/usr/bin/env python3
"""Acquire official PDFs outside Git and audit table extraction and provenance."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import fitz

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/audits/mhlw/resource_quality_20261126"
QUEUE = AUDIT / "definition_review/pdf_only_2020_acquisition_queue.csv"
OUT = AUDIT / "early_pdf_audit"
JST = ZoneInfo("Asia/Tokyo")
NAMES = "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
REGION = re.compile(r"^\s*(?:\d{1,2}\s*)?(" + "|".join(NAMES + ["全国", "合計", "総計"]) + r")\s*")
NUMBER = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)")
DATE = r"(?:令和\s*(\d+)\s*年\s*|(?:20\d\d)\s*年\s*)?(\d{1,2})\s*月\s*(\d{1,2})\s*日"
LICENSE = "https://www.mhlw.go.jp/chosakuken/"


def now():
    return datetime.now(JST).isoformat(timespec="seconds")


def norm(text):
    return unicodedata.normalize("NFKC", text or "")


def compact(text):
    return re.sub(r"\s+", "", norm(text))


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def save(name, fields, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields.split(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fetch(row, private):
    url = row["url"]
    name = url.rsplit("/", 1)[-1]
    result = dict(url=url, final_url="", archive_observation_date=row["observation_date"], archive_label=row["archive_label"],
                  retrieved_at_jst=now(), http_status="", mime="", format="", bytes="", sha256="",
                  status="failed", error="", title=row["archive_label"].split("（2020年")[0],
                  publisher="厚生労働省", body_observation_dates="不明", publication_dates="不明",
                  revision_dates="不明", license_url=LICENSE, redistribution="PDF本体は作業用保管")
    for _ in range(2):
        try:
            with urlopen(url, timeout=20) as response:
                result.update(http_status=response.status, mime=response.headers.get("Content-Type", ""),
                              final_url=response.geturl())
                body = response.read()
            if not body.startswith(b"%PDF-"):
                raise ValueError("PDF signature missing")
            with fitz.open(stream=body, filetype="pdf") as pdf:
                if not len(pdf):
                    raise ValueError("No pages")
                version = pdf.metadata.get("format", "PDF")
            (private / name).write_bytes(body)
            result.update(format=version, bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                          status="downloaded", error="")
            break
        except HTTPError as exc:
            result.update(http_status=exc.code, final_url=exc.geturl(), mime=exc.headers.get("Content-Type", ""), error=str(exc))
        except (OSError, ValueError, RuntimeError) as exc:
            result["error"] = str(exc)
    result["retrieved_at_jst"] = now()
    return result


def days(text, suffix, anchor_year):
    found = []
    for era, mo, day in re.findall(DATE + suffix, norm(text)):
        year = 2018 + int(era) if era else anchor_year
        try:
            found.append(datetime(year, int(mo), int(day)).date().isoformat())
        except ValueError:
            continue
    return "|".join(sorted(set(found))) or "不明"


def numeric(cell):
    cell = norm(cell).strip()
    return int(cell.replace(",", "")) if NUMBER.fullmatch(cell) else None


def pdf_rows(text):
    rows = {}
    for line in norm(text).splitlines():
        match = REGION.match(line)
        if match:
            key = match[1] if match[1] in NAMES else "全国"
            rows.setdefault(key, []).append(tuple(re.sub(r"\s*/\s*", "/", line[match.end():]).split()))
    return rows


def inspect_pdf(path, record, private):
    plain = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True).stdout.decode()
    poppler_pages = plain.split("\f")
    record["body_observation_dates"] = days("\n".join(plain.splitlines()[:15]), r"\s*(?:\d{1,2}\s*時\s*)?(?:時点|現在)", 2020)
    record["publication_dates"] = days(plain, r"\s*公表", 2020)
    record["revision_dates"] = days(plain, r"\s*(?:付け?\s*)?修正", 2020)
    contents, comparisons, sums = [], [], []
    with fitz.open(path) as pdf:
        for page_no, page in enumerate(pdf, 1):
            layout = poppler_pages[page_no-1] if page_no <= len(poppler_pages) else ""
            lines = layout.splitlines()
            data_lines = [i for i, line in enumerate(lines) if REGION.match(norm(line))]
            heading = lines[:min(data_lines)] if data_lines else lines[:15]
            footer = lines[max(data_lines)+1:] if data_lines else []
            notes = [line.strip() for line in footer if line.strip()]
            raster = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            raster.save(private / f"{path.stem}-{page_no}.png")
            page_entry = {"url": record["url"], "page": page_no, "headings": heading, "footnotes_and_footer": notes,
                          "layout_text": layout.splitlines(), "attribution": "厚生労働省公表資料（上記URL）を加工して作成", "render_sha256": hashlib.sha256(raster.samples).hexdigest(),
                          "tables": []}
            independent = pdf_rows(layout)
            for table_index, table in enumerate(page.find_tables().tables, 1):
                original = table.extract()
                rows = {}
                cells = []
                for i, row in enumerate(original):
                    area = next((REGION.fullmatch(norm(value).strip()) for value in row[:3]
                                 if value and REGION.fullmatch(norm(value).strip())), None)
                    if not area:
                        continue
                    key = area[1] if area[1] in NAMES else "全国"
                    region_column = next(j for j, value in enumerate(row[:3]) if value and REGION.fullmatch(norm(value).strip()))
                    values = row[region_column+1:]
                    tokens = tuple(compact(value) for value in values if compact(value))
                    visual_tokens = independent.get(key, [])
                    same = len(visual_tokens) == 1 and tokens == visual_tokens[0]
                    rows.setdefault(key, []).append((values, same))
                    cells.append(dict(grid_row=i+1, area=key, values=values, poppler_tokens=visual_tokens, match=same))
                coverage = sum(len(rows.get(name, [])) == 1 for name in NAMES)
                matched = sum(len(rows.get(name, [])) == 1 and rows[name][0][1] for name in NAMES)
                total = rows.get("全国", [])
                status = "screened_grid" if coverage == matched == 47 and len(total) == 1 and total[0][1] else "hold"
                page_entry["tables"].append(dict(table=table_index, bbox=list(table.bbox), grid=original, region_rows=cells, status=status))
                comparisons.append(dict(url=record["url"], page=page_no, table=table_index, prefectures=coverage,
                                        verified_prefectures=matched, national_rows=len(total), status=status))
                if status == "screened_grid":
                    for index, value in enumerate(total[0][0]):
                        national = numeric(value)
                        if national is None:
                            continue
                        pref = [numeric(rows[name][0][0][index]) if index < len(rows[name][0][0]) else None for name in NAMES]
                        present = [v for v in pref if v is not None]
                        status_sum = "incomplete" if len(present) != 47 else "match" if sum(present) == national else "mismatch"
                        sums.append(dict(url=record["url"], page=page_no, table=table_index, position_after_region=index+1,
                                         national=national, numeric_prefectures=len(present),
                                         prefecture_sum=sum(present) if len(present)==47 else "", status=status_sum))
            if not page_entry["tables"]:
                comparisons.append(dict(url=record["url"], page=page_no, table="", prefectures=sum(n in independent for n in NAMES),
                                        verified_prefectures=0, national_rows=len(independent.get("全国", [])), status="hold"))
            contents.append(page_entry)
    return contents, comparisons, sums


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True, help="Local working directory outside the repository")
    args = parser.parse_args()
    private = args.private_dir.resolve()
    if private.is_relative_to(ROOT):
        raise SystemExit("--private-dir must be outside the repository")
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    OUT.mkdir(parents=True, exist_ok=True)
    started = now()
    queue = csv_rows(QUEUE)
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifest = list(pool.map(lambda row: fetch(row, private), queue))
    pages, tables, totals = [], [], []
    errors = []
    for record in manifest:
        if record["status"] != "downloaded":
            continue
        path = private / record["url"].rsplit("/", 1)[-1]
        try:
            content, checked, sums = inspect_pdf(path, record, private)
            pages.extend(content)
            tables.extend(checked)
            totals.extend(sums)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            errors.append(dict(url=record["url"], error=str(exc)))
    save("acquisition_manifest.csv", "url final_url archive_observation_date archive_label retrieved_at_jst http_status mime format bytes sha256 "
         "status error title publisher body_observation_dates publication_dates revision_dates license_url redistribution", manifest)
    save("table_screening.csv", "url page table prefectures verified_prefectures national_rows status", tables)
    save("national_totals.csv", "url page table position_after_region national numeric_prefectures prefecture_sum status", totals)
    with (OUT / "page_extraction.jsonl").open("w", encoding="utf-8") as handle:
        for page in pages:
            handle.write(json.dumps(page, ensure_ascii=False, separators=(",", ":")) + "\n")
    downloaded = [row for row in manifest if row["status"] == "downloaded"]
    december_totals = {row["national"] for row in totals
                       if row["url"].endswith("/000707318.pdf") and row["status"] == "match"}
    tests = dict(queue_complete=len(manifest)==len({row["url"] for row in manifest})==36,
                 all_36_downloaded=len(downloaded)==36,
                 rendered_all_extracted_pages=all(page["render_sha256"] for page in pages),
                 december_sample_visual_totals={10047, 27235} <= december_totals,
                 screen_requires_full_coverage=all(row["prefectures"] == row["verified_prefectures"] == 47
                     and row["national_rows"] == 1 for row in tables if row["status"] == "screened_grid"),
                 acquisition_provenance=all(row["http_status"]==200 and row["format"].startswith("PDF") and row["sha256"]
                                            for row in downloaded),
                 extracted_downloads={row["url"] for row in downloaded}=={row["url"] for row in pages} and not errors,
                 no_imputation=all(row["numeric_prefectures"]==47 or row["prefecture_sum"]=="" for row in totals),
                 nonnumeric_preserved=numeric("－") is None and numeric("") is None and numeric("0")==0)
    report = dict(started_at_jst=started, finished_at_jst=now(), downloads=len(downloaded), pages=len(pages),
                  tables=dict(Counter(row["status"] for row in tables)), national=dict(Counter(row["status"] for row in totals)),
                  extraction_errors=errors, tests=tests)
    (OUT / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return all(tests.values())


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

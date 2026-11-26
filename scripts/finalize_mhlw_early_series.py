#!/usr/bin/env python3
"""Repair early PDF grids and write an explicitly separate prefecture series."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

from audit_mhlw_early_pdfs import AUDIT, NAMES, compact, csv_rows, now, numeric
from build_mhlw_current_metadata import write_csv

OUT = AUDIT / "final_resource_review"
PREVIOUS = AUDIT / "early_pdf_audit"
SPECIAL = {
    ("000633756", 1): ("2020-05-01", "2020-05-07", 638, 725),
    ("000633754", 1): ("2020-05-08", "2020-05-11", 600, 711),
}
PAGE_DATES = {("000633756", 2): "2020-04-28", ("000633754", 2): "2020-05-07"}
REGION = re.compile(r"^\s*(?:\d{1,2}\s*)?(" + "|".join(NAMES + ["全国", "合計", "総計"]) + ")")
ANNOTATION = re.compile(r"\(?注\d+\)?|※\d+")
DASH = set("-－—―–ー−")


def area(name):
    found = REGION.fullmatch(ANNOTATION.sub("", compact(name).translate(str.maketrans({"⻘":"青", "⻑":"長"}))))
    if found:
        return found[1] if found[1] in NAMES else "全国"
    return ""


def clean_value(value):
    return compact(ANNOTATION.sub("", unicodedata.normalize("NFKC", value or "")))


def row_tokens(line):
    match = REGION.match(line)
    if not match:
        return "", []
    name = match[1] if match[1] in NAMES else "全国"
    rest = re.sub(r"\s*/\s*", "/", line[match.end():])
    rest = re.sub(r"\(?\s*注\s*\d+\s*\)?|※\s*\d+", " ", rest)
    return name, [token for token in rest.split() if token]


def pref_grid(page, old, ident, page_no):
    table = min(page.find_tables().tables,
                key=lambda candidate: sum(abs(a-b) for a, b in zip(candidate.bbox, old["bbox"])))
    original = table.extract()
    special = SPECIAL.get((ident, page_no))
    candidates = {}
    rectangles = {}
    for index, row in enumerate(original):
        name = area(row[0])
        if not name:
            continue
        values = row[1:]
        boxes = list(table.rows[index].cells[1:])
        if special:
            _, _, x0, x1 = special
            base = table.rows[index].cells[0]
            if base:
                rect = fitz.Rect(x0, base[1], x1, base[3])
                raw = page.get_textbox(rect).strip().split("\n")[0]
                values = values + [raw]
                boxes += [tuple(rect)]
        candidates.setdefault(name, []).append((values, index))
        rectangles[index] = boxes
    return original, candidates, rectangles


def classify(raw):
    token = compact(raw)
    clean = clean_value(raw)
    if raw is None:
        return "merged_or_unmapped", ""
    if not token:
        return "blank", ""
    if all(char in DASH for char in token):
        return "dash", ""
    if clean == token and numeric(clean) is not None:
        value = numeric(clean)
        return ("reported_zero" if value == 0 else "numeric"), value
    if re.fullmatch(r"\d+(\.\d+)?%", token):
        return "published_percent", token.rstrip("%")
    return "annotated_or_text", ""


def observation(ident, number, archive):
    special = SPECIAL.get((ident, number))
    if special:
        return special[0]
    if (ident, number) in PAGE_DATES:
        return PAGE_DATES[(ident, number)]
    if ident == "000631948":
        return "mixed_2020-05-13_2020-05-15"
    return archive


def process(pdf_dir):
    old_pages = [json.loads(line) for line in (PREVIOUS / "page_extraction.jsonl").read_text().splitlines()]
    manifest = {row["url"]: row for row in csv_rows(PREVIOUS / "acquisition_manifest.csv")}
    audits, series, national, differences = [], [], [], []
    for item in old_pages:
        url, page_no = item["url"], item["page"]
        record = manifest[url]
        pdf_path = pdf_dir / url.rsplit("/", 1)[-1]
        ident = pdf_path.stem
        if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"PDF checksum mismatch: {url}")
        poppler = subprocess.run(["pdftotext", "-f", str(page_no), "-l", str(page_no),
                                  "-layout", str(pdf_path), "-"], check=True, capture_output=True).stdout.decode()
        lines = {}
        for line in unicodedata.normalize("NFKC", poppler).translate(str.maketrans({"⻘":"青", "⻑":"長"})).splitlines():
            name, tokens = row_tokens(line)
            if name:
                lines.setdefault(name, []).append(tokens)
        with fitz.open(pdf_path) as document:
            page = document[page_no-1]
            rendered = page.get_pixmap(alpha=False)
            page_hash = hashlib.sha256(rendered.samples).hexdigest()
            for table in item["tables"]:
                original, rows, boxes = pref_grid(page, table, ident, page_no)
                valid = []
                for name in NAMES + ["全国"]:
                    cells, ref = rows.get(name, []), lines.get(name, [])
                    actual = [clean_value(value) for value in cells[0][0] if clean_value(value)] if len(cells)==1 else []
                    if ident == "000631948" and name in {"岩手県", "和歌山県", "長崎県"} and len(cells)==1 and cells[0][0][8]=="ʷ":
                        # Embedded glyph renders as a dash, which Poppler omits.
                        actual = [clean_value(value) for j, value in enumerate(cells[0][0]) if j!=8 and clean_value(value)]
                    if len(cells)==len(ref)==1 and actual == ref[0]:
                        valid.append(name)
                    else:
                        differences.append(dict(url=url,page=page_no,table=table["table"],area=name,
                            grid=json.dumps(actual, ensure_ascii=False), independent=json.dumps(ref, ensure_ascii=False),
                            grid_occurrences=len(cells), reference_occurrences=len(ref)))
                accepted = len(valid)==48
                day = observation(ident, page_no, record["archive_observation_date"])
                first = min((index for values in rows.values() for _, index in values), default=0)
                columns = zip(*original[:first])
                labels = [" / ".join(dict.fromkeys(compact(a) for a in col if compact(a))) for col in columns][1:]
                special = SPECIAL.get((ident, page_no))
                if special:
                    labels.append("宿泊施設受入可能室数（参考）")
                audits.append(dict(url=url,page=page_no,table=table["table"],archive_date=record["archive_observation_date"],
                    table_date=day, before=table["status"], after="verified" if accepted else "hold",
                    prefectures=sum(len(rows.get(name, []))==1 for name in NAMES), matched=len(valid),
                    grid_bbox=json.dumps(table["bbox"]), raster_sha256=page_hash,
                    merged_or_unmapped_cells=sum(x is None for row in original for x in row),
                    method="座標で参考列を復元し脚注識別子を比較時のみ分離" if special else "NFKC都道府県名と脚注識別子の分離、矩形グリッドとPoppler行の一致"))
                if not accepted:
                    continue
                country = rows["全国"][0][0]
                for col, country_raw in enumerate(country):
                    value = numeric(country_raw)
                    if value is None:
                        continue
                    values = [numeric(rows[name][0][0][col]) for name in NAMES]
                    count = sum(v is not None for v in values)
                    total = sum(values) if count==47 else ""
                    national.append(dict(url=url,page=page_no,table=table["table"],column=col+1, national=value,
                        numeric_prefectures=count,prefecture_sum=total,
                        status=("incomplete" if count!=47 else "match" if total==value else "mismatch")))
                for name in NAMES:
                    values, index = rows[name][0]
                    for col, raw in enumerate(values):
                        documented_dash = ident=="000631948" and col==8 and raw=="ʷ" and name in {"岩手県","和歌山県","長崎県"}
                        status, value = ("dash", "") if documented_dash else classify(raw)
                        metric_id = f"early_pdf:{ident}:{page_no}:{table['table']}:{col+1}"
                        metric_date=(special[1] if col==2 else day) if special else (
                            "2020-05-15" if col in (2,3,5,6) else "2020-05-14" if col==8 else "2020-05-13"
                            ) if ident=="000631948" else ""
                        series.append(dict(source_series="mhlw_early_pdf_only",url=url,sha256=record["sha256"],
                            archive_date=record["archive_observation_date"],table_date=day,
                            metric_reference_date=metric_date, observation_date=metric_date or day,
                            series_use="reference_page_hold" if (ident,page_no) in PAGE_DATES else "pdf_only",
                            page=page_no,table=table["table"],row=index+1,column=col+1,
                            cell_bbox=json.dumps(boxes[index][col]),prefecture_code=f"{NAMES.index(name)+1:02d}",
                            prefecture=name,metric_id=metric_id,header=labels[col],raw_value=raw,
                            value_status=status,numeric_value=value, excel_join_allowed="false"))
    return audits, series, national, differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    args = parser.parse_args()
    start = now()
    OUT.mkdir(exist_ok=True)
    audits, series, national, differences = process(args.pdf_dir)
    for name, rows in [("early_table_review",audits),("early_prefecture_series",series),
                       ("early_national_checks",national),("early_row_differences",differences)]:
        if rows:
            write_csv(OUT / f"{name}.csv", rows)
    if not differences:
        with (OUT/"early_row_differences.csv").open("w",encoding="utf-8",newline="") as stream:
            csv.writer(stream,lineterminator="\n").writerow(
                ["url","page","table","area","grid","independent","grid_occurrences","reference_occurrences"])
    tests = dict(all_38_tables_assessed=len(audits)==38,
        all_nine_rechecked=sum(x["before"]=="hold" for x in audits)==9,
        reference_pages_explicitly_flagged=sum(r["series_use"]=="reference_page_hold" for r in series)>0,
        approved_tables_require_48_matched_rows=all(x["matched"]==48 for x in audits if x["after"]=="verified"),
        series_has_unique_source_cells=len({(r["prefecture_code"],r["metric_id"]) for r in series})==len(series),
        no_zero_imputation=all(r["numeric_value"]=="" for r in series if r["value_status"] in ("dash","blank","merged_or_unmapped")),
        no_excel_join=all(r["excel_join_allowed"]=="false" for r in series),
        annotated_severe_values_preserved=all(any(r["url"].endswith("/000694896.pdf") and r["prefecture"]=="大阪府"
            and token in (r["raw_value"] or "") and r["numeric_value"]=="" for r in series) for token in ("51(35)",)),
        reference_dates_not_collapsed=any(r["table_date"]=="2020-05-01" and r["metric_reference_date"]=="2020-05-07" for r in series))
    result = dict(start_jst=start,end_jst=now(),transitions=dict(Counter(f'{r["before"]}->{r["after"]}' for r in audits)),
        series_rows=len(series),national=dict(Counter(r["status"] for r in national)),tests=tests)
    (OUT/"early_validation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return all(tests.values())


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)

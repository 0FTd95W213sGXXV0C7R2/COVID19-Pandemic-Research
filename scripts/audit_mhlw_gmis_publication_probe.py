#!/usr/bin/env python3
"""Audit structure and comparability of two MHLW G-MIS publication CSV snapshots."""
from __future__ import annotations
import csv, hashlib, io, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/raw/mhlw/gmis_publication_probe"
OUT = ROOT / "data/audits/mhlw/gmis_publication_probe_audit.json"
FILES = [
    ("2022-01-05_candidate", BASE / "mhlw_gmis_historical_link_000893241.csv"),
    ("2024-03-06_candidate", BASE / "mhlw_gmis_snapshot_link_001234488.csv"),
]
EXPECTED_HEADER_KEYS = {"都道府県番号", "都道府県", "医療機関コード", "医療機関名", "報告状況", "実績日", "確保病床数", "即応病床数"}

def parse_file(label, path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    decoded = None
    encoding = None
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            decoded = data.decode(enc)
            encoding = enc
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise RuntimeError(f"Could not decode {path}")
    rows = list(csv.reader(io.StringIO(decoded)))
    header_idx = None
    header = None
    for i, row in enumerate(rows):
        values = {str(x).strip() for x in row}
        if EXPECTED_HEADER_KEYS.issubset(values):
            header_idx, header = i, [str(x).strip() for x in row]
            break
    if header_idx is None:
        raise RuntimeError(f"Header row not found in {path}")
    records = []
    for line_no, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(str(x).strip() for x in row):
            continue
        row = row + [""] * max(0, len(header) - len(row))
        records.append((line_no, dict(zip(header, row[:len(header)]))))
    date_col = next((x for x in header if x == "実績日"), None)
    code_col = "医療機関コード"
    status_col = "報告状況"
    codes = [r.get(code_col, "").strip() for _, r in records]
    date_values = [r.get(date_col, "").strip() for _, r in records if r.get(date_col, "").strip()]
    dates = sorted(set(date_values))
    date_value_counts = dict(Counter(date_values))
    nonstandard_date_rows = [
        {"line": line_no, "medical_institution_code": r.get(code_col, "").strip(),
         "medical_institution_name": r.get("医療機関名", "").strip(),
         "raw_date_value": r.get(date_col, "").strip()}
        for line_no, r in records
        if r.get(date_col, "").strip() and not ("/" in r.get(date_col, "").strip())
    ]
    missing = {col: sum(not str(r.get(col, "")).strip() for _, r in records) for col in header}
    status_counts = dict(Counter(r.get(status_col, "").strip() or "(blank)" for _, r in records))
    numeric = {}
    for col in header:
        if any(k in col for k in ("確保病床数", "即応病床数", "入院中")):
            vals = [r.get(col, "").strip() for _, r in records]
            numeric[col] = {
                "numeric": sum(v.isdigit() for v in vals),
                "blank": sum(not v for v in vals),
                "non_numeric_nonblank": sum(bool(v) and not v.isdigit() for v in vals),
                "zero": sum(v == "0" for v in vals),
            }
    return {
        "label": label,
        "filename": path.name,
        "bytes": len(data),
        "sha256": digest,
        "encoding": encoding,
        "row_count_including_blanks": len(rows),
        "header_line_1based": header_idx + 1,
        "header": header,
        "data_record_count": len(records),
        "unique_nonblank_medical_institution_codes": len(set(x for x in codes if x)),
        "blank_medical_institution_codes": sum(not x for x in codes),
        "duplicate_medical_institution_code_count": len([x for x, n in Counter(codes).items() if x and n > 1]),
        "duplicate_medical_institution_code_excess_rows": sum(n - 1 for x, n in Counter(codes).items() if x and n > 1),
        "observation_dates_raw": dates,
        "observation_date_raw_value_counts": date_value_counts,
        "nonstandard_date_value_rows": nonstandard_date_rows,
        "report_status_counts": status_counts,
        "missing_values_by_column": missing,
        "numeric_field_checks": numeric,
    }, set(x for x in codes if x)

def main():
    results = []
    code_sets = {}
    for label, path in FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        summary, codes = parse_file(label, path)
        results.append(summary)
        code_sets[label] = codes
    a, b = code_sets.values()
    intersection = len(a & b)
    union = len(a | b)
    now = datetime.now(timezone.utc)
    audit = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "status": "PRELIMINARY_SNAPSHOT_STRUCTURE_AUDIT",
        "interpretation": "Two separate cross-sectional publication snapshots; not a continuous time series by themselves.",
        "facility_code_overlap": {
            "intersection_count": intersection,
            "union_count": union,
            "jaccard": intersection / union if union else None,
            "only_in_first_snapshot": len(a - b),
            "only_in_second_snapshot": len(b - a),
        },
        "snapshots": results,
        "not_done": [
            "No normalization or longitudinal join",
            "No imputation of blanks or nonresponses",
            "No interpretation of facility-level missingness as zero",
            "No inference that facility-code overlap proves constant reporting coverage",
            "No calculation of occupancy rate until denominator and reporting status are audited",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

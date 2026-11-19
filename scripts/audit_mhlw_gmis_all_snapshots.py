#!/usr/bin/env python3
"""Full structural and coverage audit for all MHLW G-MIS public snapshots."""
from __future__ import annotations
import csv, hashlib, io, json, re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/metadata/mhlw/gmis_all_snapshots_manifest.json"
OUT = ROOT / "data/audits/mhlw/gmis_all_snapshots_audit.json"

def parse_date(value):
    s = str(value or "").strip()
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d).date().isoformat()
    if s.isdigit():
        try:
            return (datetime(1899, 12, 30) + timedelta(days=int(s))).date().isoformat()
        except Exception:
            return None
    return None

def parse_int(value):
    s = str(value or "").strip().replace(",", "")
    return int(s) if re.fullmatch(r"-?\d+", s) else None

def decode_csv(data):
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return enc, list(csv.reader(io.StringIO(data.decode(enc))))
        except (UnicodeDecodeError, csv.Error):
            pass
    return None, None

def find_header(rows):
    for i, row in enumerate(rows[:100]):
        cells = {str(x).strip() for x in row}
        if ({"医療機関コード", "実績日", "確保病床数"}.issubset(cells)
            and any(x in cells for x in ("即応病床数", "即応病床"))
            and any(x in cells for x in ("入院中患者数", "入院中"))):
            header = [str(x).strip() for x in row]
            while header and not header[-1]:
                header.pop()
            return i, header
    return None, None

def inspect(item):
    path = ROOT / item["local_path"]
    data = path.read_bytes()
    enc, rows = decode_csv(data)
    if rows is None:
        return {"snapshot_date": item["snapshot_date"], "status": "decode_failed"}
    hi, header = find_header(rows)
    if hi is None:
        return {"snapshot_date": item["snapshot_date"], "status": "header_not_recognized",
                "encoding": enc, "bytes": len(data),
                "first_nonempty_rows": [r for r in rows[:25] if any(str(x).strip() for x in r)][:20]}
    records = []
    for row in rows[hi + 1:]:
        if not any(str(x).strip() for x in row):
            continue
        row = row + [""] * max(0, len(header) - len(row))
        records.append(dict(zip(header, row[:len(header)])))
    code_col = "医療機関コード"
    status_col = "報告状況" if "報告状況" in header else None
    date_col = "実績日"
    secured_col = "確保病床数"
    immediate_col = next(x for x in header if x in ("即応病床数", "即応病床"))
    inpatient_col = next(x for x in header if x in ("入院中患者数", "入院中"))
    codes = [str(r.get(code_col, "")).strip() for r in records]
    code_counts = Counter(x for x in codes if x)
    raw_dates = Counter(str(r.get(date_col, "")).strip() for r in records if str(r.get(date_col, "")).strip())
    normalized_dates = Counter()
    for raw, count in raw_dates.items():
        normalized_dates[parse_date(raw) or f"UNPARSED:{raw}"] += count
    published_date = item.get("snapshot_date")
    mismatch = [{"raw_value": raw, "normalized": parse_date(raw), "rows": count}
                for raw, count in raw_dates.items() if parse_date(raw) != published_date]
    numeric_checks = {}
    for col in (secured_col, immediate_col, inpatient_col):
        vals = [str(r.get(col, "")).strip() for r in records]
        numeric_checks[col] = {
            "numeric": sum(parse_int(v) is not None for v in vals),
            "blank": sum(not v for v in vals),
            "non_numeric_nonblank": sum(bool(v) and parse_int(v) is None for v in vals),
            "zero": sum(parse_int(v) == 0 for v in vals if v),
            "sum_numeric": sum(parse_int(v) for v in vals if parse_int(v) is not None),
        }
    return {
        "snapshot_date": published_date, "published_label": item.get("published_label"),
        "source_url": item["source_url"], "local_path": item["local_path"],
        "status": "audited", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "encoding": enc, "header_line_1based": hi + 1, "header": header,
        "schema_signature": "|".join(header), "facility_records": len(records),
        "unique_nonblank_facility_codes": len(set(x for x in codes if x)),
        "blank_facility_codes": sum(not x for x in codes),
        "duplicate_facility_code_count": sum(n > 1 for n in code_counts.values()),
        "duplicate_facility_code_excess_rows": sum(n - 1 for n in code_counts.values() if n > 1),
        "report_status_counts": dict(Counter(str(r.get(status_col, "")).strip() or "(blank)" for r in records)) if status_col else {},
        "raw_observation_date_counts": dict(raw_dates),
        "normalized_observation_date_counts": dict(normalized_dates),
        "observation_date_mismatches": mismatch,
        "numeric_field_checks": numeric_checks,
        "missing_values_by_column": {col: sum(not str(r.get(col, "")).strip() for r in records) for col in header},
        "field_crosswalk": {"secured_beds": secured_col, "immediately_available_beds": immediate_col, "inpatients": inpatient_col},
    }

def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = [x for x in manifest.get("results", []) if x.get("status") == "downloaded"]
    results = [inspect(x) for x in items]
    results.sort(key=lambda x: x.get("snapshot_date", ""))
    audited = [x for x in results if x.get("status") == "audited"]
    # Adjacent-snapshot overlap: calculate facility-code panel stability.
    overlaps, previous_codes, previous_date = [], None, None
    for item in sorted(items, key=lambda x: x.get("snapshot_date", "")):
        data = (ROOT / item["local_path"]).read_bytes()
        enc, rows = decode_csv(data)
        if rows is None:
            continue
        hi, header = find_header(rows)
        if hi is None:
            continue
        idx = header.index("医療機関コード")
        codes = {row[idx].strip() for row in rows[hi+1:] if len(row) > idx and row[idx].strip()}
        date = item["snapshot_date"]
        if previous_codes is not None:
            inter, union = len(previous_codes & codes), len(previous_codes | codes)
            overlaps.append({
                "from_snapshot": previous_date, "to_snapshot": date,
                "days_between": (datetime.fromisoformat(date)-datetime.fromisoformat(previous_date)).days,
                "previous_facilities": len(previous_codes), "current_facilities": len(codes),
                "intersection": inter, "union": union, "jaccard": inter/union if union else None,
                "previous_only": len(previous_codes-codes), "current_only": len(codes-previous_codes),
            })
        previous_codes, previous_date = codes, date
    signatures = Counter(x.get("schema_signature", "UNRECOGNIZED") for x in audited)
    intervals = [(datetime.fromisoformat(audited[i]["snapshot_date"])-datetime.fromisoformat(audited[i-1]["snapshot_date"])).days for i in range(1, len(audited))]
    now = datetime.now(timezone.utc)
    audit = {
        "created_at_utc": now.isoformat(), "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "source_manifest": "data/metadata/mhlw/gmis_all_snapshots_manifest.json",
        "discovered_csv_count": manifest.get("discovered_unique_csv_url_count"),
        "downloaded_csv_count": manifest.get("downloaded_count"),
        "audited_csv_count": len(audited), "unrecognized_or_failed_count": len(results)-len(audited),
        "snapshot_date_range": [audited[0]["snapshot_date"], audited[-1]["snapshot_date"]] if audited else None,
        "snapshot_intervals_days": {"minimum": min(intervals) if intervals else None,
                                    "maximum": max(intervals) if intervals else None,
                                    "distribution": dict(Counter(intervals))},
        "schema_variant_count": len(signatures), "schema_variant_snapshot_counts": dict(signatures),
        "snapshots": results, "adjacent_facility_coverage_overlap": overlaps,
        "interpretation_limits": [
            "These are dated public snapshots, not a daily G-MIS time series.",
            "The official target population excludes institutions/beds accepting suspected cases and temporary medical facilities.",
            "Unreported rows do not mean zero and may display previously entered values.",
            "The earliest snapshot uses shorter immediate-bed and inpatient column labels; the semantic crosswalk is provisional.",
            "No occupancy rates, imputations, longitudinal panel, or analytical dataset were created.",
            "Facility-list changes may reflect designation/reporting coverage changes, not only hospital openings or closures."
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "created_at_jst": audit["created_at_jst"], "discovered": audit["discovered_csv_count"],
        "downloaded": audit["downloaded_csv_count"], "audited": audit["audited_csv_count"],
        "unrecognized": audit["unrecognized_or_failed_count"], "date_range": audit["snapshot_date_range"],
        "intervals": audit["snapshot_intervals_days"], "schema_variants": audit["schema_variant_snapshot_counts"],
        "snapshots": [{"date": x.get("snapshot_date"), "records": x.get("facility_records"),
                       "unique_facilities": x.get("unique_nonblank_facility_codes"),
                       "report_status": x.get("report_status_counts"),
                       "date_mismatch": x.get("observation_date_mismatches"),
                       "headers": x.get("header"), "numeric": x.get("numeric_field_checks")}
                      for x in results]
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

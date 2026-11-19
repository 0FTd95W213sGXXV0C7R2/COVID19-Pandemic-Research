#!/usr/bin/env python3
"""Audit weekly MHLW hospitalization survey workbooks without normalizing data."""
from __future__ import annotations
import hashlib, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
OUT = ROOT / "data/audits/mhlw/weekly_inpatient_survey_audit.json"
PREFECTURES = {
"北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県",
"埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県",
"岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
"鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県",
"佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県","全国"
}

def clean(v):
    return str(v).replace("\n"," ").strip() if v is not None else ""

def numeric(v):
    if isinstance(v, (int, float)):
        return True
    s = clean(v).replace(",", "")
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", s))

def inspect(item):
    path = ROOT / item["local_path"]
    data = path.read_bytes()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    header_row = None
    pref_col = None
    for i, row in enumerate(rows[:20]):
        for j, v in enumerate(row):
            if clean(v) in ("都道府県名", "都道府県"):
                header_row, pref_col = i, j
                break
        if header_row is not None:
            break
    if header_row is None:
        wb.close()
        return {"snapshot_date": item["snapshot_date"], "status": "prefecture_header_not_found",
                "sheetnames": wb.sheetnames, "max_row": ws.max_row, "max_column": ws.max_column}
    start = max(0, header_row - 3)
    end = min(len(rows), header_row + 3)
    labels = []
    for col in range(ws.max_column or 0):
        parts = []
        for rr in rows[start:end]:
            if col < len(rr):
                val = clean(rr[col])
                if val and val not in parts:
                    parts.append(val)
        labels.append(" / ".join(parts))
    data_rows = []
    for row in rows[header_row + 1:]:
        if pref_col < len(row) and clean(row[pref_col]) in PREFECTURES:
            data_rows.append(row)
    prefecture_values = [clean(row[pref_col]) for row in data_rows]
    field_checks = {}
    keywords = ("PCR検査陽性者数","療養者数","入院者数","在院者数","確保病床","病床数","重症者数","中等症Ⅱ","宿泊療養者数","自宅療養者数")
    for col, label in enumerate(labels):
        if any(k in label for k in keywords):
            vals = [row[col] if col < len(row) else None for row in data_rows]
            field_checks[str(col + 1) + ":" + label] = {
                "numeric": sum(numeric(v) for v in vals if v is not None),
                "blank": sum(v is None or clean(v)=="" for v in vals),
                "non_numeric_nonblank": sum(v is not None and clean(v)!="" and not numeric(v) for v in vals),
            }
    title = " ".join(clean(v) for row in rows[:3] for v in row if v is not None)
    md = re.search(r"(\d{1,2})月(\d{1,2})日", title)
    title_month_day = f"{int(md.group(1)):02d}-{int(md.group(2)):02d}" if md else None
    note_rows = []
    for row in rows[-8:]:
        vals = [clean(v) for v in row if clean(v)]
        if vals:
            note_rows.append(" | ".join(vals)[:500])
    wb.close()
    return {
        "snapshot_date": item["snapshot_date"],
        "source_url": item["source_url"],
        "local_path": item["local_path"],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "workbook_status": "audited",
        "sheet_names": wb.sheetnames,
        "sheet_max_row": ws.max_row,
        "sheet_max_column": ws.max_column,
        "prefecture_header_row_1based": header_row + 1,
        "prefecture_column_1based": pref_col + 1,
        "data_row_count": len(data_rows),
        "unique_prefecture_names": len(set(prefecture_values)),
        "missing_prefecture_names": sorted(PREFECTURES - set(prefecture_values) - {"全国"}),
        "contains_national_total": "全国" in set(prefecture_values),
        "title_month_day": title_month_day,
        "header_labels_by_column": labels,
        "schema_signature": "||".join(labels),
        "field_checks": field_checks,
        "bottom_notes": note_rows,
    }

def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = [x for x in manifest["results"] if x.get("status") == "downloaded"]
    results = [inspect(x) for x in items]
    results.sort(key=lambda x: x.get("snapshot_date", ""))
    variants = Counter(x.get("schema_signature", "UNRECOGNIZED") for x in results)
    dates = [datetime.fromisoformat(x["snapshot_date"]) for x in results if x.get("snapshot_date") != "unknown"]
    intervals = [(dates[i]-dates[i-1]).days for i in range(1,len(dates))]
    now = datetime.now(timezone.utc)
    audit = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "source_manifest": "data/metadata/mhlw/weekly_inpatient_survey_manifest.json",
        "discovered_workbooks": manifest.get("discovered_unique_excel_count"),
        "downloaded_workbooks": manifest.get("downloaded_count"),
        "audited_workbooks": sum(x.get("workbook_status") == "audited" for x in results),
        "snapshot_date_range": [results[0]["snapshot_date"], results[-1]["snapshot_date"]] if results else None,
        "interval_days_distribution": dict(Counter(intervals)),
        "schema_variant_count": len(variants),
        "schema_variant_counts": dict(variants),
        "workbooks": results,
        "limitations": [
            "The survey is a separate prefecture-level weekly series, not the facility-level G-MIS series.",
            "Header/schema changes across dates require separate variable crosswalks; no automatic concatenation was performed.",
            "No missing-value imputation, occupancy-rate calculation, or analysis dataset update was performed.",
            "The public page lists earlier 2020 materials in PDF form; this acquisition covers only the Excel files linked on the page."
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "created_at_jst": audit["created_at_jst"],
        "discovered": audit["discovered_workbooks"],
        "downloaded": audit["downloaded_workbooks"],
        "audited": audit["audited_workbooks"],
        "date_range": audit["snapshot_date_range"],
        "interval_days": audit["interval_days_distribution"],
        "schema_variants": audit["schema_variant_counts"],
        "snapshots": [{
            "date": x["snapshot_date"], "rows": x.get("data_row_count"),
            "unique_prefectures": x.get("unique_prefecture_names"),
            "national_total": x.get("contains_national_total"),
            "header": x.get("header_labels_by_column"),
        } for x in results]
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

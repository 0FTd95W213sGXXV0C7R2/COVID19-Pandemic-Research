#!/usr/bin/env python3
"""Compact structural/schema audit for all official MHLW weekly survey Excel files."""
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
    return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", clean(v).replace(",", "")))

def inspect(item):
    path = ROOT / item["local_path"]
    data = path.read_bytes()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    header_row = pref_col = None
    for i, row in enumerate(rows[:20]):
        for j, v in enumerate(row):
            if clean(v) in ("都道府県名", "都道府県"):
                header_row, pref_col = i, j
                break
        if header_row is not None:
            break
    if header_row is None:
        wb.close()
        return {"snapshot_date": item["snapshot_date"], "status": "prefecture_header_not_found"}
    labels = []
    for col in range(ws.max_column or 0):
        parts = []
        for rr in rows[max(0, header_row-3):min(len(rows), header_row+3)]:
            if col >= len(rr):
                continue
            val = clean(rr[col])
            if not val or "新型コロナ" in val or "公表" in val or "令和" in val:
                continue
            if re.search(r"\d{1,2}月\d{1,2}日", val):
                continue
            if val not in parts:
                parts.append(val)
        labels.append(" / ".join(parts))
    def norm_pref(v):
        return clean(v).replace(" ", "").replace("　", "")
    data_rows = [row for row in rows[header_row+1:]
                 if pref_col < len(row) and norm_pref(row[pref_col]) in PREFECTURES]
    prefecture_values = [norm_pref(row[pref_col]) for row in data_rows]
    debug_rows = []
    if item["snapshot_date"] in ("2020-12-23", "2021-04-07", "2023-05-03", "2023-10-04", "2024-03-27"):
        for idx, row in enumerate(rows[header_row+1:header_row+16], start=header_row+2):
            debug_rows.append({"row_1based": idx, "cells": [clean(v) for v in row[:10]]})
    field_checks = {}
    keywords = ("PCR検査陽性者数","療養者数","入院者数","在院者数","確保病床","病床数","重症者数","中等症Ⅱ","宿泊療養者数","自宅療養者数")
    for col, label in enumerate(labels):
        if any(k in label for k in keywords):
            vals = [row[col] if col < len(row) else None for row in data_rows]
            field_checks[str(col+1)+":"+label] = {
                "numeric": sum(numeric(v) for v in vals if v is not None),
                "blank": sum(v is None or clean(v)=="" for v in vals),
                "non_numeric_nonblank": sum(v is not None and clean(v)!="" and not numeric(v) for v in vals),
            }
    title = " ".join(clean(v) for row in rows[:3] for v in row if v is not None)
    md = re.search(r"(\d{1,2})月(\d{1,2})日", title)
    title_month_day = f"{int(md.group(1)):02d}-{int(md.group(2)):02d}" if md else None
    sheet_names = wb.sheetnames
    max_row, max_column = ws.max_row, ws.max_column
    wb.close()
    return {
        "snapshot_date": item["snapshot_date"],
        "source_url": item["source_url"],
        "local_path": item["local_path"],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": "audited",
        "sheet_names": sheet_names,
        "sheet_max_row": max_row,
        "sheet_max_column": max_column,
        "data_row_count": len(data_rows),
        "unique_prefecture_names": len(set(prefecture_values)),
        "missing_prefecture_names": sorted(PREFECTURES - set(prefecture_values) - {"全国"}),
        "contains_national_total": "全国" in set(prefecture_values),
        "prefecture_column_1based": pref_col + 1,
        "debug_rows_after_header": debug_rows,
        "title_month_day": title_month_day,
        "header_labels_by_column": labels,
        "schema_signature": "||".join(labels),
        "field_checks": field_checks,
    }

def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = [x for x in manifest["results"] if x.get("status") == "downloaded"]
    inspected = [inspect(x) for x in items]
    inspected.sort(key=lambda x: x.get("snapshot_date", ""))
    schema_defs, snapshots = {}, []
    for item in inspected:
        signature = item.get("schema_signature", "UNRECOGNIZED")
        sid = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:10]
        if sid not in schema_defs:
            schema_defs[sid] = {
                "count": 0,
                "representative_snapshot": item.get("snapshot_date"),
                "header_labels_by_column": item.get("header_labels_by_column", []),
            }
        schema_defs[sid]["count"] += 1
        snapshots.append({
            "snapshot_date": item.get("snapshot_date"),
            "status": item.get("status"),
            "source_url": item.get("source_url"),
            "local_path": item.get("local_path"),
            "sha256": item.get("sha256"),
            "sheet_max_row": item.get("sheet_max_row"),
            "sheet_max_column": item.get("sheet_max_column"),
            "data_row_count": item.get("data_row_count"),
            "unique_prefecture_names": item.get("unique_prefecture_names"),
            "missing_prefecture_names": item.get("missing_prefecture_names"),
            "contains_national_total": item.get("contains_national_total"),
            "prefecture_column_1based": item.get("prefecture_column_1based"),
            "debug_rows_after_header": item.get("debug_rows_after_header", []),
            "title_month_day": item.get("title_month_day"),
            "schema_id": sid,
            "field_checks": item.get("field_checks", {}),
        })
    dates = [datetime.fromisoformat(x["snapshot_date"]) for x in snapshots if x.get("status") == "audited"]
    intervals = [(dates[i]-dates[i-1]).days for i in range(1,len(dates))]
    now = datetime.now(timezone.utc)
    audit = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "source_manifest": "data/metadata/mhlw/weekly_inpatient_survey_manifest.json",
        "discovered_workbooks": manifest.get("discovered_unique_excel_count"),
        "downloaded_workbooks": manifest.get("downloaded_count"),
        "audited_workbooks": sum(x.get("status") == "audited" for x in inspected),
        "snapshot_date_range": [snapshots[0]["snapshot_date"], snapshots[-1]["snapshot_date"]] if snapshots else None,
        "interval_days_distribution": dict(Counter(intervals)),
        "schema_variant_count": len(schema_defs),
        "schema_definitions": schema_defs,
        "snapshots": snapshots,
        "limitations": [
            "This is a prefecture-level weekly survey, separate from facility-level G-MIS snapshots.",
            "Schema changes require date-specific variable crosswalks; no automatic concatenation was performed.",
            "No imputation, occupancy-rate calculation, or analytical dataset update was performed.",
            "The MHLW page contains earlier PDF-only reports; this acquisition covers the Excel links exposed on the page."
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
        "schema_definitions": audit["schema_definitions"],
        "coverage_anomalies": [x for x in snapshots if x.get("missing_prefecture_names")],
        "snapshots": [{k:x.get(k) for k in ("snapshot_date","data_row_count","unique_prefecture_names","contains_national_total","title_month_day","schema_id")} for x in snapshots]
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

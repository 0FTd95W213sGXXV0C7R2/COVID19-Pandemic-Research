#!/usr/bin/env python3
"""Build a conservative, date-specific variable crosswalk from all MHLW weekly workbooks."""
import hashlib, json, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
AUDIT = ROOT / "data/audits/mhlw/weekly_inpatient_survey_audit.json"
OUT = ROOT / "data/audits/mhlw/weekly_inpatient_survey_variable_crosswalk_candidates.json"
PREF_RE = re.compile(r"^\s*(?:0?[1-9]|[1-3][0-9]|4[0-7])\s*[　 ]*(?:北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)")
SPACE_RE = re.compile(r"\s+")
RULES = [
    ("positive_cases_excluding_recovered", r"PCR.*陽性者数"),
    ("inpatients_in_secured_beds", r"確保病床に入院している者数"),
    ("inpatients_outside_secured_beds", r"確保病床外に入院している者数"),
    ("severe_patients_in_secured_beds", r"確保病床に入院している重症者数"),
    ("severe_patients_outside_secured_beds", r"確保病床外に入院している重症者数"),
    ("moderate_severe_II_in_secured_beds", r"確保病床に入院している中等症"),
    ("moderate_severe_II_outside_secured_beds", r"確保病床外に入院している中等症"),
    ("moderate_severe_II_patients_total", r"中等症Ⅱ.*患者数|中等症II.*患者数"),
    ("severe_patients_total", r"重症者数"),
    ("secured_bed_occupancy_rate", r"確保病床\s*使用率|確保病床数に対する使用率"),
    ("room_occupancy_rate", r"確保居室\s*使用率|確保居室数に対する使用率"),
    ("immediately_available_beds", r"即応病床数"),
    ("secured_beds", r"確保病床数"),
    ("hotel_accommodation_patients", r"宿泊療養者数"),
    ("home_care_patients", r"自宅療養者"),
    ("social_welfare_facility_patients", r"社会福祉施設等療養者数"),
    ("patients_under_destination_coordination", r"療養先調整中の人数"),
    ("patients_under_hospital_coordination", r"入院先調整中の人数"),
    ("temporary_facility_patients", r"臨時の医療施設.*療養者数"),
    ("total_inpatients_or_inpatients_present", r"入院者数|在院者数"),
    ("total_patients_in_care", r"療養者数"),
    ("immediately_available_rooms", r"即応居室数"),
    ("secured_rooms", r"確保居室数"),
]
def norm(v):
    return SPACE_RE.sub(" ", str(v)).strip()

def classify(label):
    compact = re.sub(r"\s+", "", label)
    severe_bed_context = "重症者用病床数" in compact
    for key, pattern in RULES:
        if re.search(pattern, compact):
            # Separate severe-specific bed capacity from general bed capacity.
            if severe_bed_context and key in ("immediately_available_beds", "secured_beds", "secured_bed_occupancy_rate"):
                return "severe_specific_" + key
            return key
    return "unclassified"

def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    audit_by_date = {x["snapshot_date"]: x for x in audit.get("snapshots", [])}
    per_snapshot = []
    aggregate = defaultdict(lambda: {"dates": [], "columns": [], "examples": []})
    schema_groups = defaultdict(list)
    for item in manifest.get("results", []):
        if item.get("status") != "downloaded":
            continue
        date = item["snapshot_date"]
        path = ROOT / item["local_path"]
        aud = audit_by_date.get(date, {})
        rec = {"snapshot_date": date, "source_url": item.get("source_url"),
               "local_path": item["local_path"], "manifest_sha256": item.get("sha256"),
               "schema_id": aud.get("schema_id"), "status": "pending"}
        if not path.exists():
            rec["status"] = "file_missing"
            per_snapshot.append(rec)
            continue
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        rec["actual_sha256"] = actual
        rec["sha256_match"] = actual == item.get("sha256")
        try:
            wb = load_workbook(path, data_only=True, read_only=False)
            ws = wb[wb.sheetnames[0]]
            pref_rows = []
            for row in range(1, ws.max_row + 1):
                for col in range(1, min(ws.max_column, 4) + 1):
                    val = ws.cell(row, col).value
                    if isinstance(val, str) and PREF_RE.match(norm(val)):
                        pref_rows.append(row)
                        break
            if len(pref_rows) != 47:
                rec["status"] = "prefecture_row_detection_error"
                rec["detected_prefecture_rows"] = len(pref_rows)
                wb.close()
                per_snapshot.append(rec)
                continue
            first_data = min(pref_rows)
            # Expand merged-cell values so grouped headings are associated with each child column.
            values = {}
            for row in range(1, first_data):
                for col in range(1, ws.max_column + 1):
                    val = ws.cell(row, col).value
                    if val is not None and norm(val):
                        values[(row, col)] = norm(val)
            for merged in ws.merged_cells.ranges:
                min_col, min_row, max_col, max_row = merged.bounds
                anchor = values.get((min_row, min_col))
                if anchor:
                    for rr in range(min_row, min(max_row, first_data - 1) + 1):
                        for cc in range(min_col, max_col + 1):
                            values[(rr, cc)] = anchor
            columns = []
            for col in range(1, ws.max_column + 1):
                labels = []
                for row in range(1, first_data):
                    v = values.get((row, col))
                    if v and (not labels or labels[-1] != v):
                        labels.append(v)
                # Remove repeated document title/date strings from the candidate header.
                labels = [x for x in labels if not re.search(r"(?:令和|平成)\s*[0-9０-９]+年|\d{4}年\s*\d{1,2}月\s*\d{1,2}日|調査結果|新型コロナウイルス感染症患者", x)]
                label = " / ".join(labels)
                if not label:
                    continue
                concept = classify(label)
                vals = [ws.cell(r, col).value for r in pref_rows]
                numeric = sum(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)
                dash = sum(isinstance(v, str) and norm(v) in ("－", "ー", "-", "―") for v in vals)
                blank = sum(v is None or norm(v) == "" for v in vals)
                other = len(vals) - numeric - dash - blank
                colrec = {"column_1based": col, "header_path": labels, "header_label": label,
                          "candidate_concept": concept,
                          "value_profile_47_prefectures": {"numeric": numeric, "dash_like": dash, "blank": blank, "other_nonblank": other}}
                columns.append(colrec)
                key = (concept, label)
                agg = aggregate[key]
                numeric_values = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
                agg.setdefault("numeric_min", None)
                agg.setdefault("numeric_max", None)
                if numeric_values:
                    agg["numeric_min"] = min(numeric_values) if agg["numeric_min"] is None else min(agg["numeric_min"], min(numeric_values))
                    agg["numeric_max"] = max(numeric_values) if agg["numeric_max"] is None else max(agg["numeric_max"], max(numeric_values))
                agg["dash_count"] = agg.get("dash_count", 0) + dash
                agg["blank_count"] = agg.get("blank_count", 0) + blank
                if date not in agg["dates"]:
                    agg["dates"].append(date)
                agg["columns"].append({"date": date, "column": col, "schema_id": aud.get("schema_id")})
                if len(agg["examples"]) < 4:
                    agg["examples"].append({"date": date, "header_path": labels})
            schema_groups[aud.get("schema_id", "unknown")].append(date)
            rec["first_prefecture_row"] = first_data
            rec["prefecture_rows_detected"] = len(pref_rows)
            rec["column_count"] = len(columns)
            rec["status"] = "audited" if rec["sha256_match"] else "sha256_mismatch"
            wb.close()
        except Exception as exc:
            rec["status"] = "workbook_error"
            rec["error"] = repr(exc)
        per_snapshot.append(rec)
    summary = {
        "expected_downloaded": manifest.get("downloaded_count"),
        "processed": len(per_snapshot),
        "audited": sum(x["status"] == "audited" for x in per_snapshot),
        "sha256_mismatch": sum(x["status"] == "sha256_mismatch" for x in per_snapshot),
        "missing": sum(x["status"] == "file_missing" for x in per_snapshot),
        "prefecture_row_detection_errors": sum(x["status"] == "prefecture_row_detection_error" for x in per_snapshot),
        "workbook_errors": sum(x["status"] == "workbook_error" for x in per_snapshot),
        "schema_count": len(schema_groups),
        "candidate_header_signatures": len(aggregate)
    }
    now = datetime.now(timezone.utc)
    output = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "official_page": manifest.get("official_page"),
        "scope": "Date-specific header-path extraction and conservative label classification. No data normalization, imputation, aggregation or analytical concatenation.",
        "summary": summary,
        "schema_groups": [{"schema_id": k, "count": len(v), "first_date": min(v), "last_date": max(v), "dates": v} for k,v in sorted(schema_groups.items())],
        "candidate_variables": [
            {"candidate_concept": k[0], "exact_header_label": k[1], "date_count": len(v["dates"]),
             "first_date": min(v["dates"]), "last_date": max(v["dates"]), "dates": v["dates"],
             "column_occurrence_count": len(v["columns"]), "schema_ids": sorted({x["schema_id"] for x in v["columns"]}), "column_indices": sorted({x["column"] for x in v["columns"]}), "numeric_min": v.get("numeric_min"), "numeric_max": v.get("numeric_max"), "dash_count": v.get("dash_count", 0), "blank_count": v.get("blank_count", 0), "examples": v["examples"]}
            for k,v in sorted(aggregate.items(), key=lambda z:(z[0][0],z[0][1]))
        ],
        "snapshots": per_snapshot,
        "limitations": [
            "Candidate concept labels are rule-based and are not a final decision that two columns are longitudinally comparable.",
            "Header hierarchy is reconstructed from merged cells; visually formatted or implicit labels may need manual verification.",
            "Dash-like symbols are counted but not converted; their meaning remains date-, field- and prefecture-specific.",
            "No national aggregation, occupancy-rate recalculation, imputation, or MASTER/analysis dataset update was performed."
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created_at_jst": output["created_at_jst"], "summary": summary,
                      "schema_groups": output["schema_groups"]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

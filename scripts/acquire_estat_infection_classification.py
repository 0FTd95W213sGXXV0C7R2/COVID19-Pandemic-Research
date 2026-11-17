#!/usr/bin/env python3
"""Acquire e-Stat table 0003412006 as a separate classification audit; do not merge with A3."""
import csv, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TABLE_ID = "0003412006"
API = "https://api.e-stat.go.jp/rest/3.0/app/json"
OUT = Path("artifacts/a3_infection_classification")
OUT.mkdir(parents=True, exist_ok=True)
YEARS = {"2020000000": 2020, "2021000000": 2021, "2022000000": 2022,
         "2023000000": 2023, "2024000000": 2024}
MONTHS = {f"{m:02d}": m for m in range(1, 13)}
MONTH_CODES = {f"{m+10:05d}": m for m in range(1, 13)}  # e-Stat monthly codes 00110..00220

def fail(msg):
    raise RuntimeError(msg)

def save_json(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p

def api(name, params, raw_name):
    r = requests.get(f"{API}/{name}", params=params, timeout=(20, 120))
    r.raise_for_status()
    obj = r.json()
    save_json(raw_name, obj)
    root = "GET_META_INFO" if name == "getMetaInfo" else "GET_STATS_DATA"
    result = obj.get(root, {}).get("RESULT", {})
    if str(result.get("STATUS")) != "0":
        fail(f"{name} failed: {result}")
    return obj

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def main():
    app_id = os.environ.get("ESTAT_APP_ID", "").strip()
    if not app_id:
        fail("Missing ESTAT_APP_ID Actions secret.")
    now = datetime.now(timezone.utc)
    jst = now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat()
    meta = api("getMetaInfo", {"appId": app_id, "lang": "J", "statsDataId": TABLE_ID,
                               "explanationGetFlg": "Y"}, "metadata_raw.json")
    code_names = {}
    for d in walk(meta):
        code, name = d.get("@code"), d.get("@name")
        if code is not None and name is not None and "新型コロナ" in str(name):
            code_names[str(code)] = str(name)
    if not code_names:
        fail("No COVID-related classification codes found in metadata; inspect raw metadata.")
    base = {"appId": app_id, "lang": "J", "statsDataId": TABLE_ID,
            "metaGetFlg": "N", "cntGetFlg": "N", "limit": "100000"}
    obj = api("getStatsData", base, "full_table_raw.json")
    data = obj["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    rows = [data] if isinstance(data, dict) else data
    if not rows:
        fail("Full-table response has no observations.")
    # Table dimensions are month, infection classification, sex, and year.
    # Retain all COVID-related classifications separately; never add them together.
    output = []
    for row in rows:
        year = YEARS.get(str(row.get("@time", "")))
        cat = str(row.get("@cat02", ""))
        sex = str(row.get("@cat03", ""))
        month_code = str(row.get("@cat01", ""))
        if year is None or cat not in code_names or sex != "00100":
            continue
        month = MONTH_CODES.get(month_code)
        if month is None and month_code != "00100":
            continue
        value = str(row.get("$", "")).strip().replace(",", "")
        output.append({"year": year, "month": month if month is not None else "TOTAL",
                       "classification_code": cat, "classification_name": code_names[cat],
                       "value": value})
    if not output:
        # Dimension order can differ in a future API schema; preserve the raw files for diagnosis.
        fail("No candidate rows matched expected dimensions. Raw JSON preserved; inspect dimension codes.")
    csv_path = OUT / "covid_infection_classification_monthly_and_totals.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(output[0].keys()))
        w.writeheader()
        w.writerows(sorted(output, key=lambda x: (x["classification_code"], x["year"],
                                                   13 if x["month"] == "TOTAL" else x["month"])))
    summaries = {}
    for code in sorted(code_names):
        for year in sorted(set(x["year"] for x in output)):
            vals = [x for x in output if x["classification_code"] == code and x["year"] == year]
            months = [x for x in vals if x["month"] != "TOTAL"]
            totals = [x for x in vals if x["month"] == "TOTAL"]
            summaries[f"{code}:{year}"] = {
                "classification": code_names[code],
                "monthly_observation_count": len(months),
                "monthly_sum": sum(int(x["value"]) for x in months if x["value"].isdigit())
                               if all(x["value"].isdigit() for x in months) else None,
                "annual_total_rows": [x["value"] for x in totals],
                "monthly_values": [{"month": x["month"], "value": x["value"]} for x in months]
            }
    audit = {"table_id": TABLE_ID, "table_title": "感染症による死亡数，性・死因（感染症分類）・死亡月別",
             "retrieved_at_utc": now.isoformat(), "retrieved_at_jst": jst,
             "full_table_rows_returned": len(rows), "covid_classification_codes": code_names,
             "candidate_row_count": len(output), "summaries_by_code_and_year": summaries,
             "limitations": [
                 "This table uses Infectious Diseases Control Act classification, not the ICD underlying-cause classification.",
                 "COVID-related classifications are retained separately and are not added together.",
                 "A numerical match to annual underlying-cause totals does not establish indicator equivalence.",
                 "No values are imputed; raw API JSON is preserved unchanged.",
                 "This dataset is exploratory only and is not merged into A3."
             ]}
    (OUT / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    with (OUT / "SHA256SUMS.txt").open("w", encoding="utf-8") as f:
        for p in files:
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            f.write(f"{h}  {p.name}\n")
    print(f"PASS: downloaded {len(rows)} table rows; extracted {len(output)} candidate rows.")
    print(f"COVID classification codes: {json.dumps(code_names, ensure_ascii=False)}")
    print(f"Retrieved at JST: {jst}")
    print("A3 indicator equivalence is NOT established; do not merge this dataset.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

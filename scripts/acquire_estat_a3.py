#!/usr/bin/env python3
"""Acquire and audit e-Stat A3 monthly COVID-19 deaths. Requires ESTAT_APP_ID."""
import csv, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TABLE_ID = "0003411700"
API = "https://api.e-stat.go.jp/rest/3.0/app/json"
CAUSE, SEX, MONTH_TOTAL = "22201", "00100", "00100"
MONTHS = {"00110":1,"00120":2,"00130":3,"00140":4,"00150":5,"00160":6,
          "00170":7,"00180":8,"00190":9,"00200":10,"00210":11,"00220":12}
YEARS = {"2020000000":2020,"2021000000":2021,"2022000000":2022,"2023000000":2023}
MHLW_TOTALS = {2020:3466,2021:16766,2022:47638,2023:38086}
OUT = Path("artifacts/a3")
OUT.mkdir(parents=True, exist_ok=True)

def die(message):
    raise RuntimeError(message)

def get_api(name, params, raw_name=None):
    r = requests.get(f"{API}/{name}", params=params, timeout=(20,120))
    r.raise_for_status()
    try:
        obj = r.json()
    except ValueError:
        die(f"{name}: response is not JSON")
    if raw_name:
        save_json(raw_name, obj)
    root = "GET_META_INFO" if name == "getMetaInfo" else "GET_STATS_DATA"
    result = obj.get(root, {}).get("RESULT", {})
    if str(result.get("STATUS")) != "0":
        die(f"{name}: e-Stat error {result}; request_params={{{', '.join(f'{k}={v}' for k,v in params.items() if k!='appId')}}}")
    return obj

def get_values(obj):
    try:
        values = obj["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    except (KeyError, TypeError):
        die("API response lacks DATA_INF.VALUE")
    return [values] if isinstance(values, dict) else values

def save_json(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p

def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()

def parse_count(value, label):
    s = str(value).strip().replace(",", "")
    if not s or s in {"-", "－", "…", "x", "X"}:
        die(f"{label}: source value is missing/non-numeric ({value!r}); not replacing with zero")
    try:
        n = float(s)
    except ValueError:
        die(f"{label}: cannot parse {value!r}")
    if n < 0 or not n.is_integer():
        die(f"{label}: expected a non-negative integer, got {value!r}")
    return int(n)

def main():
    app_id = os.environ.get("ESTAT_APP_ID", "").strip()
    if not app_id:
        die("ESTAT_APP_ID secret is missing. Add repository Actions secret ESTAT_APP_ID.")
    retrieved = datetime.now(timezone.utc)
    retrieved_jst = retrieved.astimezone(ZoneInfo("Asia/Tokyo")).isoformat()

    meta = get_api("getMetaInfo", {"appId":app_id,"lang":"J","statsDataId":TABLE_ID,
                                   "explanationGetFlg":"Y"}, "estat_a3_metadata_raw.json")
    base = {"appId":app_id,"lang":"J","statsDataId":TABLE_ID,"metaGetFlg":"N",
            "cntGetFlg":"N","limit":"100000"}

    # The table metadata reports 53,352 observations, below the API's 100,000-row
    # response limit. Retrieve the table once without category/time filters, then
    # select the required dimensions locally. This avoids undocumented/fragile
    # interactions between cdTime and cdCat01 filters.
    all_obj = get_api("getStatsData", base, "estat_a3_full_table_raw.json")
    rows = get_values(all_obj)
    if not rows:
        die("Unfiltered e-Stat response contains no rows.")
    monthly, annual = {}, {}
    diagnostics = {"returned_rows":len(rows),"target_rows_by_year":{}}
    for row in rows:
        time_code = str(row.get("@time",""))
        cat01 = str(row.get("@cat01",""))
        cat02 = str(row.get("@cat02",""))
        cat03 = str(row.get("@cat03",""))
        year = YEARS.get(time_code)
        if year is None or cat02 != SEX or cat03 != CAUSE:
            continue
        if cat01 in MONTHS:
            key = (year, MONTHS[cat01])
            if key in monthly:
                die(f"Duplicate monthly row: {key}")
            monthly[key] = parse_count(row.get("$",""), str(key))
            diagnostics["target_rows_by_year"][str(year)] = diagnostics["target_rows_by_year"].get(str(year),0)+1
        elif cat01 == MONTH_TOTAL:
            if year in annual:
                die(f"Duplicate annual total: {year}")
            annual[year] = parse_count(row.get("$",""), f"annual total {year}")

    expected = {(y,m) for y in YEARS.values() for m in range(1,13)}
    if set(monthly) != expected:
        die(f"Expected 48 monthly values; missing={sorted(expected-set(monthly))}; extra={sorted(set(monthly)-expected)}; diagnostics={diagnostics}")
    if set(annual) != set(YEARS.values()):
        die(f"Expected annual totals for 2020-2023; received {sorted(annual)}; diagnostics={diagnostics}")

    checks = []
    for y in sorted(YEARS.values()):
        s = sum(monthly[y,m] for m in range(1,13))
        checks.append({"year":y,"monthly_sum":s,"e_stat_annual_total":annual[y],
                       "monthly_sum_matches_e_stat":s==annual[y],
                       "mhlw_annual_report_total":MHLW_TOTALS[y],
                       "e_stat_matches_mhlw_annual_report":annual[y]==MHLW_TOTALS[y]})
    if not all(x["monthly_sum_matches_e_stat"] and x["e_stat_matches_mhlw_annual_report"] for x in checks):
        die("Annual reconciliation failed. Raw API response is preserved; no values were altered.")

    csv_path = OUT / "a3_covid19_deaths_by_month_2020_2023.csv"
    with csv_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.writer(f)
        w.writerow(["year","month","deaths_persons","date_basis","cause_code","sex_code","stats_data_id"])
        for (y,m),v in sorted(monthly.items()):
            w.writerow([y,m,v,"month_of_death",CAUSE,SEX,TABLE_ID])

    audit = {"source":"e-Stat / Ministry of Health, Labour and Welfare","stats_data_id":TABLE_ID,
             "cause_code":CAUSE,"cause_label":"22201_新型コロナウイルス感染症","sex_code":SEX,
             "years":sorted(YEARS.values()),"observation_count":len(monthly),"unit":"persons",
             "time_basis":"month_of_death","retrieved_at_utc":retrieved.isoformat(),
             "retrieved_at_jst":retrieved_jst,"response_diagnostics":diagnostics,
             "annual_reconciliation":checks,"status":"PASS","raw_source_files":[
                 "estat_a3_metadata_raw.json","estat_a3_full_table_raw.json"],
             "notes":["Raw API JSON preserved unchanged.",
                      "The complete table was requested without category/time filters.",
                      "Required rows were selected locally using metadata codes.",
                      "Missing values are not converted to zero.",
                      "No legacy MASTER or derived data is read."]}
    (OUT/"a3_acquisition_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=["# A3 Monthly COVID-19 Deaths — Acquisition Report","",
            f"- Retrieved (JST): {retrieved_jst}",f"- e-Stat table ID: {TABLE_ID}",
            "- Time basis: month of death","- Cause: 22201_新型コロナウイルス感染症",
            "- Sex: total","- Expected observations: 48",f"- Acquired observations: {len(monthly)}",
            f"- Full table rows returned: {len(rows)}","",
            "| Year | Monthly sum | e-Stat annual total | MHLW annual report | Result |",
            "|---:|---:|---:|---:|---|"]
    for x in checks:
        report.append(f"| {x['year']} | {x['monthly_sum']} | {x['e_stat_annual_total']} | {x['mhlw_annual_report_total']} | PASS |")
    report += ["","Raw API JSON is preserved unchanged. No legacy MASTER is used.",""]
    (OUT/"A3_ACQUISITION_REPORT.md").write_text("\n".join(report),encoding="utf-8")
    files=[p for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="SHA256SUMS.txt"]
    (OUT/"SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files),encoding="utf-8")
    print(f"PASS: {len(monthly)} monthly observations; all annual checks passed.")
    print(f"Retrieved at JST: {retrieved_jst}")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr)
        sys.exit(1)

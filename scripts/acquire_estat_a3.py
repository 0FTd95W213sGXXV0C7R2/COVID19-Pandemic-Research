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

def get_api(name, params):
    r = requests.get(f"{API}/{name}", params=params, timeout=(20,120))
    r.raise_for_status()
    try:
        obj = r.json()
    except ValueError:
        die(f"{name}: response is not JSON")
    root = "GET_META_INFO" if name == "getMetaInfo" else "GET_STATS_DATA"
    result = obj.get(root, {}).get("RESULT", {})
    if str(result.get("STATUS")) != "0":
        die(f"{name}: e-Stat error {result}")
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
    meta = get_api("getMetaInfo", {"appId":app_id,"lang":"J","statsDataId":TABLE_ID,"explanationGetFlg":"Y"})
    meta_path = save_json("estat_a3_metadata_raw.json", meta)

    base = {"appId":app_id,"lang":"J","statsDataId":TABLE_ID,"metaGetFlg":"N","cntGetFlg":"N","limit":"100000"}
    monthly, annual = {}, {}
    raw_files = [meta_path.name]
    request_diagnostics = []

    # e-Stat API cdTime is a single-code filter. Query each year separately;
    # a comma-separated list was silently reduced to the final year in the
    # first run, despite being echoed in PARAMETER.
    for time_code, year in YEARS.items():
        common = {"cdTab":"10100","cdCat02":SEX,"cdCat03":CAUSE,"cdTime":time_code}
        month_obj = get_api("getStatsData", {**base,**common,"cdCat01":",".join(MONTHS)})
        month_path = save_json(f"estat_a3_monthly_raw_{year}.json", month_obj)
        raw_files.append(month_path.name)
        month_rows = get_values(month_obj)
        request_diagnostics.append({
            "year":year,"time_code":time_code,"request_type":"monthly",
            "returned_rows":len(month_rows),
            "returned_time_codes":sorted({str(x.get("@time","")) for x in month_rows})
        })
        for row in month_rows:
            yc, mc = str(row.get("@time","")), str(row.get("@cat01",""))
            if yc == time_code and mc in MONTHS and str(row.get("@cat02")) == SEX and str(row.get("@cat03")) == CAUSE:
                key = (year, MONTHS[mc])
                if key in monthly: die(f"Duplicate monthly row: {key}")
                monthly[key] = parse_count(row.get("$",""), str(key))

        total_obj = get_api("getStatsData", {**base,**common,"cdCat01":MONTH_TOTAL})
        total_path = save_json(f"estat_a3_annual_total_raw_{year}.json", total_obj)
        raw_files.append(total_path.name)
        total_rows = get_values(total_obj)
        request_diagnostics.append({
            "year":year,"time_code":time_code,"request_type":"annual_total",
            "returned_rows":len(total_rows),
            "returned_time_codes":sorted({str(x.get("@time","")) for x in total_rows})
        })
        for row in total_rows:
            if str(row.get("@time")) == time_code and str(row.get("@cat01")) == MONTH_TOTAL and str(row.get("@cat02")) == SEX and str(row.get("@cat03")) == CAUSE:
                if year in annual: die(f"Duplicate annual total: {year}")
                annual[year] = parse_count(row.get("$",""), f"annual total {year}")

    expected = {(y,m) for y in YEARS.values() for m in range(1,13)}
    if set(monthly) != expected:
        die(f"Expected 48 monthly values; missing={sorted(expected-set(monthly))}; extra={sorted(set(monthly)-expected)}; request_diagnostics={request_diagnostics}")
    if set(annual) != set(YEARS.values()):
        die(f"Expected annual table totals for 2020-2023; received {sorted(annual)}; request_diagnostics={request_diagnostics}")

    checks = []
    for y in sorted(YEARS.values()):
        s = sum(monthly[y,m] for m in range(1,13))
        checks.append({"year":y,"monthly_sum":s,"e_stat_annual_total":annual[y],
                       "monthly_sum_matches_e_stat":s==annual[y],
                       "mhlw_annual_report_total":MHLW_TOTALS[y],
                       "e_stat_matches_mhlw_annual_report":annual[y]==MHLW_TOTALS[y]})
    if not all(x["monthly_sum_matches_e_stat"] and x["e_stat_matches_mhlw_annual_report"] for x in checks):
        die("Annual reconciliation failed. Raw API responses are preserved; no values were altered.")

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
             "retrieved_at_jst":retrieved_jst,"request_diagnostics":request_diagnostics,
             "annual_reconciliation":checks,"status":"PASS","raw_source_files":raw_files,
             "notes":["Raw API JSON preserved unchanged.","Each cdTime year is requested separately.",
                      "Missing values are not converted to zero.","No legacy MASTER or derived data is read."]}
    audit_path=OUT/"a3_acquisition_audit.json"
    audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=["# A3 Monthly COVID-19 Deaths — Acquisition Report","",
            f"- Retrieved (JST): {retrieved_jst}",f"- e-Stat table ID: {TABLE_ID}",
            "- Time basis: month of death","- Cause: 22201_新型コロナウイルス感染症",
            "- Sex: total","- Expected observations: 48",f"- Acquired observations: {len(monthly)}","",
            "| Year | Monthly sum | e-Stat annual total | MHLW annual report | Result |",
            "|---:|---:|---:|---:|---|"]
    for x in checks:
        report.append(f"| {x['year']} | {x['monthly_sum']} | {x['e_stat_annual_total']} | {x['mhlw_annual_report_total']} | PASS |")
    report += ["","Raw API JSON is preserved unchanged. No legacy MASTER is used.",""]
    report_path=OUT/"A3_ACQUISITION_REPORT.md"
    report_path.write_text("\n".join(report),encoding="utf-8")
    files=[p for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="SHA256SUMS.txt"]
    (OUT/"SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files),encoding="utf-8")
    print(f"PASS: {len(monthly)} monthly observations; all annual checks passed.")
    print(f"Retrieved at JST: {retrieved_jst}")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr)
        sys.exit(1)

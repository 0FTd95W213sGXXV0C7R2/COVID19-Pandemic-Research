#!/usr/bin/env python3
"""Independently reconcile released rows, source hashes, and cohort identities."""
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/"data/audits/mhlw/resource_quality_20261126"
OUT = AUDIT/"resource_handoff"
META = ROOT/"data/metadata/rebuild_2026/scarce_resource/mhlw_resource_quality"
JST = ZoneInfo("Asia/Tokyo")


def rows(path):
    with (gzip.open if path.suffix==".gz" else open)(path,"rt",encoding="utf-8",newline="") as handle:
        yield from csv.DictReader(handle)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verification():
    start=datetime.now(JST)
    tests={}
    raw=list(rows(META/"raw_manifest.csv"))
    tests["all_556_original_hashes"]=len(raw)==556 and all(
        sha(ROOT/r["path"])==r["sha256"] and (ROOT/r["path"]).stat().st_size==int(r["bytes"]) for r in raw)
    pointer=json.loads((META/"active_crosswalk.json").read_text())
    tests["v3_registry_dependencies"]=pointer["release"]=="weekly_candidate_v3" and all(
        sha(ROOT/path)==digest for path,digest in pointer["sha256"].items())
    cross={r["variable_id"]:r for r in rows(ROOT/pointer["crosswalk"])}
    prior_held=list(rows(AUDIT/"final_resource_review/definition_notice_review.csv"))
    hold_ids={r["variable_id"] for r in prior_held if cross[r["variable_id"]]["analysis_gate"]=="hold"}
    region_holds={r["variable_id"] for r in prior_held if r["outcome"]!="hold" and r["concept"]=="total_severe_patients"}
    original_held={r["variable_id"] for r in prior_held if r["outcome"]=="hold"}
    source_path=ROOT/"data/processed/rebuild_2026/scarce_resource/mhlw_weekly_prefecture_long.csv"

    def source_key(row):
        return row["observation_date"],row["prefecture_code"],row["variable_id"]

    eligible={}
    for row in rows(source_path):
        definition=cross[row["variable_id"]]
        if (definition["source_system"]=="weekly" and definition["analysis_gate"] in {"descriptive","available_prefectures"}
                and definition["valid_from"]<=row["observation_date"]<=definition["valid_to"]
                and row["value_status"] in {"numeric","reported_zero"} and row["numeric_value"]!=""):
            eligible[source_key(row)]=row
    derived=list(rows(OUT/"weekly_excel_v3_analysis.csv.gz"))
    derived_keys=[source_key(r) for r in derived]
    tests["eligible_source_rows_match_exactly"]=set(derived_keys)==eligible.keys() and all(
        all(row[key]==value for key,value in eligible[source_key(row)].items()) for row in derived)
    tests["588_review_holds_excluded"]=len(hold_ids)==588 and not any(row["variable_id"] in hold_ids for row in derived)
    tests["all_weekly_analysis_holds_excluded"]=all(cross[r["variable_id"]]["analysis_gate"]!="hold" for r in derived)
    tests["regional_severity_not_assumed_equivalent"]=(len(region_holds)==79 and len(original_held)==509
        and region_holds|original_held==hold_ids and all(cross[key]["analysis_gate"]=="hold" for key in region_holds))
    official_notice=list(rows(AUDIT/"final_resource_review/supplemental_source_manifest.csv"))
    tests["regional_and_national_standard_evidence_traced"]={"tokyo_record","survey_oct","survey_may","survey_2022"} <= {
        r["id"] for r in official_notice if r["status"]=="downloaded"}
    tests["definition_id_preserved_without_merging"]=all(
        r["definition_id"]==cross[r["variable_id"]]["definition_id"] and r["definition_id"] and
        r["source_series"]=="mhlw_weekly_excel_v3" for r in derived) and (
        cross["2023-05-10:1:B"]["definition_id"]!=cross["2023-10-04:1:B"]["definition_id"])
    defined_keys=[(r["observation_date"],r["prefecture_code"],r["definition_id"]) for r in derived]
    tests["excel_source_and_series_observation_keys_unique"]=len(set(derived_keys))==len(set(defined_keys))==len(derived)
    tests["weekly_no_imputation"]=all(r["raw_value"]==r["numeric_value"] and
        ((float(r["numeric_value"])==0)==(r["value_status"]=="reported_zero")) for r in derived)

    reference={r["metric_id"] for r in rows(AUDIT/"final_resource_review/early_prefecture_series.csv") if r["series_use"]=="reference_page_hold"}
    pdf=list(rows(OUT/"early_pdf_numeric_extract.csv.gz"))
    pdf_keys={(r["metric_id"],r["prefecture_code"]) for r in pdf}
    pdf_origin=[r for r in rows(AUDIT/"final_resource_review/early_prefecture_series.csv")
                if r["metric_id"] not in reference and r["value_status"] in {"numeric","reported_zero","published_percent"} and r["numeric_value"]]
    tests["pdf_reference_exclusion_complete_and_exact"]=bool(reference) and not any(r["metric_id"] in reference for r in pdf) and pdf==pdf_origin
    tests["pdf_series_separate_and_duplicate_free"]=len(pdf_keys)==len(pdf) and all(
        r["excel_join_allowed"]=="false" and r["source_series"]=="mhlw_early_pdf_only" and r["observation_date"]<"2020-12-23" for r in pdf)

    facility=list(rows(OUT/"gmis_facility_snapshots.csv.gz"))
    facility_by_source=defaultdict(dict)
    for r in facility:
        facility_by_source[r["source_path"]][int(r["source_record"])]=r
    checks=0
    source_manifest=json.loads((ROOT/"data/metadata/mhlw/gmis_all_snapshots_manifest.json").read_text())["results"]
    matches=True
    for item in source_manifest:
        if item["status"]!="downloaded":
            continue
        with (ROOT/item["local_path"]).open(encoding=item["encoding"],newline="") as handle:
            table=list(csv.reader(handle))
        header_pos=item["header_line_1based"]
        fields=table[header_pos-1]
        index=facility_by_source[item["local_path"]]
        for record, values in enumerate(table[header_pos:],header_pos+1):
            if not any(v.strip() for v in values):
                continue
            origin=dict(zip(fields,values))
            row=index[record]
            pairs={"facility_id":"医療機関コード","report_status":"報告状況","raw_actual_date":"実績日","prefecture":"都道府県",
                   "secured_beds_raw":"確保病床数","immediate_beds_raw":item["immediate_bed_column"],"current_inpatients_raw":item["inpatient_column"]}
            matches &= all(row[d]==(origin[s].strip() if d=="facility_id" else origin.get(s,"")) for d,s in pairs.items())
            matches &= row["region_code"]==origin["都道府県番号"].strip().zfill(2)
            for column in ("secured_beds","immediate_beds","current_inpatients"):
                raw_number=row[column+"_raw"].strip().replace(",","")
                number=str(int(raw_number)) if re.fullmatch(r"-?\d+",raw_number) else ""
                matches &= row[column]==number
            matches &= (row["current_report"]=="1")== (row["report_status"]=="報告済み" and row["actual_date"]==row["snapshot_date"])
            matches &= (row["republished_prior"]=="1")== (row["report_status"]=="未報告" and
                any(row[f].strip() for f in ("secured_beds_raw","immediate_beds_raw","current_inpatients_raw")))
            checks+=1
    tests["gmis_facility_values_independently_reconciled"]=matches and checks==len(facility)==116214
    tests["gmis_unique_source_records_and_no_missing_id_panel"]=sum(map(len,facility_by_source.values()))==len(facility) and all(
        r["fixed_reporting_panel"]=="0" and r["matched_previous_current"]=="0" for r in facility if not r["facility_id"])
    membership=defaultdict(set)
    for row in facility:
        if row["facility_id"] and row["duplicate_facility_code"]=="0":
            membership[row["snapshot_date"]].add(row["facility_id"])
    snapshots=sorted(membership)
    expected_events=set()
    for left,right in zip(snapshots,snapshots[1:]):
        expected_events.update((right,left,"new_or_returning",code) for code in membership[right]-membership[left])
        expected_events.update((right,left,"no_longer_listed",code) for code in membership[left]-membership[right])
    event_rows=list(rows(OUT/"gmis_membership_events.csv"))
    event_keys={(row["snapshot_date"],row["previous_date"],row["event"],row["facility_id"]) for row in event_rows}
    tests["facility_turnover_codes_reconcile"]=event_keys==expected_events and len(event_keys)==len(event_rows)
    cohorts=list(rows(OUT/"gmis_prefecture_cohorts.csv"))
    tests["gmis_cohort_populations_and_missingness_declared"]=all(
        r["statewide_continuous_series"]=="false" and int(r["numeric_count"])<=int(r["rows"])
        and (r["numeric_sum"]=="" if int(r["numeric_count"])==0 else r["numeric_sum"]!="") for r in cohorts)
    available=Counter()
    for r in facility:
        if r["current_report"]=="1" and r["duplicate_facility_code"]=="0":
            available[r["snapshot_date"],r["region_code"],"all_current_report_rows"]+=1
        if r["fixed_reporting_panel"]=="1":
            available[r["snapshot_date"],r["region_code"],"fixed_reporters_within_regime"]+=1
    tests["gmis_current_and_fixed_populations_reconcile"]=all(
        available[r["snapshot_date"],r["region_code"],r["cohort"]]==int(r["rows"])
        for r in cohorts if not r["cohort"].startswith("matched"))

    vintages=list(rows(OUT/"gmis_critical_care_weekly_vintages.csv"))
    latest=list(rows(OUT/"gmis_critical_care_weekly_latest.csv"))
    manifests={r["url"]:r for r in rows(OUT/"critical_care_acquisition.csv")}
    tests["critical_care_unique_observation_vintages_and_latest_selection"]=(len({(r["week"],r["publication_date"]) for r in vintages})==len(vintages)
        and len({r["week"] for r in latest})==len(latest)
        and all(row==max((r for r in vintages if r["week"]==row["week"]),key=lambda r:r["publication_date"]) for row in latest)
        and all(manifests[r["url"]]["sha256"]==r["sha256"] for r in vintages))
    tests["critical_care_week_values_are_not_chart_estimates"]=all(
        r["page"].isdigit() and all(r[key].isdigit() for key in ("icu_current_patients_7d_average",
            "ecmo_or_ventilator_current_patients_7d_average","new_admissions_week_total")) for r in latest)

    report=dict(start_jst=start.isoformat(timespec="seconds"),end_jst=datetime.now(JST).isoformat(timespec="seconds"),
        original_files=len(raw),weekly_v3_rows=len(derived),early_pdf_rows=len(pdf),excluded_review_holds=len(hold_ids),
        all_weekly_hold_columns=sum(v["source_system"]=="weekly" and v["analysis_gate"]=="hold" for v in cross.values()),
        gmis_reconciled_rows=checks,critical_week_count=len(latest),tests=tests)
    (OUT/"independent_validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
    return all(tests.values())


if __name__=="__main__":
    raise SystemExit(0 if verification() else 1)

#!/usr/bin/env python3
"""Build separate G-MIS panels and v3-filtered research extracts."""
import csv
import gzip
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

from audit_mhlw_early_pdfs import AUDIT, now
from audit_mhlw_gmis_all_snapshots import MANIFEST, ROOT, decode_csv, find_header, parse_date, parse_int
from build_mhlw_current_metadata import load_active_crosswalk, analysis_allowed, sha

OUT = AUDIT / "resource_handoff"
EARLY = AUDIT / "final_resource_review/early_prefecture_series.csv"
WEEKLY = ROOT / "data/processed/rebuild_2026/scarce_resource/mhlw_weekly_prefecture_long.csv"
METRICS = ("secured_beds", "immediate_beds", "current_inpatients")


def read(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0])
    with path.open("wb") as binary:
        if path.suffix == ".gz":
            with gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as zipped:
                with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as stream:
                    emit(stream, fields, rows)
        else:
            with io.TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
                emit(stream, fields, rows)


def emit(stream, fields, rows):
    writer = csv.DictWriter(stream, fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def current(row):
    return row["report_status"] == "報告済み" and row["actual_date"] == row["snapshot_date"]


def read_gmis():
    items = json.loads(MANIFEST.read_text())["results"]
    snapshots = {}
    for item in sorted(items, key=lambda item: item["snapshot_date"]):
        if item["status"] != "downloaded":
            continue
        path = ROOT / item["local_path"]
        if sha(path) != item["sha256"]:
            raise ValueError(f"G-MIS input changed: {path}")
        _, source = decode_csv(path.read_bytes())
        head, columns = find_header(source)
        metric_columns = ("確保病床数", item["immediate_bed_column"], item["inpatient_column"])
        day = item["snapshot_date"]
        result = []
        for index, cells in enumerate(source[head+1:], head+2):
            if not any(value.strip() for value in cells):
                continue
            data = dict(zip(columns, cells))
            report = data.get("報告状況", "")
            region = data["都道府県番号"].strip()
            identifier = data["医療機関コード"].strip()
            raw_day = data["実績日"]
            actual = parse_date(raw_day) or ""
            raw = {metric: data.get(label, "") for metric, label in zip(METRICS, metric_columns)}
            row = dict(snapshot_date=day, actual_date=actual, raw_actual_date=raw_day, region_code=region.zfill(2),
                prefecture=data["都道府県"], facility_id=identifier, report_status=report,
                missing_facility_code=int(not identifier), republished_prior=int(report=="未報告" and any(v.strip() for v in raw.values())),
                source_path=item["local_path"], source_url=item["source_url"], source_record=index,
                capacity_regime="pre_oct2023" if day<"2023-10-01" else "post_oct2023")
            for metric, token in raw.items():
                row[metric+"_raw"] = token
                row[metric] = parse_int(token)
            result.append(row)
        if day in snapshots or len(result) != item["data_record_count"]:
            raise ValueError(f"Unexpected snapshot coverage: {day}")
        snapshots[day] = result
    return snapshots


def keyed(rows):
    keys = Counter(r["facility_id"] for r in rows if r["facility_id"])
    return {r["facility_id"]:r for r in rows if r["facility_id"] and keys[r["facility_id"]]==1}


def group(rows, field):
    result = defaultdict(list)
    for row in rows:
        result[row[field]].append(row)
    return result


def summaries(snapshots):
    frame, coverage, totals, changes = [], [], [], []
    previous, previous_day = {}, ""
    dated_keyed = {day:keyed(rows) for day,rows in snapshots.items()}
    regimes = group([dict(day=day, regime=rows[0]["capacity_regime"]) for day,rows in snapshots.items()], "regime")
    fixed = {}
    for regime, dates in regimes.items():
        lists = [dated_keyed[r["day"]] for r in dates]
        shared = set.intersection(*(set(index) for index in lists))
        fixed[regime] = {code for code in shared if all(current(index[code]) for index in lists)
                         and len({index[code]["region_code"] for index in lists})==1}
    for day, rows in snapshots.items():
        present = dated_keyed[day]
        counts = Counter(r["facility_id"] for r in rows if r["facility_id"])
        regime = rows[0]["capacity_regime"]
        compared = bool(previous_day) and regime==next(iter(previous.values()))["capacity_regime"] if previous else False
        if previous_day:
            for event, codes, source in (
                ("new_or_returning", present.keys()-previous.keys(), present),
                ("no_longer_listed", previous.keys()-present.keys(), previous),
            ):
                changes.extend(dict(snapshot_date=day,previous_date=previous_day,event=event,
                    facility_id=code,region_code=source[code]["region_code"]) for code in sorted(codes))
        shared = present.keys() & previous.keys()
        paired = {code for code in shared if compared and present[code]["region_code"]==previous[code]["region_code"]
                  and current(present[code]) and current(previous[code])}
        for row in rows:
            code = row["facility_id"]
            row["duplicate_facility_code"] = int(bool(code) and counts[code]>1)
            row["snapshot_membership"] = ("unidentified" if not code else "duplicate" if counts[code]>1
                else "first_snapshot" if not previous_day else "retained" if code in previous else "new_or_returning")
            row["current_report"] = int(current(row))
            row["fixed_reporting_panel"] = int(bool(code) and code in fixed[regime])
            row["matched_previous_current"] = int(bool(code) and code in paired)
            frame.append(row)
        all_reporting = [r for r in rows if current(r) and not r["duplicate_facility_code"]]
        cohorts = [("all_current_report_rows", day, all_reporting),
                   ("fixed_reporters_within_regime",day,[r for code,r in present.items() if code in fixed[regime]])]
        if compared:
            cohorts.extend([("matched_adjacent_previous",previous_day,[r for code,r in previous.items() if code in paired]),
                            ("matched_adjacent_current",day,[r for code,r in present.items() if code in paired])])
        for name, measured, members in cohorts:
            for region, local in sorted(group(members,"region_code").items()):
                for metric in METRICS:
                    values = [r[metric] for r in local if r[metric] is not None]
                    totals.append(dict(snapshot_date=measured,pair_end_date=day,regime=regime,cohort=name,
                        region_code=region,prefecture=local[0]["prefecture"],metric=metric,unit="人" if metric=="current_inpatients" else "床",
                        rows=len(local),unknown_facility_codes=sum(not r["facility_id"] for r in local),
                        numeric_count=len(values),published_zero_count=values.count(0),numeric_sum=sum(values) if values else "",
                        statewide_continuous_series="false"))
        coverage.append(dict(snapshot_date=day,previous_date=previous_day,capacity_regime=regime,rows=len(rows),
            reporting=len(all_reporting),not_reported=sum(r["report_status"]=="未報告" for r in rows),
            republished_prior=sum(r["republished_prior"] for r in rows),unknown_facility=sum(not r["facility_id"] for r in rows),
            wrong_or_blank_actual_date=sum(r["actual_date"]!=day for r in rows),
            duplicate_code_rows=sum(r["duplicate_facility_code"] for r in rows),
            newly_listed=len(present.keys()-previous.keys()) if previous_day else "",
            no_longer_listed=len(previous.keys()-present.keys()) if previous_day else "",
            matched_reporting=len(paired),fixed_reporting=len(fixed[regime])))
        previous, previous_day = present, day
    return frame, coverage, totals, changes


def main():
    OUT.mkdir(exist_ok=True)
    started = now()
    frame, coverage, totals, changes = summaries(read_gmis())
    write(OUT/"gmis_facility_snapshots.csv.gz",frame)
    write(OUT/"gmis_snapshot_coverage.csv",coverage)
    write(OUT/"gmis_prefecture_cohorts.csv",totals)
    write(OUT/"gmis_membership_events.csv",changes)
    crosswalk = load_active_crosswalk()
    series = []
    for row in read(WEEKLY):
        definition = crosswalk[row["variable_id"]]
        if analysis_allowed(definition,row["value_status"]):
            day = row["observation_date"]
            if not (definition["valid_from"]<=day<=definition["valid_to"]):
                raise ValueError(f"Date outside active definition: {row['variable_id']}")
            series.append(dict(**row,definition_id=definition["definition_id"],concept=definition["concept"],
                severity=definition["severity"],measurement_unit=definition["unit"],
                analysis_gate=definition["analysis_gate"],source_series="mhlw_weekly_excel_v3"))
    write(OUT/"weekly_excel_v3_analysis.csv.gz",series)
    early = [r for r in read(EARLY) if r["series_use"]=="pdf_only" and r["numeric_value"]
             and r["value_status"] in {"numeric","reported_zero","published_percent"}]
    write(OUT/"early_pdf_numeric_extract.csv.gz",early)
    result = dict(start_jst=started,end_jst=now(),facility_rows=len(frame),snapshot_count=len(coverage),
        nonreporting=sum(r["not_reported"] for r in coverage),republished_prior=sum(r["republished_prior"] for r in coverage),
        unidentified=sum(r["unknown_facility"] for r in coverage),cohort_rows=len(totals), membership_events=len(changes),
        weekly_excel_rows=len(series),early_pdf_rows=len(early))
    (OUT/"build_summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()

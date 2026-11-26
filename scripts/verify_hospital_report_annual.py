#!/usr/bin/env python3
"""Verify published CSV byte integrity and source-cell mapping without the builder."""
import calendar
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REL = Path('non_covid_access/hospital_report_2017_2024')
AUDIT = ROOT / 'data/audits' / REL
DATA = ROOT / 'data/processed' / REL


def read(path, mode=csv.DictReader, encoding='utf-8'):
    with path.open(encoding=encoding, newline='') as stream:
        return list(mode(stream))


def clean(value):
    return unicodedata.normalize('NFKC', value).strip()


def numbers(records):
    return [Decimal(r['numeric_value']) for r in records if r['numeric_value'] != '']


def main():
    sources = read(AUDIT / 'source_manifest.csv')
    source = {r['id']: r for r in sources}
    originals = {key: read(ROOT / record['saved_path'], csv.reader, 'cp932')
                 for key, record in source.items()}
    monthly = read(DATA / 'national_monthly.csv')
    annual = read(DATA / 'prefecture_annual.csv')
    derived = read(DATA / 'national_daily_means_derived.csv')
    checks = {}

    def record(name, condition, **details):
        checks[name] = {'status': 'pass' if condition else 'fail', **details}

    record('source_hash_and_size', len(source) == len(sources) and all(
        (p := ROOT / r['saved_path']).stat().st_size == int(r['bytes'])
        and hashlib.sha256(p.read_bytes()).hexdigest() == r['sha256'] for r in sources), files=len(sources))
    record('official_annual_metadata', all(r['official_metadata'] == 'verified' and
           r['edition'] == 'annual_release' and r['stat_code'] == '00450023' for r in sources))
    expected_cells = {}
    for sid, rows in originals.items():
        if source[sid]['grain'] == 'national':
            header = next(i for i, r in enumerate(rows) if len(r) > 13 and clean(r[-1]) == '12月')
            expected_cells.update({(sid, r+1, c+1): (f"{source[sid]['year']}-{int(clean(rows[header][c])[:-1]):02}", '全国')
                                   for r in range(header+1, len(rows)) if len(rows[r]) >= 14 and rows[r][0].strip()
                                   for c in range(2, 14)})
        else:
            start = next(i for i, r in enumerate(rows) if r and ''.join(r[0].split()) == '全国')
            expected_cells.update({(sid, r+1, c+1): (source[sid]['year'], ''.join(rows[r][0].split()))
                                   for r in range(start, start+48) for c in range(1, len(rows[r]))})
    emitted_cells = [(r['source_id'], int(r['source_row']), int(r['source_column'])) for r in monthly+annual]
    record('independent_cell_coverage', len(emitted_cells) == len(expected_cells) and set(emitted_cells) == expected_cells.keys(),
           cells=len(emitted_cells))
    mismatches = []
    for row, (key, r, c) in zip(monthly+annual, emitted_cells):
        cell = originals[key][r-1][c-1]
        normalized = clean(cell).replace(',', '')
        numeric = normalized if re.fullmatch(r'[0-9]+(\.[0-9]+)?', normalized) else ''
        if (cell != row['raw_value'] or numeric != row['numeric_value'] or
                (row['period'], row['geography']) != expected_cells.get((key, r, c)) or
                originals[key][r-1][0] != row['source_label']):
            mismatches.append((key, r, c))
    record('original_raw_and_numeric_no_imputation', not mismatches, mismatches=mismatches)
    dimensions = ('period', 'geography', 'metric', 'hospital', 'bed', 'reprint')
    keys = [tuple(row[col] for col in dimensions) for row in monthly+annual]
    duplicates = [k for k, n in Counter(keys).items() if n > 1]
    record('observation_keys', not duplicates, duplicates=duplicates[:20])
    months = {f'{year}-{month:02}' for year in range(2017, 2025) for month in range(1, 13)}
    totals = defaultdict(list)
    for r in monthly:
        if r['hospital'] == '総数' and r['bed'] == '全病床' and r['reprint'] == '0':
            totals[r['metric']].append(r)
    expected_metrics = {'inpatient_days', 'month_end_inpatients', 'admissions', 'discharges',
                        'outpatient_contacts', 'average_stay', 'month_end_bed_utilization', 'beds'}
    record('96_months_eight_published_series', set(totals) == expected_metrics and all(
        {r['period'] for r in records if r['numeric_value']} == months for records in totals.values()), months=len(months))
    input_by_pointer = {key: row for key, row in zip(emitted_cells, monthly+annual)}
    mean_keys = {(r['period'], r['metric']) for r in derived}
    record('derived_separation_and_calendar_formula', len(derived) == len(mean_keys)
           and mean_keys == {(m, k) for m in months for k in ('daily_mean_inpatients', 'daily_mean_outpatients')}
           and all(r['metric'] not in expected_metrics
                   and by_pointer['metric'] == ('inpatient_days' if r['metric'] == 'daily_mean_inpatients' else 'outpatient_contacts')
                   and by_pointer['period'] == r['period'] and by_pointer['hospital'] == '総数'
                   and by_pointer['bed'] == '全病床' and r['numerator_raw'] == by_pointer['raw_value']
                   and int(r['calendar_days']) == calendar.monthrange(*map(int, r['period'].split('-')))[1]
                   and abs(Decimal(r['numeric_value']) * int(r['calendar_days']) -
                           Decimal(r['numerator_raw'])) <= Decimal('0.000016')
                   for r in derived if (by_pointer := input_by_pointer[(r['source_id'], int(r['source_row']), int(r['source_column']))])),
           rows=len(derived))
    affected = [r for r in monthly if '療養病床' in r['bed'] or r['hospital'] == '療養病床及び一般病床のみの病院']
    discontinued = [r for r in monthly if r['bed'] == '介護療養病床' and r['period'] >= '2024-04']
    record('care_bed_boundary_and_nonapplicability', bool(discontinued) and all(
        r['comparison_segment'] == ('through_2024_03' if r['period'] < '2024-04' else 'from_2024_04')
        for r in affected) and all(r['value_status'] == 'not_applicable' and r['numeric_value'] == '' for r in discontinued),
        discontinued_cells=len(discontinued))
    additive = {'inpatient_days', 'admissions', 'discharges', 'outpatient_contacts'}
    cohort = defaultdict(list)
    for r in annual:
        if r['hospital'] == '総数' and r['bed'] == '全病床' and r['metric'] in additive:
            cohort[r['period'], r['metric']].append(r)
    comparisons = []
    for (year, metric), records in sorted(cohort.items()):
        country = numbers(r for r in records if r['geography'] == '全国')
        region = numbers(r for r in records if r['geography'] != '全国')
        month = numbers(r for r in totals[metric] if r['period'].startswith(year))
        status = 'pending' if (len(country), len(region), len(month)) != (1, 47, 12) else (
            'match' if country[0] == sum(region) == sum(month) else 'difference')
        comparisons.append(dict(year=year, metric=metric, prefecture_count=len(region), month_count=len(month),
                                national_annual=str(country[0]) if country else '',
                                prefecture_sum=str(sum(region)) if len(region) == 47 else '',
                                national_month_sum=str(sum(month)) if len(month) == 12 else '', status=status))
    with (AUDIT / 'annual_reconciliation.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, list(comparisons[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(comparisons)
    record('annual_national_prefecture_month_sum', len(comparisons) == 32
           and all(r['status'] == 'match' for r in comparisons), counts=dict(Counter(r['status'] for r in comparisons)))
    cohorts = defaultdict(dict)
    for r in monthly + annual:
        if (r['metric'] in additive | {'month_end_inpatients', 'beds', 'beds_june_end'} and
                r['reprint'] == '0' and r['bed'] == '全病床' and
                r['hospital'] in ('総数', '精神科病院', '一般病院')):
            cohorts[r['source_id'], r['period'], r['geography'], r['metric']][r['hospital']] = r
    complete = [items for items in cohorts.values() if len(items) == 3 and len(numbers(items.values())) == 3]
    differences = [items['総数'] for items in complete if
                   Decimal(items['総数']['numeric_value']) != sum(numbers([items['精神科病院'], items['一般病院']]))]
    june = {(row['period'][:4], row['hospital']): row['numeric_value'] for row in monthly
            if row['metric'] == 'beds' and row['period'].endswith('-06') and row['bed'] == '全病床'}
    june_rows = [row for row in annual if row['metric'] == 'beds_june_end'
                 and row['geography'] == '全国' and row['hospital'] in ('総数', '精神科病院', '一般病院')]
    record('june_beds_same_reference_date', len(june_rows) == 24 and all(
        row['numeric_value'] == june.get((row['period'], row['hospital']))
        for row in june_rows), compared=len(june_rows))
    record('additive_hospital_type_totals', bool(complete) and not differences, compared=len(complete),
           pending=len(cohorts)-len(complete), mismatches=differences[:10])
    checks['national_prefecture_monthly_reconciliation'] = {
        'status': 'not_tested', 'reason': 'Comparable monthly prefecture series was not acquired'}
    checks['nonadditive_region_reconciliation'] = {
        'status': 'not_applicable', 'reason': 'Rates and average lengths of stay cannot be summed'}
    summary = {'verified_at_jst': datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
               'checks': checks, 'rows': {'national_monthly': len(monthly), 'prefecture_annual': len(annual),
                                         'derived': len(derived)}}
    output = json.dumps(summary, ensure_ascii=False, indent=2)
    (AUDIT / 'verification.json').write_text(output+'\n', encoding='utf-8')
    print(output)
    return int(any(check['status'] == 'fail' for check in checks.values()))


if __name__ == '__main__':
    raise SystemExit(main())

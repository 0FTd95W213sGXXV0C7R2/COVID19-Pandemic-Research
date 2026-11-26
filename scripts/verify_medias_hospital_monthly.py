#!/usr/bin/env python3
"""Independently check files, original cells, coverage and reproducible arithmetic."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo
from zipfile import ZipFile
from xml.etree import ElementTree
import posixpath
import re

import xlrd

SCOPE = Path('non_covid_access/medias_hospital_monthly')
AUDIT = Path('data/audits') / SCOPE
OUT = Path('data/processed') / SCOPE


def records(path):
    with path.open(encoding='utf-8', newline='') as stream:
        yield from csv.DictReader(stream)


def workbook(filename):
    if filename.endswith('.xls'):
        excel = xlrd.open_workbook(filename)
        return lambda sheet, row, col: excel.sheet_by_name(sheet).cell_value(row-1, col-1), excel.release_resources
    archive = ZipFile(filename)
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    relation = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    links = {r.attrib['Id']:r.attrib['Target'] for r in ElementTree.fromstring(
        archive.read('xl/_rels/workbook.xml.rels'))}
    sheet_paths = {r.attrib['name']:links[r.attrib[relation]] for r in ElementTree.fromstring(
        archive.read('xl/workbook.xml')).iter(ns+'sheet')}
    def string(item):
        return ''.join(node.text or '' for node in item.iter(ns+'t'))
    shared = []
    if 'xl/sharedStrings.xml' in archive.namelist():
        shared = [string(item) for item in ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))]
    loaded = {}
    def lookup(sheet, row, column):
        if sheet not in loaded:
            target = sheet_paths[sheet]
            file = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            cells = {}
            for cell in ElementTree.fromstring(archive.read(file)).iter(ns+'c'):
                address = re.fullmatch(r'([A-Z]+)([0-9]+)', cell.attrib['r'])
                col = 0
                for digit in address[1]:
                    col = col * 26 + ord(digit) - 64
                value = cell.findtext(ns+'v')
                kind = cell.get('t', 'n')
                if kind == 's':
                    value = shared[int(value)]
                elif kind == 'inlineStr':
                    value = string(cell)
                elif kind == 'n' and value is not None:
                    value = float(value)
                cells[int(address[2]),col] = value
            loaded[sheet] = cells
        return loaded[sheet].get((row,column))
    return lookup, archive.close


def same(value, raw):
    if isinstance(value, (float, int)):
        try:
            return Decimal(str(value)) == Decimal(raw)
        except ArithmeticError:
            return False
    return ('' if value is None else str(value)) == raw


def main():
    checks = {}
    def save(name, ok, **details):
        checks[name] = dict(status='pass' if ok else 'fail', **details)

    sources = {r['local_path']: r for r in records(AUDIT/'source_manifest.csv') if r['local_path']}
    save('hash_and_size', all((p := Path(filename)).stat().st_size == int(r['bytes']) and
                             hashlib.sha256(p.read_bytes()).hexdigest() == r['sha256']
                             for filename,r in sources.items()), count=len(sources))
    h = list(records(OUT/'hospital_provisional.csv'))
    m = list(records(OUT/'medias_published.csv'))
    y = list(records(OUT/'medias_recomputed_yoy.csv'))
    mismatches, value_errors = [], 0
    for filename, group in groupby(sorted(h+m,key=lambda r:r['source']), key=lambda r:r['source']):
        get, close = workbook(filename)
        try:
            for r in group:
                original = get(r['sheet'],int(r['row']),int(r['column']))
                if not same(original,r['raw_value']):
                    mismatches.append((filename,r['sheet'],r['row'],r['column']))
                if r['value'] != (r['raw_value'] if isinstance(original,(float,int)) else ''):
                    value_errors += 1
        finally:
            close()
    save('original_cells', not mismatches, count=len(h)+len(m), mismatches=len(mismatches), sample=mismatches[:10])
    save('no_missing_value_imputation', not value_errors, errors=value_errors)
    keys = ('period','geography','series','metric','category')
    count = len({tuple(r[k] for k in keys) for r in h+m})
    save('unique_observations', count==len(h)+len(m), duplicates=len(h)+len(m)-count)
    cal = {f'{year}-{month:02}' for year in range(2017,2025) for month in range(1,13)}
    needed = {'inpatient_days','month_end_inpatients','admissions','discharges','beds',
              'outpatient_contacts','daily_mean_inpatients','daily_mean_outpatients',
              'month_end_bed_utilization','average_stay'}
    geos = set()
    covered = defaultdict(set)
    for r in h:
        if r['category']=='総数' and r['value'] and r['geography']!='全国':
            covered[r['period'],r['metric']].add(r['geography'])
            geos.add(r['geography'])
    save('hospital_96_months_47_prefectures_10_metrics', len(geos)==47 and set(covered)=={(d,t) for d in cal for t in needed}
         and all(len(g)==47 for g in covered.values()), combinations=len(covered), prefectures=len(geos))
    national = {(r['period'],r['metric'],r['category']):Decimal(r['value']) for r in m
                if r['series']=='national_level' and r['value']}
    published = {(r['period'],r['metric'],r['category']):Decimal(r['value']) for r in m
                 if r['series']=='national_published_yoy' and r['value']}
    save('medias_national_96_months', all({p for p,t,c in national if t==metric and c=='総計'}==cal
         for metric in ('cost','cost_per_day','visit_days')), months=len(cal))
    computed = 0
    baseline_mismatch = 0
    derived_error = 0
    deviations = []
    baselines = sorted((r for r in y if r['baseline_source']), key=lambda r:r['baseline_source'])
    for filename, group in groupby(baselines,key=lambda r:r['baseline_source']):
        get, close = workbook(filename)
        try:
            for r in group:
                cell = get(r['baseline_sheet'],int(r['baseline_row']),int(r['baseline_column']))
                if not same(cell,r['baseline']):
                    baseline_mismatch += 1
                key = (r['period'],r['metric'],r['category'])
                if r['recomputed_yoy']:
                    expected = 100 * (national[key] / Decimal(str(cell)) - 1)
                    actual = Decimal(r['recomputed_yoy'])
                    if abs(expected-actual)>Decimal('0.0000001'):
                        derived_error += 1
                    if abs(expected-published[key])>Decimal('0.05'):
                        deviations.append((key,float(expected-published[key]),r['edition_match']))
                    computed += 1
        finally:
            close()
    save('yoy_derived_arithmetic', not baseline_mismatch and not derived_error,
         verified=computed, uncomputed=len(y)-computed, distinct_baseline_sources=len({r['baseline_source'] for r in baselines}),
         discrepancies_over_005pp=len(deviations), discrepancy_examples=deviations[:8])
    components = ('医科入院','医科入院外','歯科','調剤','入院時食事療養等','訪問看護療養')
    additive = [abs(national[p,'cost','総計'] - sum(national[p,'cost',kind] for kind in components)) for p in cal]
    save('national_cost_components', max(additive) <= Decimal('0.000001'), months=len(additive),
         maximum_absolute_error_trillion_yen=str(max(additive)))
    ratios = [abs(10*national[p,'cost','総計']/national[p,'visit_days','総計'] -
                  national[p,'cost_per_day','総計']) for p in cal]
    save('national_cost_per_day', max(ratios) <= Decimal('0.000001'), months=len(ratios),
         maximum_absolute_error_thousand_yen=str(max(ratios)))
    hc = list(records(AUDIT/'hospital_edition_comparison.csv'))
    equal = Counter((r['comparison'], 'pending' if not r['difference'] else
                     'match' if Decimal(r['difference'])==0 else 'difference') for r in hc)
    h_totals = {(r['period'],r['geography'],r['metric']):Decimal(r['value'])
                for r in h if r['category']=='総数' and r['value']}
    compared = [r for r in hc if r['comparison']=='same_edition_47_prefectures_vs_national']
    save('hospital_additive_same_edition', len(compared)==576 and all(
        sum(h_totals[r['period'],geo,r['metric']] for geo in geos) ==
        h_totals[r['period'],'全国',r['metric']] for r in compared), comparisons=len(compared))
    counts = Counter(r['series'] for r in m)
    regional = defaultdict(set)
    for r in m:
        if r['series']=='regional_published_yoy' and r['geography']!='全国計' and r['category']=='総計' and r['value']:
            regional[r['period'],r['metric']].add(r['geography'])
    with (AUDIT/'coverage.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(['dataset','month','metric','covered_geographies','expected_geographies','status'])
        for month in sorted(cal):
            for metric in sorted(needed):
                n = len(covered[month,metric])
                writer.writerow(['hospital_provisional',month,metric,n,47,'complete' if n==47 else 'pending'])
            for metric in ('cost','visit_days','cost_per_day'):
                n = len(regional[month,metric])
                writer.writerow(['medias_regional_yoy',month,metric,n,47,'complete' if n==47 else 'missing_or_partial'])
    report = {'verified_jst':datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
              'checks':checks,'hospital_rows':len(h),'medias_rows':len(m),'medias_rows_by_series':dict(counts),
              'hospital_edition_comparisons':{f'{kind}/{status}':n for (kind,status),n in equal.items()},
              'medias_region_months':len({r['period'] for r in m if r['series']=='regional_published_yoy' and not r['period'].startswith('FY')})}
    (AUDIT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(any(v['status']=='fail' for v in checks.values()))


if __name__ == '__main__':
    raise SystemExit(main())

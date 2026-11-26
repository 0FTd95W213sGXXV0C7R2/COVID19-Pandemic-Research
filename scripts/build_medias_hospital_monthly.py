#!/usr/bin/env python3
"""Build separate MHLW hospital provisional and MEDIAS observation series."""
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl
import xlrd

REL = Path('non_covid_access/medias_hospital_monthly')
AUDIT = Path('data/audits') / REL
OUT = Path('data/processed') / REL
PRIOR = Path('data/processed/non_covid_access/hospital_report_2017_2024')
PERIODS = {f'{year}-{month:02}' for year in range(2017, 2025) for month in range(1, 13)}
HOSPITAL = {
    1: ('daily_mean_inpatients', '人/日'), 3: ('month_end_bed_utilization', '%'),
    4: ('average_stay', '日'), 5: ('inpatient_days', '人日'), 6: ('month_end_inpatients', '人'),
    7: ('beds', '床'), 8: ('admissions', '人'), 9: ('discharges', '人'),
}
FLOWS = {'inpatient_days', 'admissions', 'discharges', 'outpatient_contacts'}


def norm(value):
    return ''.join(unicodedata.normalize('NFKC', str(value or '')).split())


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def sheets(path, names):
    if path.suffix == '.xls':
        workbook = xlrd.open_workbook(path, on_demand=True)
        try:
            for name in workbook.sheet_names():
                if norm(name) in names:
                    sheet = workbook.sheet_by_name(name)
                    yield name, [sheet.row_values(i) for i in range(sheet.nrows)]
        finally:
            workbook.release_resources()
    else:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for name in workbook.sheetnames:
                if norm(name) in names:
                    yield name, list(workbook[name].values)
        finally:
            workbook.close()


def at(rows, row, col):
    return rows[row-1][col-1] if len(rows[row-1]) >= col else None


def item(src, name, rows, row, col, period, geo, series, metric, category, unit):
    raw = at(rows, row, col)
    text = norm(raw)
    numeric = raw if isinstance(raw, (float, int)) else ''
    state = ('reported_zero' if raw == 0 else 'numeric') if numeric != '' else (
        {'': 'blank', '-': 'dash', '−': 'dash', '・': 'not_applicable',
         '...': 'unknown_or_unpublished', '…': 'unknown_or_unpublished',
         'x': 'suppressed', 'X': 'suppressed'}.get(text, 'unclassified_symbol'))
    return dict(period=period, geography=geo, series=series, metric=metric, category=category,
                unit=unit, value=numeric, raw_value=raw if raw is not None else '', value_status=state,
                issue=src['issue'], source=src['local_path'], sheet=name, row=row, column=col)


def hospital(src):
    for name, rows in sheets(Path(src['local_path']), {f'参考表{i}' for i in range(1, 10)}):
        table = int(norm(name)[3:])
        start = next(i for i, row in enumerate(rows, 1) if len(row) > 1 and norm(row[1]) == '全国')
        for column in range(4, max(len(r) for r in rows[start-1:start+47])+1):
            header = next((norm(at(rows, r, column)) for r in (start-1, start-2)
                           if norm(at(rows, r, column))), '')
            if not header:
                continue
            if table == 2:
                metric, unit = ('daily_mean_outpatients', '人/日') if column < 7 else ('outpatient_contacts', '延人')
            else:
                metric, unit = HOSPITAL[table]
            for row in range(start, start+48):
                yield item(src, name, rows, row, column, src['issue'], norm(at(rows, row, 2)),
                           'hospital_provisional', metric, header, unit)


COST = ('総計','診療費','医科入院','医科入院外','歯科','調剤','入院時食事療養等','訪問看護療養')
DAYS = ('総計','診療費','医科入院','医科入院外','歯科','調剤','訪問看護療養')
DAILY = ('総計','医科入院','医科入院（食事等含む）','医科入院外','歯科','調剤','訪問看護療養','医科入院外＋調剤')
NATIONAL = {'3': ('cost', '兆円', COST), '4': ('visit_days', '億日', DAYS), '5': ('cost_per_day', '千円', DAILY)}
REGION = {'27': 'cost', '28': 'visit_days', '29': 'cost_per_day',
          '32': 'cost', '33': 'visit_days', '34': 'cost_per_day'}


def fiscal(era, year):
    return (1988 if era == '平成' else 2018) + (1 if year == '元' else int(year))


def medias_national(src, include_baseline=False, specialty_only=False):
    names = {'表3'} if specialty_only else set(NATIONAL) | {'表3'}
    for name, rows in sheets(Path(src['local_path']), names):
        if norm(name) == '表3':
            if include_baseline:
                continue
            fy = None
            for col in range(1, len(rows[10])+1):
                year = norm(at(rows, 8, col))
                era_header = norm(at(rows, 7, col))
                if re.fullmatch(r'[0-9]+年度|元年度', year):
                    fy = fiscal(norm(at(rows, 7, col)), year[:-2])
                elif match := re.fullmatch(r'(平成|令和)([0-9]+|元)年度', era_header or year):
                    fy = fiscal(*match.groups())
                month = re.fullmatch(r'(\d+)月', norm(at(rows, 11, col)))
                if month is None or not fy:
                    continue
                m = int(month[1])
                period = f'{fy+int(m<4)}-{m:02}'
                if period not in PERIODS:
                    continue
                for row in range(12, 42):
                    category = '医科診療所' if row < 15 else norm(at(rows, 13+3*((row-12)//3), 18))
                    metric = norm(at(rows, row, 20))
                    yield item(src, name, rows, row, col, period, '全国', 'specialty_published_yoy',
                               metric, category, '%')
            continue
        metric, unit, categories = NATIONAL[norm(name)]
        fy = None
        variant = 'national_level'
        for row in range(1, len(rows)+1):
            label = norm(at(rows, row, 5))
            if re.search(r'2-[123]-ii\.', label):
                variant = 'national_published_yoy'
            year = re.match(r'(平成|令和)(\d+|元)年度', label)
            if year:
                fy = fiscal(*year.groups())
            month = re.fullmatch(r'(\d+)月', norm(at(rows, row, 7)))
            if month is None or fy is None:
                continue
            m = int(month[1])
            period = f'{fy+int(m<4)}-{m:02}'
            if period not in PERIODS and not (include_baseline and '2016-01' <= period <= '2016-12'):
                continue
            for col, category in enumerate(categories, 8):
                yield item(src, name, rows, row, col, period, '全国', variant, metric, category,
                           unit if variant == 'national_level' else '%')


def medias_region(src):
    for name, rows in sheets(Path(src['local_path']), set(REGION)):
        metric = REGION[norm(name)]
        month_table = int(name) >= 32
        if not month_table and not src['issue'].endswith('-03'):
            continue
        if month_table:
            header = ' '.join(norm(v) for v in rows[5])
            match = re.search(r'(平成|令和)(\d+|元)年(度?)(\d+)月', header)
            if not match or len(re.findall(r'月', header)) != 1:
                continue
            era, year, is_fiscal, month = match.groups()
            m = int(month)
            period = f'{fiscal(era,year)+int(bool(is_fiscal) and m<4)}-{m:02}'
            if period not in PERIODS:
                continue
        else:
            period = f'FY{int(src["issue"][:4])-1}'
            if not any(re.search(r'4[～~]3月', norm(v)) for v in rows[5]):
                continue
        start = next(i for i, row in enumerate(rows, 1) if len(row) > 4 and norm(row[4]) == '全国計')
        for col in range(11, 20):
            label = ''.join(norm(at(rows, r, col)) for r in (start-2, start-1))
            if not label:
                continue
            for row in range(start, start+48):
                yield item(src, name, rows, row, col, period, norm(at(rows, row, 5)),
                           'regional_published_yoy', metric, label, '%')


def hospital_comparisons(hospital_rows):
    groups = defaultdict(list)
    for r in hospital_rows:
        if r['category'] == '総数' and r['metric'] in FLOWS | {'month_end_inpatients','beds'}:
            groups[r['period'], r['geography'], r['metric']].append(r)
    assert all(len(g) == 1 for g in groups.values())
    prelim = {k: v[0]['value'] for k, v in groups.items()}
    def total(keys):
        values = [prelim.get(key, '') for key in keys]
        return sum(values) if all(v != '' for v in values) else ''
    regions = sorted({geo for _, geo, _ in prelim} - {'全国'})
    def difference(period, geo, metric, earlier, later, kind):
        return dict(period=period, geography=geo, metric=metric, comparison=kind,
                    provisional=earlier, other_value=later,
                    difference=later-earlier if earlier != '' and later != '' else '',
                    status='comparable' if earlier != '' and later != '' else 'pending')
    for r in read(PRIOR/'national_monthly.csv'):
        metric, period = r['metric'], r['period']
        if r['hospital'] == '総数' and r['bed'] == '全病床' and not int(r['reprint']) and metric in FLOWS | {'month_end_inpatients','beds'}:
            published = float(r['numeric_value']) if r['numeric_value'] else ''
            yield difference(period, '全国', metric, prelim.get((period,'全国',metric),''),
                             published, 'national_month_preliminary_vs_annual_edition')
            yield difference(period, '全国', metric, total([(period,g,metric) for g in regions]),
                             prelim.get((period,'全国',metric),''), 'same_edition_47_prefectures_vs_national')
    for r in read(PRIOR/'prefecture_annual.csv'):
        metric, year, geo = r['metric'], r['period'], r['geography']
        if r['hospital'] != '総数' or r['bed'] != '全病床' or int(r['reprint']) or metric not in FLOWS | {'beds_june_end'}:
            continue
        months = [f'{year}-{m:02}' for m in range(1,13)]
        keys = [(m,geo,metric) for m in months] if metric in FLOWS else [(f'{year}-06',geo,'beds')]
        yield difference(year,geo,metric,total(keys),float(r['numeric_value']) if r['numeric_value'] else '',
                         'prefecture_annual_matched_scope')


def main():
    sources = [r for r in read(AUDIT/'source_manifest.csv') if r['status'] == '取得済']
    h = [r for s in sources if s['dataset']=='hospital' for r in hospital(s)]
    m_sources = [s for s in sources if s['dataset']=='medias']
    latest = next(s for s in m_sources if s['issue']=='2025-03')
    n = list(medias_national(latest))
    specialty_keys = {(r['period'], r['metric'], r['category']) for r in n if r['series']=='specialty_published_yoy'}
    december = next(s for s in m_sources if s['issue']=='2024-12')
    for r in medias_national(december, specialty_only=True):
        key = (r['period'],r['metric'],r['category'])
        if key not in specialty_keys:
            n.append(r)
            specialty_keys.add(key)
    regional_keys = {}
    for source in sorted(m_sources, key=lambda r: r['issue']):
        for r in medias_region(source):
            key = (r['period'], r['geography'], r['metric'], r['category'])
            regional_keys.setdefault(key, r)
    region = list(regional_keys.values())
    reference = {(r['period'],r['metric'],r['category']):r for r in medias_national(latest, True)
                 if r['series']=='national_level'}
    march_2017 = next(s for s in m_sources if s['issue']=='2017-03')
    for r in medias_national(march_2017, True):
        if r['series'] == 'national_level':
            reference.setdefault((r['period'],r['metric'],r['category']),r)
    derived = []
    for r in n:
        if r['series'] != 'national_published_yoy':
            continue
        period, metric, category = r['period'],r['metric'],r['category']
        before = f'{int(period[:4])-1}{period[4:]}'
        baseline = reference.get((before, metric, category),{})
        prior = baseline.get('value','')
        current = reference[period,metric,category]['value']
        value = (current/prior-1)*100 if current != '' and prior not in ('',0) else ''
        derived.append(dict(period=period,metric=metric,category=category,baseline_period=before,
                            current=current,baseline=prior,baseline_source=baseline.get('source',''),
                            baseline_sheet=baseline.get('sheet',''),baseline_row=baseline.get('row',''),
                            baseline_column=baseline.get('column',''),
                            edition_match='same' if baseline.get('source')==r['source'] else 'different_or_unavailable',
                            recomputed_yoy=value,published_yoy=r['value'],
                            difference_pp=value-r['value'] if value != '' and r['value'] != '' else ''))
    write(OUT/'hospital_provisional.csv', h)
    write(OUT/'medias_published.csv', n+region)
    write(OUT/'medias_recomputed_yoy.csv', derived)
    write(AUDIT/'hospital_edition_comparison.csv', hospital_comparisons(h))
    write(AUDIT/'quality_flags.csv', (r for r in h+n+region if r['value_status'] != 'numeric'))


if __name__ == '__main__':
    main()

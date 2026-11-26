#!/usr/bin/env python3
"""Build source-addressed Hospital Report data from annual-release CSVs."""
import calendar
import csv
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'hospital_report_2017_2024'
AUDIT = ROOT / 'data/audits/non_covid_access' / NAME
OUTPUT = ROOT / 'data/processed/non_covid_access' / NAME
PREFECTURES = '北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄'.split()
METRICS = {
    9: ('inpatient_days', '人日'), 10: ('month_end_inpatients', '人'),
    11: ('admissions', '入院件'), 12: ('discharges', '退院件'),
    13: ('outpatient_contacts', '延人'), 15: ('average_stay', '日'),
    16: ('month_end_bed_utilization', '%'), 17: ('beds', '床'),
    106: ('annual_bed_utilization', '%'), 107: ('beds_june_end', '床'),
}
SUPPORT = dict(zip(('在院患者延数', '新入院患者数', '退院患者数', '外来患者延数',
                    '月末病床利用率', '平均在院日数'), (9, 11, 12, 13, 16, 15)))
SYMBOLS = {'': 'blank', '-': 'nothing_to_count', '−': 'nothing_to_count',
           '…': 'unknown_or_unsuitable_for_publication', '...': 'unknown_or_unsuitable_for_publication',
           '・': 'not_applicable'}
LONG_STAY = '療養病床及び一般病床のみの病院'
REGIONAL = [('総数', '全病床'), ('精神科病院', '全病床'), ('一般病院', '全病床'),
            (LONG_STAY, '全病床'), ('その他の一般病院', '全病床'),
            *[('その他の一般病院', label) for label in
              ('精神病床', '感染症病床', '結核病床', '療養病床', '一般病床', '介護療養病床')],
            ('地域医療支援病院', '全病床')]


def norm(value):
    return unicodedata.normalize('NFKC', value).strip()


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def make_record(src, rows, r, c, period, geography, hospital, bed, reprint, table, label):
    metric, unit = METRICS[table]
    raw = rows[r][c]
    cleaned = norm(raw).replace(',', '')
    if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', cleaned):
        flag = ('rounded_or_printed_zero' if table in (16, 106) else 'reported_numeric_zero') if Decimal(cleaned) == 0 else 'numeric'
        value = cleaned
    else:
        # Use the published legends; unlisted marks remain unidentified.
        flag = SYMBOLS.get(cleaned, 'unclassified')
        value = ''
    transition = ('療養病床' in bed or hospital == LONG_STAY)
    if transition and period == '2024':
        segment = '2024_partial_care_year' if bed == '介護療養病床' else '2024_transition_year'
    elif transition:
        segment = 'through_2024_03' if period < '2024-04' else 'from_2024_04'
    else:
        segment = '2017_2024'
    grain = 'june_end_snapshot' if table == 107 else ('month' if len(period) == 7 else 'year')
    return dict(period=period, time_grain=grain, geography=geography, metric=metric, hospital=hospital, bed=bed,
                reprint=int(reprint), comparison_segment=segment, unit=unit, raw_value=raw,
                numeric_value=value, value_status=flag, covid_scope='all_reported_patients',
                source_id=src['id'], source_table=src['table_number'], source_row=r+1, source_column=c+1,
                source_label=label)


def monthly(src, rows, table):
    header = next(i for i, row in enumerate(rows) if len(row) >= 14 and norm(row[2]) == '1月')
    if [norm(x) for x in rows[header][2:14]] != [f'{m}月' for m in range(1, 13)]:
        raise ValueError(src['id'])
    for r, row in enumerate(rows[header+1:], header+1):
        if len(row) < 14 or not row[0].strip():
            continue
        raw = row[0]
        label = norm(raw)
        reprint = '(再掲)' in label or table == 14
        name = label.replace('(再掲)', '').strip()
        hospital, bed = '総数', '全病床'
        metric_table = table
        if table == 14:
            hospital = '地域医療支援病院'
            metric_table = SUPPORT[name.split('(')[0].strip()]
        elif name.endswith('病床'):
            bed = name
            if raw.startswith((' ', '　')):
                hospital = 'その他の一般病院'
        else:
            hospital = name
        for m in range(1, 13):
            yield make_record(src, rows, r, m+1, f"{src['year']}-{m:02}", '全国', hospital, bed, reprint, metric_table, raw)


def source_care_beds_absent(rows, start):
    return not any('介護療養病床' in str(row) for row in rows[:start])


def regional(src, rows, table):
    start = next(i for i, row in enumerate(rows) if row and ''.join(row[0].split()) == '全国')
    regions = ['全国', *PREFECTURES]
    dimensions = REGIONAL if table != 13 else REGIONAL[:3] + REGIONAL[-1:]
    if table == 107 and source_care_beds_absent(rows, start):
        dimensions = REGIONAL[:-2] + REGIONAL[-1:]
    for r, region in enumerate(regions, start):
        row = rows[r]
        if ''.join(row[0].split()) != region:
            raise ValueError((src['id'], region, row[0]))
        if len(row) != len(dimensions) + 1:
            raise ValueError((src['id'], r, len(row)))
        for c in range(1, len(row)):
            hospital, bed = dimensions[c-1]
            yield make_record(src, rows, r, c, src['year'], region, hospital, bed,
                              hospital == '地域医療支援病院' or (bed == '介護療養病床' and table not in (15, 106)),
                              table, row[0])


def main():
    with (AUDIT / 'source_manifest.csv').open(encoding='utf-8', newline='') as file:
        sources = list(csv.DictReader(file))
    national, prefectures, structure, flags, means = [], [], [], [], []
    coverage = []
    regional_metrics = {1: 9, 2: 11, 3: 12, 4: 13, 6: 106, 7: 107, 8: 15}
    for source in sources:
        if source['status'] != 'downloaded' or source['official_metadata'] != 'verified':
            raise ValueError(source['id'])
        with (ROOT / source['saved_path']).open(encoding='cp932', newline='') as file:
            rows = list(csv.reader(file))
        table = int(source['table_number'][1:])
        is_monthly = source['grain'] == 'national'
        records = list(monthly(source, rows, table) if is_monthly else regional(source, rows, regional_metrics[table]))
        (national if is_monthly else prefectures).extend(records)
        structure.append(dict(source_id=source['id'], table=source['table_number'], period=source['year'],
                              source_rows=len(rows), extracted_cells=len(records),
                              preamble=' | '.join(' / '.join(row) for row in rows[:records[0]['source_row']-1]).rstrip()))
        for position, row in enumerate(rows[:records[0]['source_row']-1], 1):
            note = row[0] if row else ''
            if '豪雨' in note and ('報告がなかった' in note or '報告のあった' in note):
                hiroshima = '広島県' in note
                coverage.append(dict(source_id=source['id'], source_row=position,
                                     period='2018-07/2018-08' if hiroshima else '2020-06/2020-07',
                                     prefecture='広島' if hiroshima else '熊本',
                                     flag='facility_not_reported' if hiroshima else 'facility_partially_reported',
                                     source_note=note.strip()))
        flags.extend(row for row in records if row['value_status'] != 'numeric')
    for row in national:
        if row['metric'] not in ('inpatient_days', 'outpatient_contacts') or row['hospital'] != '総数' or row['bed'] != '全病床' or row['reprint']:
            continue
        year, month = map(int, row['period'].split('-'))
        days = calendar.monthrange(year, month)[1]
        means.append(dict(period=row['period'], geography='全国',
                          metric={'inpatient_days': 'daily_mean_inpatients', 'outpatient_contacts': 'daily_mean_outpatients'}[row['metric']],
                          unit='人/日', numeric_value=str((Decimal(row['numeric_value']) / days).quantize(Decimal('0.000001')))
                          if row['numeric_value'] else '', calendar_days=days, numerator_raw=row['raw_value'],
                          comparison_segment=row['comparison_segment'], covid_scope=row['covid_scope'],
                          source_id=row['source_id'], source_row=row['source_row'], source_column=row['source_column']))
    write(OUTPUT / 'national_monthly.csv', national)
    write(OUTPUT / 'prefecture_annual.csv', prefectures)
    write(OUTPUT / 'national_daily_means_derived.csv', means)
    write(AUDIT / 'structural_audit.csv', structure)
    write(AUDIT / 'quality_flags.csv', flags)
    write(AUDIT / 'facility_coverage_flags.csv', coverage)


if __name__ == '__main__':
    main()

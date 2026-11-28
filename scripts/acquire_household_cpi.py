"""Preserve the eight e-Stat CSVs and check their original monthly axes."""
import argparse
import csv
import io
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from education_sources import acquire, now

ESTAT = 'https://www.e-stat.go.jp'
TERMS = ESTAT+'/terms-of-use'
HOUSEHOLD = '家計調査 長期時系列表 家計収支編 二人以上の世帯 '
CPI = '2020年基準消費者物価指数 長期時系列データ 品目別価格指数 全国 月次 '
SMALL = '1-1 品目分類（小分類まで）：支出金額・名目増減率・実質増減率（月） '
TABLES = {
    '000040270646': HOUSEHOLD+SMALL+'支出金額（2000年1月～）',
    '000040270647': HOUSEHOLD+SMALL+'名目増減率（2000年1月～）',
    '000040270648': HOUSEHOLD+SMALL+'実質増減率（2000年1月～）',
    '000040270649': HOUSEHOLD+'品目分類（全品目）（2015年改定）：支出金額（月） 支出金額（2015年1月～2019年12月）',
    '000040270650': HOUSEHOLD+'品目分類（全品目）（2020年改定）：支出金額（月） 支出金額（2020年1月～2024年12月）',
    '000032103842': CPI+'1 中分類指数（1970年1月～最新月）',
    '000032103844': CPI+'1 品目別価格指数（1970年1月～最新月）',
    '000032103846': CPI+'1 季節調整済指数（2010年1月～最新月）',
}
SOURCES = {f'{table}.csv': f'{ESTAT}/stat-search/file-download?statInfId={table}&fileKind=1'
           for table in TABLES}


def month_range(start, end):
    return [f'{y:04d}{m:02d}' for y in range(int(start[:4]),int(end[:4])+1)
            for m in range(1,13) if start <= f'{y:04d}{m:02d}' <= end]


def inspect(data, household, target):
    for encoding in ('utf-8-sig','cp932'):
        try:
            decoded = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('CSV encoding unsupported')
    rows = list(csv.reader(io.StringIO(decoded,newline=''),strict=True))
    if len(rows)<7 or len(rows[0])<2 or {len(row) for row in rows}!={len(rows[0])}:
        raise ValueError('CSV dimensions are inconsistent')
    if household:
        first = rows[3].index('品目分類')+1
        if rows[3][0]!='表側連番' or not rows[0][0].startswith('二人以上の世帯_'):
            raise ValueError('Unexpected household table title or header')
        year = None
        months = []
        for year_label, month_label in zip(rows[1][first:],rows[3][first:]):
            if year_label.strip():
                year = re.fullmatch(r'(\d{4})年',unicodedata.normalize('NFKC',year_label).strip())
            month = re.fullmatch(r'(0?[1-9]|1[0-2])月',unicodedata.normalize('NFKC',month_label).strip())
            if not year or not month:
                raise ValueError('Unrecognized household month header')
            months.append(f'{year[1]}{int(month[1]):02d}')
    else:
        if rows[0][0]!='類・品目' or rows[1][0]!='Group/Item':
            raise ValueError('Unexpected CPI table header')
        months = [row[0] for row in rows[6:]]
        if any(not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])',m) for m in months):
            raise ValueError('Invalid CPI month row')
    if not months or months!=month_range(months[0],months[-1]):
        raise ValueError('Month axis has a gap, repeated month or incorrect order')
    expected = month_range(*target)
    missing = sorted(set(expected)-set(months))
    if missing:
        raise ValueError(f'Required months absent: {missing}')
    return {'encoding':encoding,'csv_rows':len(rows),'csv_columns':len(rows[0]),
            'first_month':months[0],'last_month':months[-1],'source_months':len(months),
            'required_start':target[0],'required_end':target[1],'required_months_covered':len(expected),
            'integrity':'strict_csv_uniform_width_and_complete_month_axis'}


def run(cache):
    for row in acquire(cache,SOURCES):
        table = Path(row['filename']).stem
        household = table.startswith('000040')
        landing = f'{ESTAT}/stat-search/files?layout=dataset&stat_infid={table}'
        row.update(stat_inf_id=table,title=TABLES[table],publisher='総務省統計局',
                   official_listing_url=landing,direct_download_url=row['url'],
                   reuse_terms_url=TERMS)
        if row['status']!='acquired':
            yield row
            continue
        if table.endswith('0649'):
            target=('201501','201912')
        elif table.endswith('0650'):
            target=('202001','202412')
        else:
            target=('201701','202412')
        try:
            row.update(inspect((cache/row['filename']).read_bytes(),household,target))
            row['reuse_terms_status']='e-Stat利用規約確認済み。出典表示付きで統計CSV原本を収録'
            row['preserved_path']=(cache/row['filename']).as_posix()
        except (ValueError,csv.Error) as exc:
            row.update(status='verification_failed',reason=str(exc))
        yield row


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('cache',type=Path)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    if args.manifest.exists():
        parser.error('manifest exists; specify a new output path')
    records=list(run(args.cache))
    with args.manifest.open('x') as out:
        json.dump({'recorded_jst':now(),'counts':dict(Counter(r['status'] for r in records)),
                   'files':records},out,ensure_ascii=False,indent=2)
        out.write('\n')
    raise SystemExit(any(r['status']!='acquired' for r in records))

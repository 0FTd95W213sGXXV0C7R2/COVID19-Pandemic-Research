"""Build within-year DPC facility, medical area and procedure-group observations."""
import csv
import gzip
import re
import unicodedata
from collections import Counter
from pathlib import Path

import xlrd
from openpyxl import load_workbook

AUDIT = Path('data/audits/non_covid_access/ndb_open_data')
OUT = Path('data/processed/non_covid_access/ndb_open_data')
STROKE_AMI = {'010020','010030','010040','010060','050030'}


def clean(value):
    return ''.join(unicodedata.normalize('NFKC',str(value or '')).split())


def read_book(path):
    if path.endswith('.xlsx'):
        book = load_workbook(path,read_only=True,data_only=True)
        try:
            for sheet in book:
                yield sheet.title, list(sheet.values)
        finally:
            book.close()
    else:
        book = xlrd.open_workbook(path,on_demand=True)
        try:
            for sheet in book.sheets():
                yield sheet.name, [sheet.row_values(i) for i in range(sheet.nrows)]
        finally:
            book.release_resources()


def targets(title, rows):
    if '施設概要表' in title:
        headings = [clean(x) for x in rows[0]]
        if not any('施設名' in h for h in headings):
            return
        for ri,r in enumerate(rows[1:],2):
            if not re.fullmatch(r'\d{5}(?:\.0)?',clean(r[1])):
                continue
            for c,h in enumerate(headings):
                if '提出月数' in h or h.startswith(('病床総数','DPC算定病床数','病院類型','施設名','都道府県')):
                    yield ri,c,r[1],h,''
    elif '医療圏別MDC患者数' in title:
        for ri,r in enumerate(rows[2:],3):
            if not r[0] or not r[1]:
                continue
            for c,h in enumerate(rows[1]):
                if re.fullmatch(r'MDC\d{2}',clean(h)):
                    yield ri,c,f'{r[0]}:{r[1]}','退院件数',h
    elif '施設類型別' in title and '疾患別手術別集計' in title:
        if not rows[0] or '疾患コード' not in clean(rows[0][0]):
            return
        disease = ''
        measure = ''
        for ri,r in enumerate(rows[1:],2):
            disease = clean(r[0]) or disease
            measure = clean(r[2]) or measure
            surgery = clean(r[3])
            if (not re.fullmatch(r'\d{6}',disease) or not surgery or '再掲' in surgery
                    or measure not in ('件数','在院日数')):
                continue
            for c in range(4,len(rows[0]),2):
                if rows[0][c]:
                    yield ri,c,rows[0][c],measure,f'{disease}:{surgery}'
    elif '予定・救急医療入院' in title:
        if len(rows) < 4 or '通番' not in clean(rows[0][1]):
            return
        group = ''
        for c,h in enumerate(rows[2]):
            group = clean(rows[1][c]) or group
            if clean(h) not in {'予定入院','化学療法実施の再入院','予定外入院','救急医療入院'}:
                continue
            for ri,r in enumerate(rows[3:],4):
                if re.fullmatch(r'\d{5}(?:\.0)?',clean(r[1])):
                    yield ri,c,r[1],h,group


def main():
    with (AUDIT/'dpc_medias_manifest.csv').open(encoding='utf-8') as stream:
        sources = list(csv.DictReader(stream))
    counts = Counter()
    with gzip.open(OUT/'dpc_observations.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(['fiscal_year','source','table','sheet','row','column','entity','metric','group','raw','numeric','status'])
        for src in sources:
            path,title = src['path'],src['title']
            if src['dataset']!='dpc' or not path.endswith(('.xls','.xlsx')):
                continue
            if not any(label in title for label in ('施設概要表','医療圏別MDC患者数','施設類型別','予定・救急医療入院')):
                continue
            for name, rows in read_book(path):
                if not rows:
                    continue
                for row,col,entity,metric,group in targets(title,rows):
                    r = rows[row-1]
                    value = r[col] if col<len(r) else None
                    if value in ('',None):
                        state,number = 'blank',''
                    elif isinstance(value,(int,float)):
                        state,number = ('numeric_zero' if value==0 else 'numeric'),value
                    elif metric not in ('施設名','都道府県','病院類型') and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',clean(value)):
                        number = clean(value)
                        state = 'numeric_zero' if float(number)==0 else 'numeric'
                    elif clean(value) in ('-','‐','−'):
                        state,number = 'withheld_or_unavailable',''
                    else:
                        state,number = 'text',''
                    writer.writerow([src['period'],path,title,name,row,col+1,entity,metric,group,value,number,state])
                    counts[src['period'],title,state] += 1
    with (AUDIT/'dpc_coverage_flags.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(['year','table','status','rows'])
        writer.writerows((*key,n) for key,n in sorted(counts.items()))


if __name__=='__main__':
    main()

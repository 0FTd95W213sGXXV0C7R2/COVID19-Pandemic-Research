"""Audit bounded education tables and keep raw values and source coordinates."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

import openpyxl
import pdfplumber

from education_sources import now

PDF_TABLES = {2017:(83,10),2018:(81,9)}
CORE = ('enrollment','illness','economic','nonattendance','nonattendance_90_days',
        'nonattendance_0_to_10_attendance_days','nonattendance_0_attendance_days','other')


def pdf_rows(lines, width):
    records={}
    for line in lines:
        match=re.match(r'^\s*(?:(\d{1,2})\s+([^\d]+?)|()計)\s+([\d, ]+)$',line)
        if not match:
            continue
        vals=[int(v.replace(',','')) for v in match[4].split()]
        if len(vals)!=width:
            continue
        key=int(match[1]) if match[1] else 0
        if key in records:
            raise ValueError(f'duplicate prefecture code {key}')
        records[key]=(re.sub(r'\s','',match[2] or '全国'),vals)
    if set(records)!=set(range(48)):
        raise ValueError(f'incomplete prefecture table: {sorted(records)}')
    return records


def coordinate_lines(page):
    groups={}
    for word in page.extract_words(y_tolerance=2):
        y=round(word['top'],1)
        row=next((key for key in groups if abs(key-y)<2),y)
        groups.setdefault(row,[]).append(word)
    return [' '.join(w['text'] for w in sorted(words,key=lambda w:w['x0']))
            for words in groups.values()]


def absence(path,year):
    page,width=PDF_TABLES[year]
    layout=subprocess.check_output(['pdftotext','-layout','-f',str(page),'-l',str(page),str(path),'-'],text=True)
    if '①【合計（小・中）】' not in layout:
        raise ValueError('unexpected table')
    primary=pdf_rows(layout.splitlines(),width)
    with pdfplumber.open(path) as pdf:
        independent=pdf_rows(coordinate_lines(pdf.pages[page-1]),width)
    if primary!=independent:
        raise ValueError('PDF extractors disagree')
    for code,(name,vals) in primary.items():
        if sum(vals[i] for i in (1,2,3,7))!=vals[-1] or not 0<=vals[4]<=vals[3]<=vals[-1]<=vals[0]:
            raise ValueError((year,code,vals))
    if any(sum(row[1][i] for code,row in primary.items() if code)!=primary[0][1][i] for i in range(width)):
        raise ValueError('prefecture sums disagree with national totals')
    metrics=(*CORE,*(['other_with_nonattendance_factors'] if width==10 else []),'long_absence')
    return [dict(fiscal_year=year,prefecture_code=f'{code:02}',prefecture=name,school_scope='国公私立小・中合計',
                 metric=metric,value=v,unit='人',source_id=path.stem,locator=f'PDF p.{page} 表5-6 行{code or "計"} 列{i+1}')
            for code,(name,vals) in sorted(primary.items()) for i,(metric,v) in enumerate(zip(metrics,vals))]


def xlsx_first_sheet_values(path, sheet_number=1):
    ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(path) as book:
        strings = []
        if 'xl/sharedStrings.xml' in book.namelist():
            root = ElementTree.fromstring(book.read('xl/sharedStrings.xml'))
            strings = [''.join(t.text or '' for t in si.findall('.//s:t',ns)) for si in root]
        root = ElementTree.fromstring(book.read(f'xl/worksheets/sheet{sheet_number}.xml'))
    result = {}
    for cell in root.findall('.//s:sheetData/s:row/s:c',ns):
        kind = cell.get('t','n')
        raw = cell.findtext('s:v',namespaces=ns)
        if kind=='s':
            value = strings[int(raw)]
        elif kind=='inlineStr':
            value = ''.join(t.text or '' for t in cell.findall('.//s:t',ns))
        elif kind=='n':
            value = float(raw) if raw is not None else None
        else:
            value = raw
        result[cell.get('r')] = value
    return result


def ict(path):
    workbook=openpyxl.load_workbook(path,data_only=True)
    independent=xlsx_first_sheet_values(path)
    output=[]
    sheet=workbook.worksheets[0]
    if '都道府県別' not in sheet['B4'].value:
        raise ValueError('unexpected table')
    for row in range(6,54):
        region=str(sheet.cell(row,2).value).strip()
        for col in range(3,sheet.max_column+1):
            header=sheet.cell(4,col).value
            if not header:
                continue
            c=sheet.cell(row,col)
            if c.value!=independent.get(c.coordinate):
                raise ValueError(c.coordinate)
            value=c.value
            unit=sheet.cell(5,col).value
            if isinstance(value,(int,float)) and (value<0 or ('％' in str(unit) and value>100)):
                raise ValueError(c.coordinate)
            output.append(dict(region=region,school_scope=sheet['B2'].value,metric=header,unit=unit,
                               raw_value=value,cell_state='blank' if value is None else 'numeric' if isinstance(value,(int,float)) else 'source_symbol',
                               source_id=path.stem,sheet=sheet.title,cell=c.coordinate))
    workbook.close()
    return output


def save_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)


def run(cache,out,legacy):
    started=now()
    inventory=json.loads((out/'source_manifest.json').read_text())
    for r in inventory:
        if r['status']=='acquired' and hashlib.sha256((cache/r['filename']).read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError(r['filename'])
    rows=[r for year in PDF_TABLES for r in absence(cache/f'absence_{year}.pdf',year)]
    prior={int(r['fiscal_year']):int(r['count']) for r in csv.DictReader(legacy.open())}
    cross={r['fiscal_year']:{'previous':prior[r['fiscal_year']],'source':r['value'],
                            'match':prior[r['fiscal_year']]==r['value']}
           for r in rows if r['prefecture_code']=='00' and r['metric']=='long_absence'}
    details=[r for m in inventory if m['status']=='acquired' and m['filename'].startswith('ict_') for r in ict(cache/m['filename'])]
    for records,fields in ((rows,('fiscal_year','prefecture_code','metric')),(details,('source_id','sheet','cell'))):
        if len(records)!=len({tuple(r[k] for k in fields) for r in records}):
            raise ValueError('duplicate key')
    save_csv(out/'absence_2017_2018.csv',rows)
    if details:
        save_csv(out/'ict_first_sheet.csv',details)
    summary=dict(started_jst=started,finished_jst=now(),absence_rows=len(rows),
                 absence_coordinate_agreement=len(rows),legacy_national_comparison=cross,
                 ict_rows=len(details),ict_states=dict(Counter(r['cell_state'] for r in details)),
                 ict_check='openpyxl vs OOXML sheet1.xml and shared strings; second sheets not audited.')
    (out/'qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for field in ('cache','out','legacy'):
        p.add_argument(field,type=Path)
    a=p.parse_args()
    run(a.cache,a.out,a.legacy)

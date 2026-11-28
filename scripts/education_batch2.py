"""Recheck preserved sources and extract the education follow-up tables."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import openpyxl
import pdfplumber

from audit_education_sources import CORE, coordinate_lines, save_csv, xlsx_first_sheet_values
from education_sources import now

OLD = Path('data/audits/rebuild_2026/education_foundation_20261128')


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def nfk(text):
    return unicodedata.normalize('NFKC',text)


def text_pages(path):
    return nfk(subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)).split('\f')


def region_table(lines, width):
    """Preserve the number of columns, and reject repeated or missing regions."""
    pattern=r'^\s*(?:(\d{1,2})\s+([^\d]+?)|合?\s*計)\s+([\d,. ]+)$'
    rows={}
    for line in lines:
        m=re.match(pattern,nfk(line))
        if not m:
            continue
        vals=m[3].split()
        if len(vals)!=width:
            continue
        code=int(m[1]) if m[1] else 0
        if code in rows:
            raise ValueError(('duplicate region',code))
        rows[code]=(re.sub(r'\s','',m[2] or '全国'),tuple(Decimal(v.replace(',','')) for v in vals))
    if set(rows)!=set(range(48)):
        raise ValueError(('incomplete region table',sorted(rows)))
    return rows


MODERN_PAGES = {2019:81,2020:80,2021:81,2022:81,2023:83,2024:84}
SCHOOLS = ('elementary_junior_high','elementary','junior_high')
DIGITS_2024 = str.maketrans('㻜㻝㻞㻟㻠㻡㻢㻣㻤㻥㻘','0123456789,')


def panel(path, year, region_names=None):
    result=[]
    pages=text_pages(path)
    start=83 if year==2017 else 81
    width=10 if year==2017 else 9
    metrics=(*CORE,*(['other_with_nonattendance_factors'] if width==10 else []),'long_absence')
    specs=[(start+i,school,metrics) for i,school in enumerate(('elementary_junior_high','elementary','junior_high'))]
    specs.extend([(121 if year==2017 else 119,'highschool',('nonattendance','nonattendance_per_1000')),
                  (130 if year==2017 else 128,'highschool',('dropout_enrollment_april1','dropout_total','dropout_pct'))])
    if year in MODERN_PAGES:
        fields=list(CORE)
        if year in (2020,2021,2022):
            fields.insert(-1,'infection_avoidance')
        if year>=2023:
            fields.insert(4,'nonattendance_50_days')
        specs=[(MODERN_PAGES[year]+i,school,(*fields,'long_absence'))
               for i,school in enumerate(SCHOOLS)]
    def source_lines(lines):
        if year==2024:
            result=[]
            for line in lines:
                line=line.translate(DIGITS_2024)
                line=re.sub(r'\(cid:(1609[2-9]|1610[01]|16088)\)',
                            lambda m: ',' if m[1]=='16088' else str(int(m[1])-16092),line)
                tokens=line.split()
                if len(tokens)==len(fields)+2 and re.fullmatch(r'[0-4][0-9]',tokens[0]):
                    tokens[1]=region_names[int(tokens[0])] if region_names else '地域'
                    result.append(' '.join(tokens))
            return result
        return lines
    with pdfplumber.open(path) as pdf:
        for page,school,fields in specs:
            primary=region_table(source_lines(pages[page-1].splitlines()),len(fields))
            independent=region_table(source_lines(coordinate_lines(pdf.pages[page-1])),len(fields))
            if primary!=independent:
                raise ValueError(('reader disagreement',year,page))
            check_totals(primary,fields)
            for code,(name,values) in sorted(primary.items()):
                if region_names is not None:
                    expected_name=region_names[code]
                    if year!=2024 and code and name!=expected_name:
                        raise ValueError((year,code,name,expected_name))
                    name=expected_name
                for i,(metric,value) in enumerate(zip(fields,values),1):
                    unit='%' if metric.endswith('_pct') else 'per_1000' if metric.endswith('_per_1000') else 'persons'
                    result.append(dict(fiscal_year=year,prefecture_code=f'{code:02}',school_type=school,metric_id=metric,
                                       prefecture=name,value=value,unit=unit,value_type='published',
                                       source_id=path.stem,pdf_page=page,source_column=i))
    return result


def check_totals(rows, fields):
    for i,metric in enumerate(fields):
        if metric.endswith(('_pct','_per_1000')):
            continue
        if sum(values[i] for code,(_,values) in rows.items() if code)!=rows[0][1][i]:
            raise ValueError(('national sum',metric))


def rounding_matches(count, denominator, published, scale=100):
    if not denominator:
        return False
    rounded=(Decimal(count)*scale/Decimal(denominator)).quantize(
        Decimal('0.1'),rounding=ROUND_HALF_UP)
    return rounded==Decimal(published)


def continuation(path,year):
    pages=text_pages(path)
    result=[]
    for page,schools in ((100 if year==2017 else 98,SCHOOLS[1:]),
                         (110 if year==2017 else 108,('highschool',))):
        parts=pages[page-1].split('【合計】')[1:]
        if len(parts)!=len(schools):
            raise ValueError(('continuation header',year,page))
        for school,part in zip(schools,parts):
            vals=[]
            for prefix in (r'^\s*\(A\).*不登校',r'^\s*\(B\).*継続',r'^\s*比率'):
                line=next(line for line in part.splitlines() if re.search(prefix,line))
                vals.append(Decimal(line.split()[-1].replace(',','')))
            denominator,numerator,rate=vals
            if not rounding_matches(numerator,denominator,rate):
                raise ValueError(('continuation arithmetic',year,school))
            for metric,value,unit in zip(
                ('continuation_current_eligible','continued_nonattendance','continued_share_current_eligible_pct'),
                vals,('persons','persons','%')):
                result.append(dict(fiscal_year=year,prefecture_code='00',school_type=school,metric_id=metric,
                                   prefecture='全国',value=value,unit=unit,value_type='published',
                                   source_id=path.stem,pdf_page=page,source_column='計'))
    return result


LEGACY = Path('data/audits/rebuild_2026/economy_education_20261127')
LEGACY_FILES = {
    'nonattendance_reasons_2017_2024':('school_type','metric'),
    'long_absence_2017_2024_provisional':('school_scope','metric'),
    'support_2023_2024':('school_scope','metric'),
    'highschool_dropout_2017_2024':('metric',),
    'highschool_nonattendance_2017_2024':('metric',),
    'continuation_attendance_2019_2024':('school_type','metric'),
    'specialist_support_2019_2024_provisional':('metric',),
}


def legacy_audit(rows):
    national={(int(r['fiscal_year']),r['school_type'],r['metric_id']):r
              for r in rows if r['prefecture_code']=='00'}
    audit=[]
    for stem,dimensions in LEGACY_FILES.items():
        with (LEGACY/f'education_{stem}.csv').open(newline='') as handle:
            records=list(csv.DictReader(handle))
        keys=Counter(tuple(r[k] for k in ('fiscal_year',*dimensions)) for r in records)
        for i,r in enumerate(records,2):
            y=int(r['fiscal_year'])
            school=r.get('school_type',r.get('school_scope', {'highschool_dropout_2017_2024':'highschool','highschool_nonattendance_2017_2024':'highschool','specialist_support_2019_2024_provisional':'elementary_junior_high'}.get(stem,'')))
            school={'total':'elementary_junior_high','all':'elementary_junior_high'}.get(school,school)
            candidate=national.get((y,school,r['metric']))
            old=r.get('value',r.get('count',''))
            state='pending'
            if candidate and old and keys[tuple(r[k] for k in ('fiscal_year',*dimensions))]==1 and r.get('unit')==candidate['unit']:
                state='match' if Decimal(old)==candidate['value'] else 'difference'
            audit.append(dict(file=stem,row=i,fiscal_year=y,school_type=school,metric=r['metric'],
                              old_value=old,source_value=candidate['value'] if candidate else '',
                              source_id=candidate['source_id'] if candidate else '',
                              page=candidate['pdf_page'] if candidate else '',legacy_url=r['source_url'],
                              duplicate_key=keys[tuple(r[k] for k in ('fiscal_year',*dimensions))]>1,
                              status=state))
    return audit


def ict(path):
    workbook=openpyxl.load_workbook(path,data_only=True)
    all_rows=[]
    info=[]
    for number,s in enumerate(workbook.worksheets,1):
        raw=xlsx_first_sheet_values(path,number)
        cols=[c for c in range(3,s.max_column+1) if s.cell(4,c).value]
        for r in range(6,54):
            for col in cols:
                cell=s.cell(r,col)
                if cell.value!=raw.get(cell.coordinate):
                    raise ValueError((path,s.title,cell.coordinate))
                all_rows.append(dict(source_id=path.stem,sheet=s.title,cell=cell.coordinate,region=s.cell(r,2).value,
                                    metric=s.cell(4,col).value,unit=s.cell(5,col).value,value=cell.value,
                                    state='numeric' if isinstance(cell.value,(float,int)) else 'blank' if cell.value is None else 'source_symbol'))
        info.append(dict(sheet=s.title,number=number,merges=[str(m) for m in s.merged_cells.ranges],
                         headers=[list(r) for r in s.iter_rows(min_row=1,max_row=5,values_only=True)],
                         notes=[v for (v,) in s.iter_rows(min_row=54,min_col=2,max_col=2,values_only=True) if v]))
    workbook.close()
    return all_rows,info


def drive_check(paths, manifest):
    manifest=json.loads(manifest.read_text())
    result=[]
    for row in manifest:
        if row['status']!='acquired':
            continue
        name=row['filename']
        path=paths.get(name)
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None
        result.append(dict(filename=name,expected=row['sha256'],observed=digest,match=digest==row['sha256']))
    return result


def verify_annual(directory, manifest):
    records=json.loads(manifest.read_text())
    names=[r['filename'] for r in records]
    if len(names)!=14 or len(set(names))!=14 or any(r['status']!='acquired' for r in records):
        raise ValueError('Incomplete or duplicate annual manifest')
    if any(Path(n).name!=n for n in names):
        raise ValueError('Invalid manifest filename')
    if any(sum(n.startswith(f'index_{y}_') for n in names)!=1 for y in MODERN_PAGES):
        raise ValueError('Annual report coverage mismatch')
    paths={n:directory/n for n in names if (directory/n).is_file()}
    check=drive_check(paths,manifest)
    return check


def main():
    parser=argparse.ArgumentParser()
    for key in ('cache','paths','output','annual'):
        parser.add_argument(key,type=Path)
    parser.add_argument('--annual-manifest',type=Path,default=Path('data/audits/rebuild_2026/education_batch2_20261128/additional_manifest.json'))
    a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    check=drive_check(dict(json.loads(a.paths.read_text())),OLD/'source_manifest.json')
    dump(a.output/'drive_sha256.json',dict(verified_at_jst=now(),files=check))
    if not check or not all(r['match'] for r in check):
        raise ValueError('Preserved source hash verification failed; extraction stopped')
    annual_check=verify_annual(a.annual,a.annual_manifest)
    dump(a.output/'annual_sha256.json',dict(verified_at_jst=now(),files=annual_check))
    if not all(r['match'] for r in annual_check):
        raise ValueError('Annual source hash verification failed; extraction stopped')
    rows=[r for y in (2017,2018) for r in panel(a.cache/f'absence_{y}.pdf',y)]
    region_names={int(r['prefecture_code']):r['prefecture'] for r in rows if r['school_type']==SCHOOLS[0]}
    for year in MODERN_PAGES:
        path,=(a.annual/r['filename'] for r in annual_check if r['filename'].startswith(f'index_{year}_'))
        rows.extend(panel(path,year,region_names))
    for year in (2017,2018):
        rows.extend(continuation(a.cache/f'absence_{year}.pdf',year))
    legacy=legacy_audit(rows)
    save_csv(a.output/'legacy_record_audit.csv',legacy)
    key=lambda r: tuple(r[k] for k in ('fiscal_year','prefecture_code','school_type','metric_id'))
    if len({key(r) for r in rows})!=len(rows):
        raise ValueError('duplicate panel keys')
    save_csv(a.output/'prefecture_panel_2017_2024.csv',rows)
    ict_rows=[]
    info={}
    for p in sorted(a.cache.glob('ict_*.xlsx')):
        values,info[p.stem]=ict(p)
        ict_rows.extend(values)
    dump(a.output/'ict_structure.json',info)
    save_csv(a.output/'ict_all_sheets.csv',ict_rows)
    dump(a.output/'qa.json',dict(verified_at_jst=now(),drive_matches=sum(r['match'] for r in check),
                                panel_rows=len(rows),ict_rows=len(ict_rows),
                                legacy_states=Counter(r['status'] for r in legacy),
                                ict_states=Counter(r['state'] for r in ict_rows)))


if __name__=='__main__':
    main()

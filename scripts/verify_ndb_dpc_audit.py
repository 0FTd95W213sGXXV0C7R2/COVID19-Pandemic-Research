"""Verify source hashes, workbook cells, and disclosure constraints independently."""
import csv
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from verify_medias_hospital_monthly import workbook, same

AUDIT = Path('data/audits/non_covid_access/ndb_open_data')
DATA = Path('data/processed/non_covid_access/ndb_open_data')


def csv_rows(p):
    opener = gzip.open if p.suffix == '.gz' else open
    with opener(p,'rt',encoding='utf-8',newline='') as stream:
        yield from csv.DictReader(stream)


def audit_cells(path, expected_value, raw_name):
    stats = Counter()
    issues = []
    seen = set()
    years = set()
    numeric_groups = {}
    dims = set()
    with TemporaryDirectory() as directory:
        safe_copy = Path(directory)/'member.xlsx'
        for (source, member), group in groupby(csv_rows(path),lambda r:(r['source'],r.get('member',''))):
            input_path = source
            if member:
                with ZipFile(source) as archive:
                    safe_copy.write_bytes(archive.read(member))
                input_path = str(safe_copy)
            read, close = workbook(input_path)
            try:
                for r in group:
                    years.add(r['fiscal_year'])
                    stats['rows'] += 1
                    stats['state:'+r['status']] += 1
                    row, col = int(r['row']), int(r['column'])
                    cell = read(r['sheet'],row,col)
                    pointer = (source,member,r['sheet'],row,col)
                    if pointer in seen:
                        stats['repeated_pointers'] += 1
                    seen.add(pointer)
                    if not same(cell,r[raw_name]):
                        stats['raw_mismatches'] += 1
                        if len(issues)<8:
                            issues.append([pointer,str(cell),r[raw_name]])
                    if r['status'] in ('numeric','numeric_zero'):
                        if not r[expected_value] or float(r[expected_value]) != float(r[raw_name]):
                            stats['incorrect_numeric'] += 1
                    elif r[expected_value]:
                        stats['imputed'] += 1
                    if r.get('axis') == 'month':
                        key = (source, member,r['sheet'],row)
                        if key not in numeric_groups:
                            numeric_groups[key] = {}
                        dimension = r['dimension']
                        numeric_groups[key][dimension] = r[expected_value]
                        if re.fullmatch(r'\d{4}-\d{2}',dimension):
                            dims.add(dimension)
            finally:
                close()
    for values in numeric_groups.values():
        total = [v for k,v in values.items() if k.startswith('総計')]
        months = [v for k,v in values.items() if re.fullmatch(r'\d{4}-\d{2}',k)]
        if len(total)==1 and len(months)==12 and all(total+months):
            stats['month_sum_tested'] += 1
            if sum(int(float(v)) for v in months) != int(float(total[0])):
                stats['month_sum_difference'] += 1
        else:
            stats['month_sum_pending'] += 1
    return dict(stats), sorted(years), sorted(dims), issues


def main():
    manifests = [(AUDIT/'source_manifest.csv','saved_path'),(AUDIT/'dpc_medias_manifest.csv','path')]
    acquired = [(r[k],r) for p,k in manifests for r in csv_rows(p) if r['status']=='acquired']
    mismatch = [path for path,r in acquired if (p:=Path(path)).stat().st_size != int(r['size'])
                or hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256']]
    ndb, years, months, nissues = audit_cells(DATA/'claims_counts.csv.gz','count','raw_value')
    dpc, dyears, _, dissues = audit_cells(DATA/'dpc_observations.csv.gz','numeric','raw')
    medias = Counter()
    supplements = list(csv_rows(DATA/'medias_regional_supplement.csv'))
    for source, rows in groupby(sorted(supplements,key=lambda r:r['source']),lambda r:r['source']):
        read, close = workbook(source)
        try:
            for r in rows:
                medias['rows'] += 1
                if not same(read(r['sheet'],int(r['row']),int(r['column'])),r['raw_value']):
                    medias['raw_mismatches'] += 1
        finally:
            close()
    prior_raw = Path('data/raw/non_covid_access/medias_hospital_monthly')
    for year in ('2018','2020'):
        pdf = prior_raw/f'medias_{year}_03_pdf.pdf'
        content = subprocess.check_output(['pdftotext','-layout',str(pdf),'-'],text=True)
        for letter, metric in zip('abc',('cost','visit_days','cost_per_day')):
            table = next(page for page in content.split('\f')
                         if re.search(rf'5-2-{letter}\..*対前年同月比',page))
            line = next(line for line in table.splitlines() if line.strip().startswith('全国計'))
            match = re.match(r'全国計\s*(▲\s*)?([0-9]+\.[0-9]+)',line.strip())
            text_value = float(match[2])*(-1 if match[1] else 1)
            published = next(r for r in supplements if r['period']==year+'-03' and r['metric']==metric
                             and r['geography']=='全国計' and r['category']=='総計')
            medias['pdf_national_cells'] += 1
            if abs(text_value-float(published['value'])) > 0.0500001:
                medias['pdf_mismatches'] += 1
    fatal = ('raw_mismatches','repeated_pointers','incorrect_numeric','imputed')
    valid = (not medias.get('pdf_mismatches') and not medias.get('raw_mismatches') and not mismatch and not any(table.get(k,0) for k in fatal for table in (ndb,dpc))
             and set(years)>=set(str(y) for y in range(2017,2025))
             and set(dyears)==set(str(y) for y in range(2017,2025)))
    record = dict(verified_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                  status='pass' if valid else 'fail', hashes_tested=len(acquired), hash_mismatches=mismatch,
                  ndb=dict(counts=ndb,fiscal_years=years,months=months,examples=nissues),
                  medias=dict(medias),
                  dpc=dict(counts=dpc,fiscal_years=dyears,examples=dissues),
                  comparison_limits=['DPC facility/type definitions differ across years',
                                     'Suppressed inputs are never used to evaluate sums'])
    (AUDIT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))
    return int(not valid)


if __name__=='__main__':
    raise SystemExit(main())

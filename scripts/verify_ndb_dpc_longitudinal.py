"""Independently check original cells, hashes and cohort boundaries."""
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

REL = Path('non_covid_access/ndb_dpc_longitudinal')
AUDIT = Path('data/audits')/REL
OUT = Path('data/processed')/REL
OLD = AUDIT.parent/'ndb_open_data'
BASE = '84a9b765a05099033e2d27e7fe965876475da525'


def read(path):
    op = gzip.open if path.suffix=='.gz' else open
    with op(path,'rt',encoding='utf-8',newline='') as f:
        yield from csv.DictReader(f)


def check_cells(rows, raw, numeric, kind):
    counts = Counter()
    keys = set()
    examples = []
    with TemporaryDirectory() as tmp:
        for (source,member), group in groupby(rows,lambda r:(r['source'],r.get('member',''))):
            path=source
            if member:
                with ZipFile(source) as z:
                    path=str(Path(tmp)/'source.xlsx')
                    Path(path).write_bytes(z.read(member))
            get,close=workbook(path)
            try:
                for r in group:
                    row,col=int(r['row']),int(r['column'])
                    cell=get(r['sheet'],row,col)
                    counts['rows']+=1
                    if not same(cell,r[raw]):
                        counts['cell_errors']+=1
                        if len(examples)<4:
                            examples.append([source,r['sheet'],row,col,cell,r[raw]])
                    if isinstance(cell,(int,float)):
                        if not r[numeric] or float(r[numeric])!=cell:
                            counts['numeric_errors']+=1
                    elif r[numeric]:
                        counts['imputed']+=1
                    if kind=='dpc':
                        key=(r['fiscal_year'],r['table'],r['entity'],r['disease_code'],r['surgery'],r['metric'])
                        counts['scope_errors'] += int('再掲' in r['surgery'] or r['comparison_segment']!='FY'+r['fiscal_year'])
                    else:
                        key=(r['period'],r['code'],r['payer_series'])
                        excluded=r['payer_series']=='excludes_public_only'
                        period=r['period']
                        counts['scope_errors']+=int(
                            excluded==(r['source_scope']=='public_funding_included')
                            or (r['fiscal_year']=='2023' and excluded and 'r10_excluded.zip' not in source)
                            or (kind=='month' and not ('2019-04'<=period<='2024-12' and re.fullmatch(r'\d{4}-\d{2}',period)))
                            or (kind=='fiscal_year' and period!=r['fiscal_year']))
                    if key in keys:
                        counts['semantic_duplicates']+=1
                    keys.add(key)
            finally:
                close()
    return dict(counts),examples


def main():
    changed=subprocess.check_output(['git','show','--format=','--name-status',BASE],text=True).splitlines()
    missing=[line.split('\t')[-1] for line in changed if not Path(line.split('\t')[-1]).exists()]
    historic=subprocess.check_output(['git','diff','--name-only',BASE,'--','data/raw','data/processed','data/audits'],text=True).splitlines()
    altered=[p for p in historic if '/ndb_dpc_longitudinal/' not in p]
    hashes=[]
    for p,key in [(OLD/'source_manifest.csv','saved_path'),(OLD/'dpc_medias_manifest.csv','path'),
                  (AUDIT/'source_manifest.csv','path')]:
        hashes.extend((r[key],r['sha256']) for r in read(p) if r['status']=='acquired')
    bad=[path for path,expected in hashes if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected]
    result={}
    examples={}
    for kind,path,raw,numeric in [('fiscal_year','ndb_fiscal_year.csv','raw_value','count'),
                                 ('month','ndb_month.csv','raw_value','count'),
                                 ('dpc','dpc_annual_detail.csv.gz','raw_value','value')]:
        rows=read(OUT/path)
        if kind!='dpc':
            rows=sorted(rows,key=lambda r:(r['source'],r['member']))
        result[kind],examples[kind]=check_cells(rows,raw,numeric,kind)
    definitions=0
    mapping_errors=0
    for source, rows in groupby(read(AUDIT/'disease_definitions.csv'),lambda r:r['source']):
        get,close=workbook(source)
        try:
            for r in rows:
                row=int(r['row'])
                prefix=''.join(str(get(r['sheet'],row,col)) for col in (1,2))
                icd=str(get(r['sheet'],row,4))
                if (prefix,icd)!=(r['dpc6'],r['icd10']):
                    mapping_errors+=1
                definitions+=1
        finally:
            close()
    facilities=list(read(AUDIT/'facility_correspondence.csv'))
    facility_errors=sum(r['linkage_status']!='within_year_only' or bool(r['external_facility_code']) for r in facilities)
    blockers=('cell_errors','numeric_errors','imputed','scope_errors','semantic_duplicates')
    ok=not(bad or missing or altered or mapping_errors or facility_errors or any(
        r.get(k,0) for r in result.values() for k in blockers))
    record=dict(status='pass' if ok else 'fail',verified_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                prior_changed_files=len(changed),missing_prior=missing,altered_prior_data=altered,hashes=len(hashes),
                hash_errors=bad,series=result,examples=examples,disease_definition_rows=definitions,
                mapping_errors=mapping_errors,facility_rows=len(facilities),facility_errors=facility_errors,
                fixed_cohorts='not_constructed',additivity='not_tested_across_surgery_or_disclosure_groups')
    (AUDIT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))
    return int(not ok)


if __name__=='__main__':
    raise SystemExit(main())

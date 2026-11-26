"""Check published annual/month additivity and preserve pending facility links."""
import csv
import json
from collections import defaultdict
from itertools import groupby
from pathlib import Path

from verify_medias_hospital_monthly import workbook, same

REL = Path('non_covid_access/ndb_dpc_longitudinal')
AUDIT = Path('data/audits') / REL
DATA = Path('data/processed') / REL


def read(path):
    with path.open(encoding='utf8',newline='') as f:
        yield from csv.DictReader(f)


def main():
    annual={(r['fiscal_year'],r['code'],r['payer_series']):r['count']
            for r in read(DATA/'ndb_fiscal_year.csv')}
    months=defaultdict(dict)
    for r in read(DATA/'ndb_month.csv'):
        months[r['fiscal_year'],r['code'],r['payer_series']][r['period']]=r['count']
    cleared=0
    differences=[]
    pending=0
    for key,total in annual.items():
        values=months[key]
        year=int(key[0])
        expected={f'{year+(m<4)}-{m:02}' for m in range(1,13)}
        if values.keys()!=expected or not total or not all(values.values()):
            pending+=1
            continue
        if int(float(total))!=sum(int(float(v)) for v in values.values()):
            differences.append(key)
        cleared+=1
    roster=list(read(AUDIT/'facility_correspondence.csv'))
    source_errors=0
    anchor=set()
    for source, rows in groupby(roster,lambda r:r['source']):
        get,close=workbook(source)
        try:
            for r in rows:
                row=int(r['row'])
                cols=('public_notice_id','local_id','municipality','prefecture','name')
                source_errors+=sum(not same(get(r['sheet'],row,c),r[k]) for c,k in enumerate(cols,1))
                anchor.add((r['fiscal_year'],r['local_id'],r['municipality'],r['name'],r['source']))
        finally:
            close()
    invalid=0
    matched=0
    for r in read(AUDIT/'facility_linkage_candidates.csv'):
        matched+=1
        for side in ('before','after'):
            key=(r[side+'_year'],r[side+'_local_id'],r['municipality'],r['exact_name'],r[side+'_source'])
            invalid+=int(key not in anchor)
        invalid+=int(r['decision']!='pending_external_facility_code')
    result=dict(status='pass' if not(differences or invalid or source_errors) else 'fail',
                ndb_additive_comparisons=cleared,ndb_pending=pending,ndb_differences=differences,
                dpc_roster_source_errors=source_errors,dpc_pending_pairs_checked=matched,
                dpc_invalid_pairs=invalid)
    (AUDIT/'linkage_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(result)
    return int(result['status']=='fail')


if __name__=='__main__':
    raise SystemExit(main())

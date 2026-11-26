"""Recover original MEDIAS regional observations from previously missed XLSM links."""
import csv
from pathlib import Path
from collections import Counter

from build_medias_hospital_monthly import medias_region

AUDIT = Path('data/audits/non_covid_access/ndb_open_data')
PREVIOUS = Path('data/processed/non_covid_access/medias_hospital_monthly/medias_published.csv')
OUTPUT = Path('data/processed/non_covid_access/ndb_open_data')


def main():
    with PREVIOUS.open(encoding='utf-8') as stream:
        prior = list(csv.DictReader(stream))
    with (AUDIT/'dpc_medias_manifest.csv').open(encoding='utf-8') as stream:
        sources = [r for r in csv.DictReader(stream) if r['path'].endswith('.xlsm')]
    key = lambda r: (r['period'],r['metric'],r['geography'],r['category'])
    old = {key(r) for r in prior if r['series']=='regional_published_yoy'}
    added = []
    for r in sources:
        for value in medias_region({'issue':r['period'],'local_path':r['path']}):
            identity = key(value)
            if identity not in old:
                old.add(identity)
                added.append(value)
    with (OUTPUT/'medias_regional_supplement.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,list(added[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(added)
    months = Counter((r['period'],r['metric']) for r in prior+added
                     if r['series']=='regional_published_yoy' and r['category']=='総計'
                     and r['geography']!='全国計' and r['value']!='')
    with (AUDIT/'medias_regional_coverage.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(['month','metric','prefectures','status'])
        for year in range(2017,2025):
            for m in range(1,13):
                period = f'{year}-{m:02}'
                for metric in ('cost','visit_days','cost_per_day'):
                    count = months[period,metric]
                    writer.writerow([period,metric,count,'complete' if count==47 else 'pending'])
    print('New MEDIAS rows:',len(added))


if __name__=='__main__':
    main()

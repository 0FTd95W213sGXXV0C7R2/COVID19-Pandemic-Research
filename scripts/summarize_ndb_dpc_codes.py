"""Flag observed code descriptions/points and annual DPC facility coverage."""
import csv
import gzip
from collections import defaultdict
from pathlib import Path
import re

from build_dpc_audit_tables import read_book, clean

AUDIT = Path('data/audits/non_covid_access/ndb_open_data')
DATA = Path('data/processed/non_covid_access/ndb_open_data')


def main():
    observed = defaultdict(lambda: defaultdict(set))
    with gzip.open(AUDIT/'procedure_code_crosswalk.csv.gz','rt',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            observed[r['section'],r['procedure_code']][r['fiscal_year']].add(
                (r['classification'],r['label'],r['points']))
    with (AUDIT/'procedure_classification_changes.csv').open('w',encoding='utf-8',newline='') as f:
        writer = csv.writer(f,lineterminator='\n')
        writer.writerow(['section','code','before_year','after_year','before_values','after_values','status'])
        for (section, code), history in sorted(observed.items()):
            years = sorted(history)
            for y1,y2 in zip(years,years[1:]):
                if history[y1]!=history[y2] or int(y2)-int(y1)>1:
                    writer.writerow([section,code,y1,y2,sorted(history[y1]),sorted(history[y2]),
                                     'check_definition_before_linkage'])
    with (AUDIT/'dpc_medias_manifest.csv').open(encoding='utf-8') as f:
        sources = list(csv.DictReader(f))
    with (AUDIT/'dpc_classification_crosswalk.csv').open('w',encoding='utf-8',newline='') as f:
        writer = csv.writer(f,lineterminator='\n')
        writer.writerow(['fiscal_year','disease_code','disease_name','surgery_group','source','sheet','row','comparison_status'])
        for r in sources:
            if '疾患別手術別集計' not in r['title'] or '施設類型別' not in r['title'] or not r['path']:
                continue
            for sheet, rows in read_book(r['path']):
                if not rows or not rows[0] or '疾患コード' not in clean(rows[0][0]):
                    continue
                code = ''
                name = ''
                seen = set()
                for i,row in enumerate(rows[1:],2):
                    if len(row)<4:
                        continue
                    if re.fullmatch(r'\d{6}',clean(row[0])):
                        code,name = clean(row[0]),row[1]
                    group = clean(row[3])
                    if code and group and (code,group) not in seen:
                        seen.add((code,group))
                        writer.writerow([r['period'],code,name,group,r['path'],sheet,i,'year_specific'])
    facilities = defaultdict(set)
    with gzip.open(DATA/'dpc_observations.csv.gz','rt',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['metric']=='施設名' and r['raw']:
                facilities[r['fiscal_year']].add((r['entity'],r['raw']))
    with (AUDIT/'dpc_facility_counts.csv').open('w',encoding='utf-8',newline='') as f:
        writer = csv.writer(f,lineterminator='\n')
        writer.writerow(['fiscal_year','listed_id_name_pairs','note'])
        writer.writerows((year,len(entries),'年度内の通番・施設名組。年度をまたぐ同一施設判定は未検証。')
                         for year,entries in sorted(facilities.items()))


if __name__=='__main__':
    main()

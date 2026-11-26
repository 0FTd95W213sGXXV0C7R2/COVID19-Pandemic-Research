"""List explicit candidates for human review without linking records or adopting codes."""
import csv
import gzip
import re
from collections import defaultdict
from pathlib import Path

AUDIT = Path('data/audits/non_covid_access/ndb_dpc_longitudinal')
PREV = AUDIT.parent/'ndb_open_data'
GROUPS = {
    '内視鏡検査': '内視鏡|ファイバースコピー',
    'CT・MRI': 'コンピューター断層|ＣＴ撮影|ＭＲＩ撮影|磁気共鳴',
    '病理診断': '病理診断|病理組織',
    '悪性腫瘍関連手術': '悪性腫瘍手術',
    '放射線治療': '放射線治療|照射',
    '化学療法関連診療行為': '化学療法|抗悪性腫瘍剤',
    'PCI': '経皮的冠動脈',
    'CABG': '冠動脈.*バイパス',
    '脳血管内治療': '脳血管内|脳.*血栓回収',
    '脳卒中関連診療行為': '脳卒中|脳梗塞',
    'リハビリテーション': 'リハビリテーション料',
}


def main():
    found=set()
    patterns={label:re.compile(pattern) for label,pattern in GROUPS.items()}
    with gzip.open(PREV/'procedure_code_crosswalk.csv.gz','rt',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            for group,pattern in patterns.items():
                if pattern.search(r['label']):
                    found.add((group,r['fiscal_year'],r['procedure_code'],r['label'],r['points'],
                               r['source'],r['member'],r['sheet'],r['row']))
    with (AUDIT/'procedure_candidates.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['group','fiscal_year','code','name','points','source','member','sheet','row','decision'])
        w.writerows((*r,'pending_definition') for r in sorted(found))
    matches=defaultdict(lambda:defaultdict(list))
    with (AUDIT/'facility_correspondence.csv').open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['municipality'] and r['name']:
                matches[r['municipality'],r['name']][int(r['fiscal_year'])].append(r)
    with (AUDIT/'facility_linkage_candidates.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['before_year','after_year','before_local_id','after_local_id','municipality','exact_name',
                    'before_months','after_months','before_source','after_source','decision'])
        for (city,name),years in sorted(matches.items()):
            for y,before in sorted(years.items()):
                after=years.get(y+1,[])
                if len(before)==len(after)==1:
                    b,a=before[0],after[0]
                    w.writerow([y,y+1,b['local_id'],a['local_id'],city,name,b['submitted_months'],a['submitted_months'],
                                b['source'],a['source'],'pending_external_facility_code'])


if __name__=='__main__':
    main()

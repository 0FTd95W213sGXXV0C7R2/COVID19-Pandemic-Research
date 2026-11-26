"""Supplement the integrated audit with historical and HBCR arithmetic checks."""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_cancer_integration import now, write_csv
from audit_hbcr_tables import reconcile


def records(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    out=args.output
    hb=args.root/'hbcr_priority_review'
    treatment=records(hb/'HBCR_2022_site_treatment_annual.csv')
    source=next((args.root/'raw/hospital_registry').glob('*_2022_report.pdf'))
    result=reconcile('site_treatment',treatment,source)
    checks=Counter()
    for suffix,total_field in (('discovery_page124_QA','registration_count'),
                               ('discovery_page125_QA','published_total'),('prostate_QA','published_total'),
                               ('treatment_QA','count')):
        # Counts are rebuilt below from the primary extracts; the QA tables only
        # carry the annual comparators absent from the page125/prostate extracts.
        extra=suffix.replace('_QA','')
        rows=records(hb/f'HBCR_2022_{extra if extra!="prostate" else "prostate_monthly"}.csv') if extra!='treatment' else records(hb/'HBCR_2022_treatment_monthly.csv')
        monthly=defaultdict(dict)
        for row in rows:
            month=row.get('diagnosis_month') or row.get('month')
            if not month:
                continue
            identity=(row.get('cancer_group') or row.get('site',''),row.get('diagnosis_year') or row['year'],
                      row.get('discovery_pathway') or row['method'])
            m=int(float(month))
            if m in monthly[identity]:
                checks['duplicate_month']+=1
            monthly[identity][m]=int(row.get('registration_count') or row['count'])
        for row in records(hb/f'HBCR_2022_{suffix}.csv'):
            identity=(row.get('cancer_group') or row.get('site',''),row.get('diagnosis_year') or row['year'],
                      row.get('discovery_pathway') or row['method'])
            if extra=='prostate':
                identity=('前立腺',identity[1],identity[2])
            values=monthly[identity]
            checks['groups']+=1
            if set(values)!=set(range(1,13)):
                checks['incomplete']+=1
            elif sum(values.values())!=int(float(row[total_field])):
                checks['sum_difference']+=1
            else:
                checks['match']+=1
    report={'recorded_jst':now(),'site_treatment':result,'monthly_additivity':dict(checks),
            'limit':'For page125 and prostate the comparator is the existing transcribed annual QA value.'}
    (out/'hbcr_denominator_additivity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    docs=Path('docs/audits/rebuild_2026')
    coverage={
        1:('PARTIALLY_REPRODUCED','行数と原表を再検証。過去集約は部分検証'),
        2:('PARTIALLY_REPRODUCED','罹患率の分母と値を比較。旧集計と対象キーが異なる'),
        3:('PARTIALLY_REPRODUCED','結合不能行を保留。旧集計と対象キーが異なる'),
        4:('PARTIALLY_REPRODUCED','年齢別率を再計算したが旧高齢層の個別集計は未再現'),
        5:('PARTIALLY_REPRODUCED','1985基準の再計算'),
        6:('PARTIALLY_REPRODUCED','Segi重みの再計算'),
        7:('PARTIALLY_REPRODUCED','2015基準は近似計算'),
        8:('PARTIALLY_REPRODUCED','2015基準の近似は実行、旧分解は未再現'),
        9:('PARTIALLY_REPRODUCED','原資料・原値照合を実施'),
        11:('PARTIALLY_REPRODUCED','対象15シートを原表から列挙'),
        13:('PARTIALLY_REPRODUCED','原表属性比較。全正規化属性は未検証'),
        14:('PARTIALLY_REPRODUCED','正規化数値と原表属性。詳細列の全属性は未検証'),
        15:('PARTIALLY_REPRODUCED','月合算と一意性の一部を再検証'),
        23:('REPRODUCED','発見経緯860件。原表キー・数値の照合範囲'),
        24:('REPRODUCED','治療535件と分母210件。原表キー・数値の照合範囲'),
        25:('REPRODUCED','発見経緯860件と病期255件。原表キー・数値の照合範囲'),
    }
    def stages():
        for stage in range(1,26):
            files=sorted(docs.glob(f'cancer*stage{stage}_*.md'))
            status,reason=coverage.get(stage,('BLOCKED' if not files else 'NOT_EXECUTED',
                                              '専用の過去記録を特定できず' if not files else '個別に再実行していない'))
            yield stage,'|'.join(str(x) for x in files),status,reason
    write_csv(out/'historical_audit_reproduction.csv',['stage','record','status','reason'],stages())
    print(report)


if __name__=='__main__':
    main()

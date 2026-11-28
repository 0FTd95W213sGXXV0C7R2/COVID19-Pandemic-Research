import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from extend_employment_wage_c13 import MONTHS, monthly_rows, overlap, revision_candidates


def sample():
    table = '<table>'
    for p in sorted(MONTHS):
        y,m = p.split('-')
        table += f'<tr><th data-unique="{y}00{m}{m}">{y}年{int(m)}月</th><td>50</td></tr>'
    return {'table':table+'</table','requestData':{
        'etcItem1':'01','etcItem2':'000','etcItem3':'0','etcItem4':'07',
        'etcItem5':'00000','colItemList1':'00'}}


class FollowupTests(unittest.TestCase):
    def test_monthly_exact_coverage_and_coordinates(self):
        rows = monthly_rows(sample(),'0')
        self.assertEqual(len(rows),96)
        self.assertEqual(rows[-1]['coordinate'],'tr[2024001212]/td[1]')
        self.assertEqual(rows[-1]['raw'],'50')

    def test_wrong_age_and_wrong_month_rejected(self):
        doc = sample()
        doc['requestData']['colItemList1'] = '01'
        with self.assertRaisesRegex(ValueError,'classification'):
            monthly_rows(doc,'0')
        doc = sample()
        doc['table'] = doc['table'].replace('2024001212','2024001111')
        with self.assertRaisesRegex(ValueError,'coordinate'):
            monthly_rows(doc,'0')

    def test_overlap_uses_explicit_coordinates(self):
        rows = monthly_rows(sample(),'0')
        earlier = [dict(rows[0],raw='90'),rows[1]]
        self.assertEqual(overlap(rows,earlier),{'matching':1,'different':1,'new_only':94,'prior_only':0})

    def test_revision_requires_explicit_year(self):
        rows = [dict(period='2019-Q1',metric='休業者',source=f'reason_{j}',sheet='p1',cell='r1',raw=str(j))
                for j in range(3)]
        evidence = {f'reason_{j}':dict(revised_years=[2019] if j==1 else [2020],release=str(j)) for j in range(3)}
        self.assertEqual(revision_candidates(rows,evidence)[0]['candidate_source'],'reason_1')

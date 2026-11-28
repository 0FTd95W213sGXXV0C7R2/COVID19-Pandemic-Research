import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from acquire_employment_wage_c13 import job_links, period, reason_rows
from lxml import html


class C13Tests(unittest.TestCase):
    def test_periods_are_distinct(self):
        self.assertEqual(period(2020,'４～６月'),('quarter','2020-Q2'))
        self.assertEqual(period(2020,'４月'),('month','2020-04'))
        self.assertEqual(period(2020,None,True),('fiscal_year','2020'))
        self.assertIsNone(period(2020,'４～９月'))

    def test_job_id_is_taken_from_catalog_link(self):
        node = html.fromstring('''<article><a data-key="uid">
          <span class="stat-separator">長期時系列表</span><span class="stat-separator">2</span>
          <span class="stat-separator">試験</span></a>
          <a href="/x?statInfId=123&amp;fileKind=0">EXCEL</a></article>''').getroottree()
        self.assertEqual(list(job_links(node))[0][2],'https://www.e-stat.go.jp/x?statInfId=123&fileKind=0')

    def test_reason_extraction_rejects_shifted_table(self):
        first = '2020年 1～3月 ' + ' '.join(['2']*10)
        text = '休業の理由別休業者\n'+'\n'.join([first]*6)
        self.assertEqual(len(reason_rows(Path('test.pdf'),text)),30)
        self.assertEqual(reason_rows(Path('test.pdf'),text+'\n'+first),[])

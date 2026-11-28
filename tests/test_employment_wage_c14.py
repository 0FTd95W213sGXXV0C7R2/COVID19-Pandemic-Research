"""C-14 period, coordinate and wage classification checks."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_employment_wage_c14 import wage_period, wage_rows, verify_cell, reference_year


class C14Tests(unittest.TestCase):
    def test_calendar_fiscal_and_quarter_are_distinct(self):
        self.assertEqual(wage_period('2020','CY'),('year','2020'))
        self.assertEqual(wage_period('2020','FY'),('fiscal_year','2020'))
        self.assertEqual(wage_period('2020','Q1'),('quarter','2020-Q1'))
        self.assertEqual(wage_period('2020','13')[0],'unknown')

    def test_era_year_anchors_first_month(self):
        self.assertEqual(reference_year('平成２９年'),(2017,False))
        self.assertEqual(reference_year('令和元年度'),(2019,True))
        self.assertIsNone(reference_year('前年同月'))

    def test_numeric_coordinate_readback(self):
        self.assertTrue(verify_cell({'D11':'1.00'},'D11',1))
        self.assertFalse(verify_cell({'D11':'1.01'},'D11',1))
        self.assertFalse(verify_cell({},'D11',0))

    def test_nominal_real_are_attributes_of_index_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'fixture.csv'
            path.write_bytes(('種別,年,月,産業分類,規模,就業形態,現金給与総額,'
                              '実質賃金指数（現金給与総額）\n指数,2020,CY,TL,T,0,100,\n').encode('cp932'))
            rows = list(wage_rows(path,'WC02'))
        self.assertEqual([r[13] for r in rows],['nominal','real'])
        self.assertEqual([r[14] for r in rows],['100',''])
        self.assertEqual([r[3] for r in rows],['G2','H2'])

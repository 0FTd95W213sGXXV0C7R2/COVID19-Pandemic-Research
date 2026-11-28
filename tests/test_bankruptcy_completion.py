"""Regression tests for missing bankruptcy tables."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from complete_bankruptcy_audit import compact_tables


class CompactBankruptcyTables(unittest.TestCase):
    def test_capital_ignores_preceding_debt_table_and_subtotal(self):
        page = """負債規模別
5000万円以上1億円未満   20   50
合計   99   60
資本金規模別
前年同月     当月
個人事業主   1   10
1000万円未満   2   20
個人+1000万円未満合計   3   30
1000万円以上5000万円未満   3   15
5000万円以上1億円未満   4   10
1億円以上   5   5
合計   15   60"""
        options = list(compact_tables(page,'BK07',60,'2020-01'))
        self.assertEqual(len(options),1)
        self.assertEqual(options[0]['5000万円以上1億円未満（5区分表）'],10)

    def test_incomplete_form_table_does_not_fill_missing_cell(self):
        page = """倒産態様別
前年同月     当月
会社更生法   0   0
破産   5   8
特別清算   1
民事再生法   2   2
合計   8   10"""
        self.assertEqual(list(compact_tables(page,'BK09',10,'2020-01')),[])

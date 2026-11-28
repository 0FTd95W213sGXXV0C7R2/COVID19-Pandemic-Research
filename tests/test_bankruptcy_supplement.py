"""Regression checks for the bankruptcy table parsers."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_bankruptcy_supplement import category_table, history


class BankruptcyParserTests(unittest.TestCase):
    def test_category_industry_total(self):
        self.assertEqual(category_table('破産 1 2 3 4 5 6 7 8 36', ('破産',)),
                         {'破産': 36})

    def test_category_rejects_inconsistent_total(self):
        with self.assertRaises(ValueError):
            category_table('破産 1 2 3 4 5 6 7 8 35', ('破産',))

    def test_category_rejects_duplicate_row(self):
        row = '破産 1 2 3 4 5 6 7 8 36'
        with self.assertRaises(ValueError):
            category_table(f'{row}\n{row}', ('破産',))

    def test_history_rejects_truncated_period(self):
        with self.assertRaisesRegex(ValueError, 'incomplete months'):
            history('2017年( 2018年( 2019年( 2020年( 2021年( 2022年(\n1 4 0')

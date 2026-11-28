"""Historical table layout and publication archive regression checks."""
import sys
import unittest
from pathlib import Path

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_bankruptcy_history import legacy_table, report_links, summary_table, FORM


class HistoricalBankruptcyTests(unittest.TestCase):
    def test_archive_separates_calendar_and_fiscal_reports(self):
        doc = html.fromstring('''<a href="/aggregation/a">倒産集計 2022年 (1月～12月)</a>
            <a href="/aggregation/b">倒産集計 2022年度</a>
            <a href="/aggregation/c">倒産集計 2022年1月報</a>''')
        self.assertEqual(set(report_links(doc, 2022)), {'tdb_2022.html', 'tdb_2022-01.html'})

    def test_legacy_previous_column_does_not_fill_current_blank(self):
        page = ('  特別清算     4 ( 40.0 )\n'
                '  破産         6 ( 60.0 )  9 (100.0 )\n'
                '  合計        10 (100.0 )  9 (100.0 )\n')
        self.assertEqual(legacy_table(page, ('特別清算','破産'), 9),
                         {'特別清算': None, '破産': 9})

    def test_summary_keeps_explicit_zero_and_rejects_unreconciled_total(self):
        page = (' 倒産態様別\n  - 前年同月 -     - 当月 -\n'
                ' 会社更生法   0  0  -\n 破産         3  5  66.7\n'
                ' 特別清算     1  1  0.0\n 民事再生法   1  1  0.0\n'
                ' 合計         5  7  40.0\n')
        self.assertEqual(summary_table(page, FORM, 7)['会社更生法'], 0)
        with self.assertRaisesRegex(ValueError, 'Summary total mismatch'):
            summary_table(page, FORM, 8)

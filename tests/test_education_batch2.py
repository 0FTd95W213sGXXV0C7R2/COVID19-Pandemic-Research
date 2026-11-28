from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError

import openpyxl

from education_batch2 import check_totals, region_table, rounding_matches
from education_sources import acquire
from audit_education_sources import xlsx_first_sheet_values


class Batch2Tests(TestCase):
    def failure(self, error, attempts):
        with TemporaryDirectory() as directory, patch(
            'education_sources.urlopen',side_effect=error
        ) as request, patch('education_sources.time.sleep'):
            record,=acquire(Path(directory),{'a.pdf':'https://example.org/a'})
            self.assertEqual(record['status'],'failed')
            self.assertEqual(request.call_count,attempts)
            self.assertFalse((Path(directory)/'a.pdf').exists())

    def test_http_404(self):
        self.failure(HTTPError('https://example.org/a',404,'not found',None,None),1)

    def test_http_429(self):
        self.failure(HTTPError('https://example.org/a',429,'rate limit',None,None),3)

    def test_http_503(self):
        self.failure(HTTPError('https://example.org/a',503,'unavailable',None,None),3)

    def test_timeout(self):
        self.failure(TimeoutError(),3)

    def test_incomplete_transfer(self):
        self.failure(IncompleteRead(b'%PDF-',40),3)

    def test_shifted_columns(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            region_table([f'{i} 県 1 2' for i in range(1,48)]+['計 47 94 1'],2)

    def test_duplicate_and_national_mismatch(self):
        lines=[f'{i} 県 1 2' for i in range(1,48)]+['計 47 93']
        with self.assertRaisesRegex(ValueError,'duplicate'):
            region_table(lines+[lines[0]],2)
        with self.assertRaisesRegex(ValueError,'national sum'):
            check_totals(region_table(lines,2),('students','cases'))

    def test_rounding(self):
        self.assertTrue(rounding_matches(1,16,'6.3'))
        self.assertFalse(rounding_matches(1,16,'6.2'))
        self.assertFalse(rounding_matches(0,0,'0.0'))

    def test_xlsx_merged_cells_and_symbol(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.xlsx'
            book=openpyxl.Workbook()
            sheet=book.create_sheet('second')
            sheet.merge_cells('A1:B1')
            sheet['A1']='***'
            sheet['A2']=0
            book.save(path)
            values=xlsx_first_sheet_values(path,2)
            self.assertEqual(values['A1'],'***')
            self.assertIsNone(values.get('B1'))
            self.assertEqual(values['A2'],0)

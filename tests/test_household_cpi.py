import unittest

from acquire_household_cpi import inspect, month_range


class HouseholdCpiTest(unittest.TestCase):
    def test_month_range(self):
        self.assertEqual(month_range('201701','202412')[0], '201701')
        self.assertEqual(len(month_range('201701','202412')), 96)

    def test_cpi_month_axis(self):
        header = '類・品目,総合\nGroup/Item,All items\ncode,1\nserial,1\nweight,1\nweight ratio,1\n'
        csv = (header+'202411,105\n202412,106\n').encode('cp932')
        self.assertEqual(inspect(csv,False,('202411','202412'))['required_months_covered'],2)
        with self.assertRaisesRegex(ValueError,'Required months'):
            inspect(csv,False,('202410','202412'))
        with self.assertRaisesRegex(ValueError,'Month axis'):
            inspect(csv.replace(b'202412',b'202411'),False,('202411','202412'))
        with self.assertRaisesRegex(ValueError,'dimensions'):
            inspect(csv.replace(b',106',b''),False,('202411','202412'))

#!/usr/bin/env python3
"""Compare two published preliminary PDF samples to the annual-release series."""
import argparse
import csv
import re
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = Path('non_covid_access/hospital_report_2017_2024')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    with (ROOT / 'data/processed' / SCOPE / 'national_daily_means_derived.csv').open(encoding='utf-8') as stream:
        annual = {(r['period'], r['metric']): r for r in csv.DictReader(stream)}
    comparisons = []
    for month in ('04', '12'):
        pdf_name = f'provisional_2024_{month}.pdf'
        text = subprocess.check_output(['pdftotext', '-f', '1', '-l', '1', '-layout',
                                        str(args.work / pdf_name), '-'], text=True)
        section = text.split('１．１日平均患者数', 1)[1].split('診療所', 1)[0]
        for label, metric in [('総数', 'daily_mean_inpatients'), ('外来患者数', 'daily_mean_outpatients')]:
            match = re.search(rf'^\s*{label}\s+([0-9]+(?: [0-9]{{3}})*)', section, re.M)
            prelim = int(match[1].replace(' ', ''))
            key = (f'2024-{month}', metric)
            final = annual[key]
            rounded = int((Decimal(final['numerator_raw']) / int(final['calendar_days'])).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP))
            comparisons.append(dict(period=key[0], metric=metric, provisional_pdf=pdf_name, page=1,
                                    provisional_value=prelim, annual_source_id=final['source_id'],
                                    annual_derived_rounded=rounded, annual_minus_provisional=rounded-prelim))
    with (ROOT / 'data/audits' / SCOPE / 'provisional_comparison.csv').open(
            'w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, list(comparisons[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(comparisons)


if __name__ == '__main__':
    main()

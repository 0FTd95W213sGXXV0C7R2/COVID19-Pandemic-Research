"""Extract source-addressed NDB observations on their published axes."""
import csv
import gzip
import io
import re
import unicodedata
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

ROOT = Path('data/audits/non_covid_access/ndb_open_data')
OUTPUT = Path('data/processed/non_covid_access/ndb_open_data')
AXES = {'都道府県別': 'prefecture', '性年齢別': 'sex_age', '診療月別': 'month'}
SECTIONS = 'ABDEGHJKLMN'


def norm(value):
    return ''.join(unicodedata.normalize('NFKC', str(value if value is not None else '')).split())


def workbooks(row, stack):
    path = Path(row['saved_path'])
    if path.suffix == '.xlsx':
        yield '', path, row['section'], row['axis']
    if path.suffix == '.zip':
        archive = stack.enter_context(ZipFile(path))
        for member in archive.namelist():
            parts = member.split('/')
            if len(parts) != 3 or not member.endswith('.xlsx') or not parts[1] or parts[1][0] not in SECTIONS:
                continue
            for label, axis in AXES.items():
                if label in parts[-1] and 'クロス' not in member:
                    yield member, io.BytesIO(archive.read(member)), parts[1][0], axis
                    break


def write(path, fields):
    handle = gzip.open(path,'wt',encoding='utf-8',newline='') if path.suffix == '.gz' else path.open('w',encoding='utf-8',newline='')
    writer = csv.writer(handle,lineterminator='\n')
    writer.writerow(fields)
    return handle, writer


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'source_manifest.csv').open(encoding='utf-8') as handle:
        sources = list(csv.DictReader(handle))
    with ExitStack() as stack:
        def writer(path, fields):
            handle, csv_writer = write(path, fields.split())
            stack.enter_context(handle)
            return csv_writer
        obs = writer(OUTPUT/'claims_counts.csv.gz',
                     'fiscal_year release scope section axis source member sheet row column procedure_code label points dimension raw_value count status')
        cov = writer(ROOT/'coverage.csv',
                     'fiscal_year release scope section axis source member sheet source_period dimension_columns extracted_cells')
        flags = writer(ROOT/'quality_flags.csv', 'release source member sheet status cells')
        code = writer(ROOT/'procedure_code_crosswalk.csv.gz',
                      'fiscal_year scope section procedure_code classification label points source member sheet row')
        for src in sources:
            if src['status'] != 'acquired':
                continue
            with ExitStack() as files:
                for member, file, section, axis in workbooks(src, files):
                    book = load_workbook(file,read_only=True,data_only=True)
                    for sheet in book:
                        rows = sheet.values
                        preamble = ''
                        heading = None
                        heading_row = 0
                        extracted = 0
                        statuses = Counter()
                        classification = ''
                        for r, cells in enumerate(rows,1):
                            labels = [norm(v) for v in cells]
                            if r == 1:
                                preamble = str(cells[0] or '')
                            if heading is None:
                                if '診療行為コード' in labels and any(x.startswith('総計') for x in labels):
                                    index = labels.index('診療行為コード')
                                    total = next(i for i,x in enumerate(labels) if x.startswith('総計'))
                                    heading = labels
                                    heading_row = r
                                continue
                            if axis == 'sex_age' and r == heading_row+1:
                                sex = ''
                                for c in range(total+1,len(heading)):
                                    sex = heading[c] or sex
                                    heading[c] = f'{sex}:{labels[c]}' if sex and labels[c] else ''
                            procedure = norm(cells[index])
                            if not re.fullmatch(r'\d{9}',procedure):
                                continue
                            name = cells[index+1]
                            points = cells[index+2]
                            if labels[0] and index >= 2:
                                classification = labels[0]
                            # Keep all published national/month columns and initial/revisit regional/age detail.
                            if axis == 'prefecture':
                                cols = range(total,len(heading)) if '初再診料' in src['title'] + member else [total]
                            elif axis == 'sex_age':
                                cols = range(total+1,len(heading)) if '初再診料' in src['title'] + member else []
                            else:
                                cols = range(total,len(heading))
                            if axis == 'prefecture':
                                code.writerow([src['fiscal_year'],src['payer_scope'],section,procedure,classification,name,
                                               points,src['saved_path'],member,sheet.title,r])
                            for c in cols:
                                if not heading[c] or c >= len(cells):
                                    continue
                                value = cells[c]
                                raw = '' if value is None else value
                                status = ('blank' if raw == '' else 'numeric_zero' if raw == 0 else
                                          'numeric' if isinstance(raw,(int,float)) else
                                          'suppressed' if norm(raw) in {'-', '‐', '－', '−', '―'} and '10未満' in norm(preamble)
                                          else 'unresolved_symbol')
                                dim = heading[c]
                                if axis == 'month' and c > total:
                                    month = re.fullmatch(r'(\d{1,2})月',dim)
                                    if month:
                                        m = int(month[1])
                                        dim = f'{int(src["fiscal_year"])+(m<4)}-{m:02}'
                                obs.writerow([src['fiscal_year'],src['release'],src['payer_scope'],section,axis,
                                              src['saved_path'],member,sheet.title,r,c+1,procedure,name,points,
                                              dim,raw,raw if status.startswith('numeric') else '',status])
                                extracted += 1
                                statuses[status] += 1
                        cov.writerow([src['fiscal_year'],src['release'],src['payer_scope'],section,axis,src['saved_path'],
                                      member,sheet.title,preamble,sum(bool(x) for x in heading[total+1:]) if heading else 0,extracted])
                        for status,n in statuses.items():
                            if status != 'numeric':
                                flags.writerow([src['release'],src['saved_path'],member,sheet.title,status,n])
                    book.close()


if __name__ == '__main__':
    main()

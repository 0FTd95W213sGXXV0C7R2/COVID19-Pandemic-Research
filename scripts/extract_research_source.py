"""Create a neutral source inspection JSON without imputing or adopting values."""
import argparse
import csv
import json
from pathlib import Path

import openpyxl
import pdfplumber
import xlrd
from lxml import html


def inspect(path, encoding='utf-8-sig'):
    suffix = path.suffix.lower()
    if suffix=='.csv':
        with path.open(encoding=encoding,newline='') as handle:
            return [{'row':i,'cells':row} for i,row in enumerate(csv.reader(handle),1)]
    if suffix=='.json':
        return json.loads(path.read_text(encoding=encoding))
    if suffix=='.html':
        root=html.parse(path)
        return [[[' '.join(cell.itertext()).strip() for cell in row.xpath('./th|./td')]
                 for row in table.xpath('.//tr')] for table in root.xpath('//table')]
    if suffix=='.pdf':
        with pdfplumber.open(path) as pdf:
            return [dict(page=i,text=p.extract_text(),tables=p.extract_tables(),ocr=False)
                    for i,p in enumerate(pdf.pages,1)]
    if suffix=='.xlsx':
        book=openpyxl.load_workbook(path,data_only=True)
        try:
            return [dict(sheet=s.title,merges=[str(r) for r in s.merged_cells.ranges],
                         rows=list(s.values)) for s in book.worksheets]
        finally:
            book.close()
    if suffix=='.xls':
        book=xlrd.open_workbook(path,formatting_info=True)
        return [dict(sheet=s.name,merges_zero_based=s.merged_cells,
                     rows=[s.row_values(i) for i in range(s.nrows)]) for s in book.sheets()]
    raise ValueError(f'Unsupported extension: {suffix}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--encoding',default='utf-8-sig')
    args=parser.parse_args()
    with args.output.open('x') as f:
        json.dump(inspect(args.source,args.encoding),f,ensure_ascii=False,default=str)
        f.write('\n')

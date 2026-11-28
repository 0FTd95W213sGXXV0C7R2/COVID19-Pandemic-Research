"""Read wage coordinates directly from unquoted CP932 originals."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import re


def check(root):
    originals = {}
    for name in ('wage_real.csv','wage_index.csv'):
        data = (root/'raw'/name).read_bytes()
        if b'"' in data:
            raise ValueError('Independent delimiter check requires unquoted source')
        originals[name] = data.decode('cp932').splitlines()
    counts = Counter()
    seen = set()
    for name in ('analysis_candidates.csv.gz','exclusions.csv.gz'):
        with gzip.open(root/name,'rt',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                if row['family'] not in ('WC01','WC02'):
                    continue
                col,line = re.fullmatch(r'([A-Z]+)(\d+)',row['cell']).groups()
                index = 0
                for letter in col:
                    index = index*26+ord(letter)-64
                source = originals[row['source']]
                fields = source[int(line)-1].split(',')
                expected = source[0].split(',')[index-1]
                if expected!=row['metric'] or fields[index-1]!=row['raw']:
                    raise ValueError(f'Independent CSV mismatch: {row["source"]} {row["cell"]}')
                key = row['source'],row['cell']
                if key in seen:
                    raise ValueError(f'Duplicate wage coordinate: {key}')
                seen.add(key)
                counts[row['family']] += 1
    return dict(counts)


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    print(json.dumps(check(parser.parse_args().root)))

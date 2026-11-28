"""Resolve annual report and correction links from the official MEXT indices."""
import argparse
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lxml import html
from education_sources import acquire
from education_batch2 import dump

ROOT='https://www.mext.go.jp'
PAGES={'index':'1302902.htm','errata':'1300356_00003.htm'}


def sources(cache):
    result={}
    for label,page in PAGES.items():
        url=f'{ROOT}/a_menu/shotou/seitoshidou/{page}'
        name=f'{label}.html'
        record,=acquire(cache,{name:url})
        if record['status']!='acquired':
            raise ValueError(record)
        document=html.parse(cache/name)
        for anchor in document.xpath('//a[@href]'):
            title=anchor.text_content().strip()
            m=re.match(r'令和([元1-6])年度児童生徒',title)
            href=anchor.get('href')
            if m and href.endswith('.pdf') and ('概要' not in title or href.endswith('100002753_3.pdf')):
                year=2019 if m[1]=='元' else int(m[1])+2018
                group='overview' if '概要' in title else label
                name='overview_2024.pdf' if group=='overview' else f'{group}_{year}_{Path(href).name}'
                result[name]=f'{ROOT}{href}'
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('cache',type=Path)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    found=sources(args.cache)
    def one(pair):
        return next(acquire(args.cache,dict([pair])))
    with ThreadPoolExecutor(8) as pool:
        dump(args.manifest,list(pool.map(one,found.items())))

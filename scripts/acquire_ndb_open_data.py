"""Acquire official NDB medical procedure workbooks within the audit scope."""
import csv
import hashlib
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from lxml import html

BASE = 'https://www.mhlw.go.jp'
INDEX = BASE + '/stf/seisakunitsuite/bunya/0000177182.html'
SCOPE = Path('non_covid_access/ndb_open_data')
RAW = Path('data/raw') / SCOPE
AUDIT = Path('data/audits') / SCOPE
SECTIONS = {'A', 'B', 'D', 'E', 'G', 'H', 'J', 'K', 'L', 'M', 'N'}


def get(url):
    with urlopen(url, timeout=45) as response:
        return response.read()


def label(node):
    return ''.join(unicodedata.normalize('NFKC', node.text_content()).split())


def retrieve(job):
    release, page, title, section, axis, url, scope = job
    result = dict(release=release, fiscal_year=2013+release, page_url=page, title=title,
                  section=section, axis=axis, url=url, payer_scope=scope, publisher='厚生労働省',
                  published='2026-06-16' if release == 11 else '不明', retrieved_jst=datetime.now(
                      ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'), status='failed',
                  saved_path='', size='', sha256='', error='', reuse=BASE+'/chosakuken/')
    try:
        file = RAW / f'r{release}_{url.rsplit("/",1)[-1]}'
        data = file.read_bytes() if file.exists() else get(url)
        expected = b'%PDF-' if file.suffix == '.pdf' else b'PK\x03\x04'
        if not data.startswith(expected):
            raise ValueError('Unexpected file signature')
        if not file.exists():
            file.write_bytes(data)
        result.update(status='acquired', saved_path=str(file), size=len(data), sha256=hashlib.sha256(data).hexdigest())
    except (OSError, ValueError) as exc:
        result['error'] = str(exc)
    return result


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    index = html.fromstring(get(INDEX))
    jobs = []
    for a in index.xpath('//h2/a[contains(text(),"NDBオープンデータ")]'):
        release = int(re.search(r'\d+', label(a))[0])
        if release not in range(3,12):
            continue
        page = urljoin(BASE,a.get('href'))
        doc = html.fromstring(get(page))
        scope = 'historical_scope'
        section = ''
        medical = False
        for el in doc.xpath('//h3|//h4|//em|//a[@href]'):
            title = label(el)
            if el.tag == 'h3':
                section = ''
                medical = title.startswith('医科診療行為') and '患者数' not in title
            if el.tag == 'h4' or (el.tag == 'em' and title == 'A基本診療料'):
                section = title.lstrip('○●')[:1]
            href = el.get('href','')
            url = urljoin(BASE,href)
            if href.endswith('.pdf') and '解説編' in title:
                jobs.append((release,page,title,'guide','guide',url,'reference'))
            if release == 11 and href.endswith('.zip') and href.rsplit('/',1)[-1] in ('001744598.zip','001742574.zip'):
                scope = 'public_funding_included' if '001742574' in href else 'public_funding_excluded'
                jobs.append((release,page,'医科診療行為（算定回数）','bundle','bundle',url,scope))
            if not medical or not href.endswith('.xlsx') or section not in SECTIONS or '算定回数' not in title:
                continue
            axes = [axis for key,axis in [('都道府県別','prefecture'),('性年齢別','sex_age'),('診療月別','month')]
                    if key in title]
            if axes and ('二次医療圏' not in title) and ('クロス' not in title):
                scope = 'public_funding_included' if release == 10 else 'historical_scope'
                jobs.append((release,page,title,section,axes[0],url,scope))
    with ThreadPoolExecutor(max_workers=15) as pool:
        rows = list(pool.map(retrieve,dict.fromkeys(jobs)))
    with (AUDIT/'source_manifest.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream,list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()

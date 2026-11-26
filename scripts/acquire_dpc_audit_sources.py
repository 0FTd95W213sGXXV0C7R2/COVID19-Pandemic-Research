"""Acquire priority DPC tables and supplemental MEDIAS evidence."""
import csv
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from lxml import html

BASE = 'https://www.mhlw.go.jp'
PAGES = dict(enumerate(('0000196043_00001','0000196043_00003','0000196043_00004','0000196043_00005',
                        '0000196043_00006','newpage_39119','newpage_00137','newpage_00203'),2017))
REL = Path('non_covid_access/ndb_open_data')
AUDIT = Path('data/audits') / REL
RAW = Path('data/raw/non_covid_access/dpc_medias_sources')
TARGET = re.compile('施設概要表|医療圏別MDC患者数|予定・救急医療入院|診断群分類別在院日数|疾患別手術別集計[_＿](施設類型別|MDC0[15]\\b)|退院患者調査.*結果報告.*総[－-]')


def get(job):
    dataset, period, page, title, url = job
    row = dict(dataset=dataset,period=period,page_url=page,title=title,url=url,publisher='厚生労働省',
               published='不明', retrieved_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
               status='failed', path='', sha256='', size='', error='', reuse=BASE+'/chosakuken/')
    try:
        file = RAW/f'{dataset}_{period}_{url.rsplit("/",1)[-1]}'
        if file.exists():
            data = file.read_bytes()
        else:
            with urlopen(url,timeout=35) as res:
                data = res.read()
            if not data.startswith((b'PK\x03\x04',b'%PDF-',bytes.fromhex('d0cf11e0a1b11ae1'))):
                raise ValueError('Unexpected file signature')
            file.write_bytes(data)
        row.update(status='acquired',path=str(file),sha256=hashlib.sha256(data).hexdigest(),size=len(data))
    except (OSError, ValueError) as exc:
        row['error'] = str(exc)
    return row


def main():
    RAW.mkdir(parents=True,exist_ok=True)
    jobs = []
    for year, ident in PAGES.items():
        page = BASE+f'/stf/shingi2/{ident}.html'
        with urlopen(page,timeout=25) as response:
            document = html.fromstring(response.read())
        for a in document.xpath('//a[@href]'):
            title = ''.join(a.text_content().split())
            href = a.get('href')
            if TARGET.search(title) and href.endswith(('.xlsx','.xls','.pdf')):
                jobs.append(('dpc',year,page,title,urljoin(BASE,href)))
    page = BASE+'/stf/seisakunitsuite/bunya/iryouhoken/database/zenpan/cyouzai_doukou_topics_h31.html'
    jobs.append(('medias','2019-12',page,'年齢階級別、都道府県別の医療費等（医科電算処理分）',
                 BASE+'/bunya/iryouhoken/database/zenpan/xls/ika_doukou_topics_r1_06.xls'))
    for issue in ('18','20'):
        page = BASE+f'/topics/medias/month/{issue}/03.html'
        with urlopen(page,timeout=25) as response:
            document = html.fromstring(response.read())
        for a in document.xpath('//a[contains(@href,"gaisan_iryou_data_03")]'):
            if a.get('href').endswith('.xlsm'):
                jobs.append(('medias',f'20{issue}-03',page,'概算医療費（3月号）',urljoin(page,a.get('href'))))
    page = BASE+'/topics/medias/month/20/02.html'
    jobs.append(('medias','2020-02',page,'概算医療費（令和元年度2月号）',
                 urljoin(page,'xls/gaisan_iryou_data_02.xlsm')))
    with ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(get,dict.fromkeys(jobs)))
    with (AUDIT/'dpc_medias_manifest.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Download MHLW release workbooks and record their provenance."""
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
REL = Path('non_covid_access/medias_hospital_monthly')
RAW = Path('data/raw') / REL
AUDIT = Path('data/audits') / REL


def fetch(job):
    kind, year, month, override = job
    period = f'{year}-{month:02}'
    suffix = f'{year % 100:02}/{month:02}.html'
    path = '/topics/medias/month/' if kind == 'medias' else '/toukei/saikin/hw/byouin/m'
    page = override or BASE + path + suffix
    record = dict(dataset=kind, issue=period, publisher='厚生労働省', page_url=page, title='', release_date='不明',
                  source_url='', retrieved_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                  http_status='', bytes='', sha256='', local_path='', status='未取得', reason='',
                  reuse_terms=BASE+'/chosakuken/')
    try:
        with urlopen(page, timeout=20) as response:
            doc = html.fromstring(response.read())
        record['title'] = doc.xpath('string(//title)').strip()
        stamps = doc.xpath('//time/@datetime')
        if stamps:
            record['release_date'] = stamps[0]
        for link in doc.xpath('//a[@href]'):
            href = link.get('href')
            label = ''.join(link.text_content().split())
            if not re.search(r'\.xlsx?$', href, re.I):
                continue
            if kind == 'medias' and 'gaisan_iryou_data_' not in href:
                continue
            if kind == 'hospital' and not (label == '参考表' or 'sankou' in href or (year == 2017 and '図表データ' in label)):
                continue
            record['source_url'] = urljoin(page, href)
            file = RAW / f'{kind}_{period}{Path(href).suffix}'
            with urlopen(record['source_url'], timeout=25) as response:
                record['http_status'] = response.status
                payload = response.read()
            if not payload.startswith((b'PK\x03\x04', bytes.fromhex('d0cf11e0a1b11ae1'))):
                raise ValueError('invalid spreadsheet signature')
            if file.exists() and file.read_bytes() != payload:
                raise ValueError('publisher bytes changed; existing raw retained')
            file.write_bytes(payload)
            record.update(status='取得済', bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                          local_path=str(file))
            break
        else:
            record['reason'] = '参考表Excelリンク未特定' if kind == 'hospital' else '概算医療費Excelリンク未特定'
    except (ValueError, OSError) as exc:
        record['http_status'] = getattr(exc, 'code', record['http_status'])
        record['reason'] = str(exc)
    return record


def medias_issues():
    archive = BASE + '/bunya/iryouhoken/database/zenpan/iryou_doukou_{}.html'
    for fiscal_year in range(2016, 2025):
        code = f'h{fiscal_year-1988:02}' if fiscal_year < 2019 else f'r{fiscal_year-2018:02}'
        with urlopen(archive.format(code), timeout=20) as response:
            doc = html.fromstring(response.read())
        pages = {a.get('href') for a in doc.xpath('//a[contains(@href,"/medias/month/")]')}
        for page in sorted(pages):
            match = re.search(r'/month/(\d{2})/(?:\d{2}-)?(\d{2})\.html$', page)
            if match:
                year, month = 2000+int(match[1]), int(match[2])
                if 2017 <= year <= 2024 or (year, month) == (2025, 3):
                    yield 'medias', year, month, urljoin(BASE, page)


def acquire_references():
    items = {
        'medias_method': ('医療費の動向 調査概要', BASE+'/toukei/list/82-1a.html', 'html'),
        'medias_age_2024': ('令和6年度 医科医療費（電算処理分）年齢階級別参考資料',
                            BASE+'/topics/medias/year/24/dl/iryouhi_data_sankou.pdf','pdf'),
        'hospital_correction_2024_12': ('病院報告 令和6年12月分概数 正誤表',
                                       BASE+'/toukei/saikin/hw/iryosd/08/dl/seigo1_r0612.pdf','pdf'),
        'medias_2018_03_pdf': ('平成29年度3月号 概算医療費',
                               BASE+'/topics/medias/month/18/dl/gaisan_iryou_data_03.pdf','pdf'),
        'medias_2020_03_pdf': ('令和元年度3月号 概算医療費',
                               BASE+'/topics/medias/month/20/dl/gaisan_iryou_data_03.pdf','pdf'),
    }
    manifest = []
    for name,(title,url,fmt) in items.items():
        now = datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
        entry = dict(dataset='reference', issue=name, publisher='厚生労働省', page_url=url,
                     title=title, release_date='不明', source_url=url, retrieved_jst=now,
                     http_status='', bytes='', sha256='', local_path='', status='未取得', reason='',
                     reuse_terms=BASE+'/chosakuken/')
        try:
            with urlopen(url, timeout=20) as response:
                payload = response.read()
                entry['http_status'] = response.status
            if fmt == 'pdf' and not payload.startswith(b'%PDF-'):
                raise ValueError('invalid PDF signature')
            file = RAW / f'{name}.{fmt}'
            if file.exists() and file.read_bytes() != payload:
                raise ValueError('publisher bytes changed; existing raw retained')
            file.write_bytes(payload)
            entry.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                         local_path=str(file), status='取得済')
        except (OSError, ValueError) as exc:
            entry['reason'] = str(exc)
            entry['http_status'] = getattr(exc,'code',entry['http_status'])
        manifest.append(entry)
    return manifest


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    jobs = [('hospital', y, m, None) for y in range(2017, 2025) for m in range(1, 13)]
    jobs.extend(dict.fromkeys(medias_issues()))
    with ThreadPoolExecutor(max_workers=14) as pool:
        rows = list(pool.map(fetch, jobs))
    rows.extend(acquire_references())
    with (AUDIT / 'source_manifest.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()

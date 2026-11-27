"""Acquire bounded first-party and primary-study documents and record their hashes."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from urllib.request import urlopen
from urllib.error import URLError

SOURCES = {
    **{f'jna_{y}.pdf': 'https://www.nurse.or.jp/'+(
        f'nursing/home/publication/pdf/research/{n}.pdf' if n <= 99 else f'nursing/assets/{n}.pdf')
       for y,n in ((2017,93),(2018,94),(2019,95),(2020,96),(2021,97),(2022,99),(2023,100),(2024,101),(2025,102))},
    'seino_supplement.pdf':'https://pmc.ncbi.nlm.nih.gov/articles/instance/8986949/bin/41649_2021_194_MOESM1_ESM.pdf',
    'yan_supplement.docx':'https://pmc.ncbi.nlm.nih.gov/articles/instance/11027999/bin/KHVI_A_2337984_SM5674.docx',
    'iasr_sapporo.html':'https://id-info.jihs.go.jp/niid/ja/2019-ncov-e/9769-485d03.html',
    'iasr_kochi.html':'https://id-info.jihs.go.jp/niid/ja/2019-ncov-e/11569-512c01.html',
    'jna_errata_2018.pdf':'https://www.nurse.or.jp/nursing/home/publication/pdf/research/94_errata.pdf',
    'work_compensation.pdf':'https://www.mhlw.go.jp/content/001101040.pdf',
    'estat_employment_2024.pdf':'https://www.e-stat.go.jp/stat-search/file-download?fileKind=2&statInfId=000040306018',
    'jma_2022.pdf':'https://www.med.or.jp/dl-med/kinmu/202206kinmuikenko.pdf',
    'mhlw_2019.pdf':'https://www.mhlw.go.jp/content/10800000/000653217.pdf',
    **{f'pmc_{n}.html':f'https://pmc.ncbi.nlm.nih.gov/articles/PMC{n}/' for n in (10020069,8590925,11027999)},
}


def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')


def acquire(name_url, folder):
    name,url = name_url
    path = folder/name
    record = dict(filename=name,url=url,checked_at_jst=now())
    try:
        if path.exists():
            data = path.read_bytes()
            record['acquisition_mode'] = 'existing_local'
        else:
            with urlopen(url,timeout=25) as response:
                record.update(http_status=response.status, final_url=response.url)
                data = response.read()
            if name.endswith('.pdf') and not data.startswith(b'%PDF'):
                raise ValueError('PDF signature missing')
            if name.endswith('.docx') and not data.startswith(b'PK'):
                raise ValueError('DOCX signature missing')
            if name.startswith('pmc_') and b'citation_title' not in data:
                raise ValueError('article HTML metadata missing')
            with path.open('xb') as f:
                f.write(data)
            record.update(acquisition_mode='downloaded',acquired_at_jst=now())
        record.update(status='acquired',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    except (OSError, ValueError, URLError) as exc:
        record.update(status='failed',reason=str(exc))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('originals',type=Path)
    parser.add_argument('manifest',type=Path)
    args = parser.parse_args()
    args.originals.mkdir(exist_ok=True,parents=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(lambda pair: acquire(pair,args.originals), SOURCES.items()))
    with args.manifest.open('x') as f:
        json.dump(records,f,ensure_ascii=False,indent=2)
        f.write('\n')

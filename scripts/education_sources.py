"""Acquire official sources into a local, resumable cache."""
import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

MEXT = 'https://www.mext.go.jp'
SOURCES = {
    **{f'absence_{year}.pdf': MEXT + f'/component/a_menu/education/detail/__icsFiles/afieldfile/2019/10/25/1412082-{year-1988}.pdf' for year in (2017,2018)},
    **{f'errata_{year}.pdf': MEXT + f'/content/20230830-mxt_jidou01-000026371_{year-2016}.pdf' for year in (2017,2018)},
    'absence_history.pdf': MEXT + '/content/20260116-mxt_jidou02-100002753_2_2.pdf',
    **{f'ict_{id}.xlsx': f'https://www.e-stat.go.jp/stat-search/file-download?statInfId={id}&fileKind=0'
       for id in ('000032252977','000032252979','000040221895')},
}


def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')


def valid(name, data, mime):
    suffix = Path(name).suffix
    markers = {'.pdf': b'%PDF-', '.xlsx': b'PK\x03\x04', '.xls': bytes.fromhex('d0cf11e0a1b11ae1')}
    if suffix in markers:
        return mime not in ('text/html','application/json') and data.startswith(markers[suffix])
    if suffix=='.json':
        return mime!='text/html' and isinstance(json.loads(data),(dict,list))
    if suffix=='.html':
        return mime=='text/html' and bool(data.strip())
    return suffix=='.csv' and mime!='text/html' and b',' in data[:8192]


def acquire(cache, sources=SOURCES):
    cache.mkdir(parents=True,exist_ok=True)
    for name,url in sources.items():
        path=cache/name
        meta=cache/(name+'.json')
        entry=dict(source_id=Path(name).stem, filename=name, url=url,publisher='文部科学省',
                   checked_jst=now(),reuse_terms_status='資料別確認待ち')
        if path.exists() and meta.exists():
            saved=json.loads(meta.read_text())
            if saved['url']==url and saved['sha256']==hashlib.sha256(path.read_bytes()).hexdigest():
                yield {**saved,'cache_hit':True}
                continue
        if path.exists() or meta.exists():
            yield {**entry,'status':'cache_conflict'}
            continue
        errors=[]
        for attempt in range(3):
            try:
                with urlopen(url,timeout=35) as response:
                    mime=response.headers.get_content_type()
                    data=response.read()
                    entry.update(http_status=response.status,final_url=response.url,content_type=mime)
                if not valid(name,data,mime):
                    raise ValueError('invalid source format')
                completed = dict(entry,status='acquired', acquired_jst=now(), bytes=len(data),
                                 sha256=hashlib.sha256(data).hexdigest(),attempt_errors=errors)
                with tempfile.NamedTemporaryFile(dir=cache,delete=False) as tmp:
                    tmp.write(data)
                try:
                    os.link(tmp.name,path)
                finally:
                    os.unlink(tmp.name)
                meta.write_text(json.dumps(completed,ensure_ascii=False)+'\n')
                entry = completed
                break
            except (OSError,ValueError) as exc:
                errors.append(str(exc))
                if path.exists():
                    break
                if isinstance(exc,HTTPError):
                    entry['http_status']=exc.code
                    if exc.code not in (429,500,502,503,504):
                        break
                if attempt<2 and not isinstance(exc,ValueError):
                    time.sleep(2**attempt)
                elif isinstance(exc,ValueError):
                    break
        if entry.get('status')!='acquired':
            entry.update(status='failed',attempt_errors=errors)
        yield entry


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('cache',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.write_text(json.dumps(list(acquire(args.cache)),ensure_ascii=False,indent=2)+'\n')

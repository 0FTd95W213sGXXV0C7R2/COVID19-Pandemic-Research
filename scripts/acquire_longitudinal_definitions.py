"""Acquire primary sources for the longitudinal NDB and DPC audit."""
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

SCOPE = Path('non_covid_access/ndb_dpc_longitudinal')
BASE = 'https://www.mhlw.go.jp'
SOURCES = [
 ('r10_excluded.zip','第10回 医科診療行為 公費レセプト除外版',BASE+'/content/12400000/001495838.zip','不明'),
 ('ndb_faq.pdf','NDBオープンデータ FAQ 第10回版',BASE+'/content/12400000/001568663.pdf','不明'),
 ('fee_2024.pdf','医科診療報酬点数表 令和6年10月施行',BASE+'/content/10808000/001276106.pdf','不明'),
 ('coding.pdf','令和6年度DPC改定資料',BASE+'/content/12400000/001252076.pdf','不明'),
 ('fee_master.zip','医科診療行為全件マスター 2026年11月版','https://www.hpdx.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_01.files/s_ALL20261102.zip','2026-11-02（版日）'),
 ('dpc_2018.xlsx','診断群分類電子点数表 平成30年4月更新',BASE+'/file/06-Seisakujouhou-12400000-Hokenkyoku/0000204167.xlsx','2018-04-17（更新）'),
 ('dpc_2020.xlsx','診断群分類電子点数表 令和2年4月更新',BASE+'/content/12400000/001348059.xlsx','2020-04-21（更新）'),
 ('dpc_2022.xlsx','診断群分類電子点数表 令和4年正式版',BASE+'/content/12400000/001348044.xlsx','2022-03-18（更新）'),
 ('dpc_2024.xlsx','診断群分類電子点数表 令和6年正式版',BASE+'/content/12400000/001334364.xlsx','2024-04-16（更新）'),
 ('fee_code_reference.pdf','診療行為コード一覧','https://shinryohoshu.mhlw.go.jp/shinryohoshu/file/spec/20bt5_s_code.pdf','不明'),
]


def main():
    raw = Path('data/raw') / SCOPE
    audit = Path('data/audits') / SCOPE
    raw.mkdir(parents=True,exist_ok=True)
    audit.mkdir(parents=True,exist_ok=True)
    rows = []
    for name,title,url,published in SOURCES:
        record = dict(path='',title=title,publisher='医療情報基盤・診療報酬審査支払機構' if name=='fee_master.zip' else '厚生労働省',url=url,published=published,
                      acquired_jst=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds'),
                      sha256='',bytes='',status='failed',error='',reuse='再配布未確認（照合用ローカル保管）' if name=='fee_master.zip' else BASE+'/chosakuken/')
        try:
            with urlopen(url,timeout=45) as response:
                data = response.read()
            if not data.startswith(b'%PDF-' if name.endswith('.pdf') else b'PK\x03\x04'):
                raise ValueError('unexpected file signature')
            path = raw/name
            if path.exists() and path.read_bytes()!=data:
                raise ValueError('publisher bytes changed')
            path.write_bytes(data)
            record.update(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),status='acquired')
        except (OSError,ValueError) as exc:
            record['error'] = str(exc)
        rows.append(record)
    with (audit/'source_manifest.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


if __name__=='__main__':
    main()

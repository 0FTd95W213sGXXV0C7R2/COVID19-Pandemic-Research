"""Fetch bounded official documents and preserve restricted extracts outside Git."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import urljoin
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import html
from education_sources import acquire, now

TDB='https://www.tdb.co.jp'
TSR='https://www.tsr-net.co.jp'
WHITE='https://www.chusho.meti.go.jp/pamflet/hakusyo/2025/'
PAGES={
    'tdb_annual.html':TDB+'/report/bankruptcy/aggregation/3krjfg3s0uf/',
    'tdb_closure.html':TDB+'/report/economic/kyuhaigyo_kaisan2024/',
    'tsr_annual.html':TSR+'/news/status/detail/1200857_1610.html',
    'tsr_labor.html':TSR+'/data/detail/1200923_1527.html',
    'tsr_prices.html':TSR+'/data/detail/1200860_1527.html',
    'whitepaper.html':WHITE+'chusho/b1_1_8.html',
    'whitepaper.pdf':WHITE+'PDF/chusho/03Hakusyo_part1_chap1_web.pdf',
    'administrative.html':'https://www.chusho.meti.go.jp/koukai/chousa/tousan/index.html',
    'opening_rates.html':WHITE+'chusho/f12.html',
}
EMP=('10人未満','10人~50人未満','50人~100人未満','100人~300人未満','300人以上')
CAP=('個人事業主','100万円未満','100万円~1000万円未満','1000万円~5000万円未満','5000万円~1億円未満','1億円以上')
FORM=('会社更生法','破産','特別清算','民事再生法')
CAUSE=('販売不振','輸出不振','売掛金回収難','不良債権の累積','大企業の進出','技術、商品開発の遅れ',
       '新市場開拓の遅れ','開発途上国の追い上げ','業界不振','企業系列、下請の再編成','放漫経営',
       '新商品開発の失敗','設備投資の失敗','経営多角化の失敗','その他の経営計画の失敗',
       '経営者の病気、死亡','火災、その他の災害','人材の不足','労使の対立','立地条件の変化','過小資本','その他')


def norm(s):
    return unicodedata.normalize('NFKC',s).replace('〜','~').replace('⺠','民')


def number(s):
    return int(s.replace(',',''))


def pdf(path):
    return norm(subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)).split('\f')


def history(page):
    years=[]
    result={}
    annual={}
    for line in page.splitlines():
        headings=re.findall(r'(\d{4})年\(',line)
        if len(headings)==6:
            years=[int(y) for y in headings]
        m=re.fullmatch(r'\s*(合計|1[0-2]|[1-9])\s+([\d, ]+)\s*',line)
        if not m or not years:
            continue
        values=list(map(number,m[2].split()))
        if len(values)%2 or len(values)>12:
            raise ValueError(line)
        for i,value in enumerate(values[::2]):
            year=years[i]
            if 2017<=year<=2024:
                target,key=(annual,year) if m[1]=='合計' else (result,(year,int(m[1])))
                if key in target:
                    raise ValueError(('duplicate',key))
                target[key]=value
    if set(result)!={(y,m) for y in range(2017,2025) for m in range(1,13)}:
        raise ValueError('incomplete months')
    return result,annual


def category_table(page, labels):
    values={}
    if labels == CAP:
        page = page.split('個人事業主',1)[1]
        page = '個人事業主' + page.split('10人未満',1)[0]
    for label in labels:
        lines=re.findall(r'^\s*(?:[資本金別従業員数主因態様]\s+)?'+re.escape(label)+
                         r'\s+((?:[\d,]+\s+){8}[\d,]+)\s*$',page,re.M)
        if len(lines)!=1:
            raise ValueError((label,lines))
        nums=list(map(number,lines[0].split()))
        if sum(nums[:-1])!=nums[-1]:
            raise ValueError(('industry sum',label))
        values[label]=nums[-1]
    return values


def table_text(cache,name):
    doc=html.fromstring((cache/name).read_bytes().decode('utf-8',errors='replace'))
    return norm(' '.join(doc.text_content().split()))


def extract(cache):
    pages=pdf(cache/'tdb_data.pdf')
    months,years=history(pages[17])
    if any(sum(months[y,m] for m in range(1,13))!=years[y] for y in range(2017,2025)):
        raise ValueError('monthly/annual discrepancy')
    rows=[]
    def add(bk,provider,period,grain,category,value,source,location):
        rows.append(dict(item=bk,provider=provider,period=str(period),frequency=grain,
                         category=category,value=value,unit='件',source=source,locator=location))
    for (year,month),value in sorted(months.items()):
        add('BK11','TDB',f'{year}-{month:02}','month','全国倒産件数',value,'tdb_data.pdf','PDF p.18 月別推移')
    for year,value in sorted(years.items()):
        add('BK11','TDB',year,'year','全国倒産件数',value,'tdb_data.pdf','PDF p.18 合計行')
    for i,period,total in ((14,'2024',years[2024]),(15,'2024-12',months[2024,12])):
        for bk,labels in (('BK06',EMP),('BK07',CAP),('BK08',CAUSE),('BK09',FORM)):
            vals=category_table(pages[i],labels)
            if sum(vals.values())!=total:
                raise ValueError(('category sum',bk,period))
            for label,value in vals.items():
                add(bk,'TDB',period,'year' if i==14 else 'month',label,value,'tdb_data.pdf',f'PDF p.{i+1} 全国列')
    text=' '.join(pdf(cache/'tdb_closure.pdf')[0].split())
    found=re.search(r'6\s*万\s*(9019)\s*件',text)
    if not found:
        raise ValueError('closure total not found')
    add('BK10','TDB','2024','year','休廃業・解散',60000+int(found[1]),'tdb_closure.pdf','PDF p.1 本文')
    price=table_text(cache,'tsr_annual.html')
    m=re.search(r'「物価高」倒産は([\d,]+)件\(前年\s*([\d,]+)件\)',price)
    if not m:
        raise ValueError('TSR prices not found')
    for y,v in zip((2024,2023),m.groups()):
        add('BK08','TSR',y,'year','物価高倒産',number(v),'tsr_annual.html','年間の特徴')
    labor=table_text(cache,'tsr_labor.html')
    m=re.search(r'過去最多の([\d,]+)件',labor)
    if not m:
        raise ValueError('TSR labor not found')
    add('BK08','TSR','2024','year','人手不足関連倒産',number(m[1]),'tsr_labor.html','記事見出し')
    keys=[tuple(row[k] for k in ('item','provider','period','frequency','category')) for row in rows]
    if len(set(keys))!=len(keys) or any(row['value']<0 for row in rows):
        raise ValueError('duplicate or negative observation')
    return rows


def csv_file(path,rows):
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def write_extracts(dest,rows):
    csv_file(dest/'bankruptcy_long.csv',rows)
    series=defaultdict(dict)
    for row in rows:
        key=tuple(row[k] for k in ('item','provider','frequency','category','unit'))
        series[key][row['period']]=row['value']
    header=('item','provider','frequency','category','unit')
    periods=sorted({r['period'] for r in rows})
    csv_file(dest/'bankruptcy_wide.csv',[
        {**dict(zip(header,key)),**{p:values.get(p,'') for p in periods}}
        for key,values in sorted(series.items())])


def main():
    p=argparse.ArgumentParser()
    p.add_argument('private',type=Path)
    p.add_argument('audit',type=Path)
    a=p.parse_args()
    cache=a.private/'raw'
    a.audit.mkdir(parents=True,exist_ok=True)
    records=list(acquire(cache,PAGES))
    links={}
    parents={}
    for name in ('tdb_annual.html','tdb_closure.html'):
        doc=html.parse(cache/name)
        names=('tdb_report.pdf','tdb_data.pdf') if name=='tdb_annual.html' else ('tdb_closure.pdf',)
        hrefs=doc.xpath('//a[contains(@href,".pdf")]/@href')
        for target,href in zip(names,hrefs,strict=True):
            links[target]=urljoin(PAGES[name],href)
            parents[target]=PAGES[name]
    records.extend(acquire(cache,links))
    for r in records:
        name=r['filename']
        r.update(landing_url=parents.get(name,r['url']),publisher='帝国データバンク' if name.startswith('tdb')
                 else '東京商工リサーチ' if name.startswith('tsr') else '中小企業庁',
                 reuse_terms='公開再配布承認未確認。原本と明細は作業領域で保持',
                 publication_date='不明',revision_date='不明')
        if r['status']=='acquired':
            path=cache/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']:
                raise ValueError(name)
            if name.endswith('.html'):
                r['title']=html.fromstring(path.read_bytes().decode('utf-8',errors='replace')).xpath('string(//title)').strip()
            else:
                r['title']={'tdb_report.pdf':'全国企業倒産集計 2024年報・12月報',
                            'tdb_data.pdf':'全国企業倒産集計 2024年報・12月報 倒産動向データ編',
                            'tdb_closure.pdf':'全国企業「休廃業・解散」動向調査（2024年）訂正版'}[name]
    (a.audit/'source_manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    rows=extract(cache)
    write_extracts(a.private,rows)
    data=dict(verified_jst=now(),files=Counter(r['status'] for r in records),
              observations=Counter(r['item'] for r in rows),
              series={bk:len({(r['provider'],r['frequency'],r['category']) for r in rows if r['item']==bk})
                      for bk in ('BK06','BK07','BK08','BK09','BK10','BK11')},
              extracted_blank=0,duplicates=0,negative=0,monthly_annual_matches=8,
              category_national_matches=8,tdb_scope='負債1000万円以上の法的整理',
              cross_provider='TSRとTDBの差は測定母集団が異なるので一致判定対象外')
    with ZipFile(a.private/'bankruptcy_drive_package.zip','w',ZIP_DEFLATED) as bundle:
        for r in records:
            if r['status']=='acquired':
                bundle.write(cache/r['filename'],'raw/'+r['filename'])
        for path in (a.private/'bankruptcy_long.csv',a.private/'bankruptcy_wide.csv',a.audit/'source_manifest.json'):
            bundle.write(path,path.name)
    data['package_sha256']=hashlib.sha256((a.private/'bankruptcy_drive_package.zip').read_bytes()).hexdigest()
    (a.audit/'quality_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    main()

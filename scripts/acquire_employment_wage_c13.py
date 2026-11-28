"""C-13 official source acquisition and source-coordinate extraction."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from hashlib import sha256, file_digest
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import urljoin
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import html
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from education_sources import acquire, now

ESTAT = 'https://www.e-stat.go.jp'
MHLW = 'https://www.mhlw.go.jp'
STAT = 'https://www.stat.go.jp'
JOBS = ESTAT+'/stat-search/files?cycle=1&layout=dataset&page=1&tclass1=000001249728&toukei=00450222&tstat=000001020327'
ARCHIVE = STAT+'/data/roudou/rireki/gaiyou.html'
FLOWS = MHLW+'/toukei/list/9-23-1c.html'
YEARS = range(2017,2025)


def normalized(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip()


def job_links(doc):
    for item in doc.xpath('//article'):
        fields = item.xpath('.//a[@data-key="uid"]//span[@class="stat-separator"]/text()')
        links = item.xpath('.//a[contains(@href,"fileKind=0")]/@href')
        if len(fields)>=3 and fields[0]=='長期時系列表' and fields[1] in map(str,range(1,12)) and len(links)==1:
            yield int(fields[1]), fields[2], urljoin(ESTAT,links[0])


def period(year, token, fiscal=False):
    token = normalized(token)
    if not token:
        return ('fiscal_year' if fiscal else 'year'), str(year)
    m = re.fullmatch(r'(1[0-2]|[1-9])月',token)
    if m:
        return 'month', f'{year}-{int(m[1]):02}'
    q = re.fullmatch(r'(1|4|7|10)[〜~～-](3|6|9|12)月(?:期)?',token)
    if q and int(q[2])==int(q[1])+2:
        return 'quarter', f'{year}-Q{(int(q[1])+2)//3}'
    return None


def workbook_rows(path, family):
    book = load_workbook(path,read_only=True,data_only=True)
    try:
        for sheet in book:
            source = list(sheet.values)
            if family.startswith('pref') and not sheet.title.startswith('時系列表'):
                continue
            header = next((i for i,r in enumerate(source[:20]) if len(r)>2 and r[2]=='北海道'),None)
            if family.startswith('pref'):
                if header is None or set(source[header-1][2:49])!=set(range(1,48)):
                    raise ValueError(f'Prefecture codes not confirmed: {sheet.title}')
                for i,r in enumerate(source[header+1:],header+2):
                    first = re.fullmatch(r'((?:19|20)\d\d)年?',normalized(r[1] if family=='pref_annual' else r[0]))
                    if first:
                        year = int(first[1])
                    if i==header+2 and not first:
                        raise ValueError('Missing initial reference year')
                    p = period(year,r[1]) if family=='pref_quarter' and r[1] is not None else (
                        period(year,None) if family=='pref_annual' and first else None)
                    if p and year in YEARS:
                        for j in range(2,49):
                            yield record(path,sheet.title,i,j,p,str(source[header-1][j]).zfill(2),
                                         str(next((v for v in source[3] if v),sheet.title)),'%' if '第６表' in sheet.title else '千人','original',r[j])
                continue
            if not family.startswith('jobs'):
                continue
            names = next((i for i,r in enumerate(source[:35]) if any(normalized(v)=='西暦' for v in r)),None)
            if names is None:
                continue
            cols = source[names]
            date_col = next(i for i,v in enumerate(cols) if normalized(v)=='西暦')
            header_rows = source[:names+2]
            wide = family in {f'jobs_{i:02}' for i in range(2,9)}
            data_start = names+4 if family=='jobs_09' else names+2
            for i,r in enumerate(source[data_start:],data_start+1):
                date = re.fullmatch(r'(20\d\d)年(度)?',normalized(r[date_col]))
                if not date or int(date[1]) not in YEARS:
                    continue
                for j in range(date_col+(2 if wide else 3),len(r)):
                    token = cols[j] if wide else r[date_col+2]
                    if wide and not re.fullmatch(r'(?:1[0-2]|[1-9])月',normalized(token)):
                        continue
                    grain = period(int(date[1]),token,bool(date[2]))
                    if grain is None:
                        continue
                    context = [normalized(h[j]) for h in header_rows if j<len(h) and h[j] is not None]
                    if not context:
                        continue
                    adjustment = 'seasonally_adjusted' if any('季節調整' in h for h in context) else (
                        'original' if any(h in ('実数','原数値') for h in context) else 'unconfirmed')
                    if wide:
                        context = [normalized(source[0][0]),*(x for x in context if x in ('実数','季節調整値'))]
                    if family in ('jobs_09','jobs_11') and adjustment=='unconfirmed':
                        adjustment = 'seasonally_adjusted' if '季節調整値' in sheet.title else 'original'
                    unit = normalized(source[data_start-1][j])
                    yield record(path,sheet.title,i,j,grain,'', ' / '.join(context),unit,adjustment,r[j])
    finally:
        book.close()


def record(path,sheet,line,column,p,region,metric,unit,adjustment,value):
    return dict(source=path.name,sheet=sheet,cell=f'{get_column_letter(column+1)}{line}',
                frequency=p[0],period=p[1],region_code=region,metric=metric,unit=unit,
                adjustment=adjustment,raw='' if value is None else str(value),
                kind='blank' if value is None else 'numeric' if type(value) in (int,float) else 'symbol_or_text')


REASONS = ('休業者','勤め先や事業の都合','景気が悪かった','勤め先や事業の都合のその他',
           '自分や家族の都合','出産・育児','介護・看護','休暇',
           '自分や家族の都合のその他','その他（表注参照）')


def reason_rows(path, text):
    """Require six identical period sequences before selecting the three level blocks."""
    lines = text.split('\f')[0].splitlines()
    if not re.search(r'休業の理由別休業者',text):
        return []
    series = []
    year = None
    for i,line in enumerate(lines,1):
        m = re.search(r'(?:(20\d{2})年\s*)?(1|4|7|10)\s*[～~〜]\s*(3|6|9|12)月?\s+(.+?)\s*$',line)
        if not m or int(m[3])!=int(m[2])+2:
            continue
        if m[1]:
            year = int(m[1])
        cells = re.sub(r'▲\s*','-',m[4]).split()
        if year is None or len(cells)!=10 or any(not re.fullmatch(r'-?\d+|[-…]',v) for v in cells):
            continue
        series.append((i,f'{year}-Q{(int(m[2])+2)//3}',cells))
    count, remainder = divmod(len(series),6)
    if not count or remainder:
        return []
    groups = [series[j:j+count] for j in range(0,len(series),count)]
    periods = [v[1] for v in groups[0]]
    if len(set(periods))!=count or any([v[1] for v in group]!=periods for group in groups):
        return []
    return [record(path,'PDF p.1 理由別表',line,column,('quarter',p),'00',sex+' / '+metric,
                   '万人','original',int(v) if re.fullmatch(r'\d+',v) else v)
            for sex,group in zip(('男女計','男','女'),groups[::2])
            for line,p,vals in group for column,(metric,v) in enumerate(zip(REASONS,vals))]


def code_tables(path):
    doc = html.parse(path,html.HTMLParser(encoding='utf-8'))
    result = []
    for option in doc.xpath('//option[@data-code and @data-title]'):
        label = option.get('data-title')
        if re.fullmatch(r'20\d{2}年.*',label):
            continue
        result.append(dict(source=path.name,dimension=option.get('data-matter_id'),
                           code=option.get('data-code'),label=label))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True,exist_ok=True)
    raw = root/'raw'
    records = []
    extracted = []
    issues = []
    def get(specs):
        def fetch(spec):
            file,url,publisher,title,landing = spec
            row = next(acquire(raw,{file:url}))
            row.update(publisher=publisher,title=title,landing_url=landing,publication_date='不明')
            return row
        with ThreadPoolExecutor(max_workers=6) as pool:
            result = list(pool.map(fetch,specs))
        records.extend(result)
        return {r['filename']:r for r in result if r['status']=='acquired'}
    indexes = [('jobs_index.html',JOBS,'厚生労働省','職業安定業務統計 長期時系列表',JOBS),
               ('flows_index.html',FLOWS,'厚生労働省','雇用動向調査 結果の概要',FLOWS),
               ('labor_archive.html',ARCHIVE,'総務省統計局','労働力調査 過去の結果',ARCHIVE),
               ('absence_metadata.html',ESTAT+'/dbview?sid=0002060002','総務省統計局','労働力調査 基本集計 月次データベース',ESTAT+'/dbview?sid=0002060002')]
    available = get(indexes)
    definitions = []
    codes = []
    specs = []
    family = {}
    for name,id in [('pref_quarter','000031831380'),('pref_annual','000031952605')]:
        landing = ESTAT+f'/stat-search/files?stat_infid={id}'
        file = name+'.xlsx'
        family[file] = name
        specs.append((file,ESTAT+f'/stat-search/file-download?statInfId={id}&fileKind=0','総務省統計局','労働力調査 都道府県別モデル推計 '+name,landing))
        specs.append((name+'_listing.html',landing,'総務省統計局','都道府県別公表台帳',landing))
    if 'jobs_index.html' in available:
        jobs = html.parse(raw/'jobs_index.html',html.HTMLParser(encoding='utf-8'))
        for n,title,url in job_links(jobs):
            file = f'jobs_{n:02}.xlsx'
            family[file] = f'jobs_{n:02}'
            specs.append((file,url,'厚生労働省',title,JOBS))
    listings = {}
    if 'flows_index.html' in available:
        doc = html.parse(raw/'flows_index.html')
        names = ['平成29年','平成30年','令和元年','令和2年','令和3年','令和4年','令和5年','令和6年']
        for a in doc.xpath('//a[@href]'):
            title = normalized(a.text_content())
            if title in names:
                year = 2017+names.index(title)
                file = f'flows_{year}.html'
                listings[file] = year
                url = urljoin(FLOWS,a.get('href'))
                specs.append((file,url,'厚生労働省',f'{year}年雇用動向調査',FLOWS))
    if 'labor_archive.html' in available:
        doc = html.parse(raw/'labor_archive.html')
        for href in sorted(set(doc.xpath('//a[@href]/@href'))):
            if re.search(r'/dt/pdf/20(?:20|21|22|23)_[1-4]sankou\.pdf$',href):
                specs.append(('reason_'+Path(href).name,urljoin(ARCHIVE,href),'総務省統計局','労働力調査 詳細集計 追加参考表',ARCHIVE))
    wage = MHLW+'/toukei/itiran/roudou/monthly/dl/maikin-chinginnobiritsu.pdf'
    specs.append(('wage_method.pdf',wage,'厚生労働省','毎月勤労統計調査における賃金の算定方法について',wage))
    for id in ('000032189741','000032189777'):
        landing = ESTAT+f'/stat-search/files?stat_infid={id}'
        specs.append((f'wage_{id}.html',landing,'厚生労働省','毎月勤労統計調査 長期時系列表',landing))
    for name,url,title in (
        ('wage_symbols.pdf',ESTAT+'/stat-search/file-download?fileKind=2&statInfId=000031913619','実数・指数累積データにおける記号の見方'),
        ('wage_guide.pdf',MHLW+'/content/10700000/001770935.pdf','指数・実数累積ファイルの活用方法'),
        ('wage_index.csv',ESTAT+'/stat-search/file-download?statInfId=000032189777&fileKind=1','実数・指数累積データ 指数'),
    ):
        specs.append((name,url,'厚生労働省',title,ESTAT+'/stat-search/files?stat_infid=000032189777'))
    specs.append(('wage_code.html',ESTAT+'/dbview?sid=0003138104','厚生労働省','毎月勤労統計 実質賃金 指数及び増減率',ESTAT+'/dbview?sid=0003138104'))
    acquired = get(specs)
    flows = []
    for file,year in listings.items():
        if file not in acquired:
            continue
        page = acquired[file]['url']
        doc = html.parse(raw/file)
        links = [a.get('href') for a in doc.xpath('//a[@href]') if '入職と離職の推移' in a.text_content()]
        if len(links)==1:
            flows.append((f'flows_{year}.pdf',urljoin(page,links[0]),'厚生労働省',f'{year}年 入職と離職の推移',page))
    acquired.update(get(flows))
    acquired.update(available)
    for r in records:
        if r['status']=='acquired':
            path = raw/r['filename']
            if sha256(path.read_bytes()).hexdigest()!=r['sha256']:
                raise ValueError(f'Source hash mismatch: {path.name}')
            if path.suffix=='.html':
                text = ' '.join(html.parse(path).getroot().text_content().split())
                date = re.search(r'公開（更新）日\s*(20\d\d-\d\d-\d\d)',text)
                if date:
                    r['publication_date'] = date[1]
    for file in acquired:
        if file=='wage_index.csv':
            with (raw/file).open(encoding='cp932',newline='') as stream:
                reader = csv.DictReader(stream)
                metrics = ('現金給与総額','実質賃金指数（現金給与総額）')
                for line,r in enumerate(reader,2):
                    if r['産業分類'].strip()!='TL' or r['規模']!='T' or r['就業形態']!='0':
                        continue
                    year = int(r['年'])
                    token = r['月']
                    if year not in YEARS:
                        continue
                    p = (('year',str(year)) if token=='CY' else
                         ('fiscal_year',str(year)) if token=='FY' else
                         ('quarter',f'{year}-{token}') if re.fullmatch(r'Q[1-4]',token) else
                         ('month',f'{year}-{token}') if re.fullmatch(r'0[1-9]|1[0-2]',token) else None)
                    if p is None:
                        continue
                    for metric in metrics:
                        v = r[metric]
                        row = record(raw/file,'CSV',line,reader.fieldnames.index(metric),p,'00',
                                     r['種別']+' / TL / T / 0 / '+metric,
                                     '指数' if r['種別']=='指数' else '未確認','unconfirmed',v or None)
                        if re.fullmatch(r'-?\d+(?:\.\d+)?',v):
                            row['kind']='numeric'
                        extracted.append(row)

        path = raw/file
        if path.suffix=='.xlsx':
            try:
                with ZipFile(path) as z:
                    if z.testzip() or 'xl/workbook.xml' not in z.namelist():
                        raise ValueError('Broken XLSX')
                extracted.extend(workbook_rows(path,family[file]))
            except ValueError as e:
                issues.append(dict(file=file,error=str(e)))
        if file in ('wage_code.html','absence_metadata.html'):
            codes.extend(code_tables(path))
        if path.suffix=='.pdf':
            text = subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
            if file.startswith('flows_'):
                year = int(path.stem[-4:])
                block = re.search(r'常用労働者の動き[（(]率[）)](.+?)(?:前年差|\f|$)',text,re.S)
                m = None
                locator = 'PDF p.1 表1-2'
                if block:
                    target = re.search(fr'[（(]{year}[）)](.*?)(?=[（(]{year-1}[）)]|$)',block[1],re.S)
                    m = re.search(r'^\s*計\s+([\d.]+)\s+([\d.]+)',target[1],re.M) if target else None
                if not m and year<2024:
                    locator = 'PDF p.1 表1'
                    m = re.search(r'^\s*計\s+(?:[\d,.]+\s+){3}([\d.]+)\s+([\d.]+)\s+[-\d.]+',text.split('\f')[0],re.M)
                if m:
                    for metric,v in zip(('入職率','離職率'),m.groups()):
                        row = record(path,locator,1,0,('year',str(year)),'00',metric,'%', 'original',float(v))
                        row.update(cell='計 / '+metric,raw=v)
                        extracted.append(row)
            elif file.startswith('reason_'):
                extracted.extend(reason_rows(path,text))
            elif file.startswith(('wage_method','wage_guide','wage_symbols')):
                for i,page in enumerate(text.split('\f'),1):
                    for line in page.splitlines():
                        if any(term in line for term in ('持家の帰属家賃を除く総合','基準年','2020 年','産業分類コード','TL','単位')):
                            definitions.append(dict(source=file,page=i,evidence=line.strip()))
    fields = ('source','sheet','cell','frequency','period','region_code','metric','unit','adjustment','raw','kind')
    with (root/'observations.csv').open('x',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(extracted)
    def save(file,data):
        with (root/file).open('x',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
    save('source_manifest.json',records)
    save('wage_definition_evidence.json',definitions)
    save('classification_codes.json',codes)
    counts = Counter()
    periods = defaultdict(set)
    for row in extracted:
        group = row['source'],row['frequency'],row['adjustment']
        counts[group] += 1
        periods[group].add(row['period'])
    keys = [(r['source'],r['sheet'],r['cell']) for r in extracted]
    duplicate_groups = defaultdict(set)
    for row in extracted:
        if row['source'].startswith('reason_'):
            duplicate_groups[(row['period'],row['metric'])].add(row['raw'])
    prior = Path(__file__).resolve().parents[1]/'data/audits/rebuild_2026/healthcare_worker_20261127'
    prior_sources = {r['filename']:sum(r['url'].split('statInfId=')[-1].split('&')[0] in p.read_text(errors='replace')
                                     for p in prior.glob('*.json'))
                     for r in records if 'statInfId=' in r['url']}
    summary = dict(executed_jst=now(),acquisition=dict(Counter(r['status'] for r in records)),
                   source_overlap_mentions=prior_sources,
                   reason_unique_period_metric=len(duplicate_groups),
                   reason_revision_candidates=sum(len(v)>1 for v in duplicate_groups.values()),
                   rows=len(extracted),kinds=dict(Counter(r['kind'] for r in extracted)),
                   coordinate_duplicates=len(keys)-len(set(keys)),extraction_issues=issues,
                   coverage=[dict(source=k[0],frequency=k[1],adjustment=k[2],rows=n,
                                  periods=len(periods[k]))
                             for k,n in sorted(counts.items())],
                   sources_without_observations=sorted(set(acquired)-{r['source'] for r in extracted}),
                   independent_extraction='未実施', prior_row_overlap='未照合。医療従事者系列は別母集団・版を含む')
    save('quality_audit.json',summary)
    package = root/'employment_wage_c13.zip'
    members = [*(raw/r['filename'] for r in records if r['status']=='acquired'),
               *root.glob('*.json'),root/'observations.csv']
    hashes = {p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in members}
    with ZipFile(package,'x',ZIP_DEFLATED) as z:
        for p in members:
            z.write(p,p.relative_to(root))
        z.writestr('internal_sha256.json',json.dumps(hashes,indent=2))
    verify(package)
    with package.open('rb') as stream:
        save('package_verification.json',dict(bytes=package.stat().st_size,sha256=file_digest(stream,'sha256').hexdigest(),
                                              verified_members=len(hashes),crc='pass'))
    print(json.dumps({k:summary[k] for k in ('acquisition','rows','kinds','coordinate_duplicates')},ensure_ascii=False))


def verify(path):
    with ZipFile(path) as z:
        hashes = json.loads(z.read('internal_sha256.json'))
        if (z.testzip() is not None or len(z.namelist())!=len(hashes)+1
                or set(z.namelist())!=set(hashes)|{'internal_sha256.json'}):
            raise ValueError('ZIP inventory or CRC mismatch')
        for member,expected in hashes.items():
            with z.open(member) as stream:
                if file_digest(stream,'sha256').hexdigest()!=expected:
                    raise ValueError(f'ZIP SHA-256 mismatch: {member}')
    return len(hashes)


if __name__=='__main__':
    main()

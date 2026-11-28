"""Reconstruct source coordinates and package a provisional C-14 audit."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
from hashlib import sha256, file_digest
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import html
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from acquire_employment_wage_c13 import ESTAT, normalized, period, verify
from education_sources import acquire, now

CATALOG = ESTAT+'/stat-search/files?tclass=000001226526&cycle=0'
C13_SHA = '26caee061d3da1105aa06d2762a3a717eddde650f248a58758132dd3ee2f11b8'
NUM = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)')
YEARS = set(range(2017,2025))


def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream,'sha256').hexdigest()


def save(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def wage_period(year, token):
    if token in ('CY','FY'):
        return ('year' if token=='CY' else 'fiscal_year'),str(year)
    if re.fullmatch(r'Q[1-4]|H[12]|0[1-9]|1[0-2]',token):
        granularity = {'Q':'quarter','H':'half_year'}.get(token[0],'month')
        return granularity,f'{year}-{token}'
    return 'unknown',f'{year}:{token}'


def wage_rows(path, item):
    text = path.read_bytes().decode('cp932')
    independent = iter(csv.reader(io.StringIO(text)))
    headers = next(independent)
    for line, row in enumerate(csv.DictReader(io.StringIO(text)),2):
        original = next(independent)
        if not row['年'] or not row['年'].isdigit() or int(row['年']) not in YEARS:
            continue
        if len(original)!=len(headers):
            raise ValueError(f'CSV width {path.name}:{line}')
        kind,year,token,industry,size,employment = (x.strip() for x in original[:6])
        freq, date = wage_period(year,token)
        for col,metric in enumerate(headers[6:],6):
            raw = row[metric]
            if raw!=original[col]:
                raise ValueError(f'CSV coordinate mismatch {path.name}:{line}:{col+1}')
            unit = 'index_2020_100' if kind=='指数' else 'unconfirmed'
            if kind=='実数' and metric in ('現金給与総額','きまって支給する給与','所定内給与','所定外給与','特別給与'):
                unit = '円'
            if kind.startswith('伸び率') and ('給与' in metric or '実質賃金指数' in metric):
                unit = '%'
            if metric in ('入職率','離職率','パートタイム労働者比率'):
                unit = '%' if kind=='実数' else 'percentage_point' if kind.startswith('伸び率') else unit
            nominal_real = ('real' if '実質賃金' in metric else 'nominal' if '給与' in metric else 'not_applicable')
            yield (item,path.name,'CSV',f'{get_column_letter(col+1)}{line}',freq,date,metric,unit,
                   'unconfirmed',kind,industry,size,employment,nominal_real,raw,'csv_readback')


def xml_values(archive, index):
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    root = ET.fromstring(archive.read(f'xl/worksheets/sheet{index}.xml'))
    return {c.attrib['r']:c.findtext(ns+'v') for c in root.iter(ns+'c')
            if c.get('t','n')=='n' and c.find(ns+'v') is not None}


def verify_cell(independent, coordinate, value):
    return coordinate in independent and float(independent[coordinate])==float(value)


def reference_year(raw):
    text = normalized(raw)
    western = re.fullmatch(r'((?:19|20)\d{2})(?:年(度)?)?',text)
    if western:
        return int(western[1]),bool(western[2])
    era = re.fullmatch(r'(平成|令和)\s*(元|\d{1,2})\s*年(度)?',text)
    if era:
        return {'平成':1988,'令和':2018}[era[1]]+(1 if era[2]=='元' else int(era[2])),bool(era[3])
    return None


def labor_rows(path):
    book = load_workbook(path,read_only=True,data_only=True)
    try:
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('XLSX CRC')
            for index,sheet in enumerate(book,1):
                data = list(sheet.values)
                if not data or re.search('注|Notes|沖縄県除く|季節指数',sheet.title,re.I):
                    continue
                independent = xml_values(archive,index)
                year = None
                for line,row in enumerate(data,1):
                    if len(row)<3:
                        continue
                    first = normalized(row[0])
                    update = reference_year(first)
                    if update:
                        year,fiscal = update
                    elif first and ('年' in first or not re.fullmatch(r'\d{1,2}',first)):
                        year = None
                    token = re.sub(r'\s+','',normalized(row[1]))
                    stamp = period(year,token,fiscal) if year in YEARS else None
                    if stamp is None or (not token and not update):
                        continue
                    # Rows with an explicit date and numerical observations only.
                    if not any(type(v) in (int,float) for v in row[2:]):
                        continue
                    for col,value in enumerate(row[2:],2):
                        if value is None:
                            continue
                        if col==2 and isinstance(value,str) and re.fullmatch(r'[A-Za-z. ]+',value):
                            continue
                        cell = f'{get_column_letter(col+1)}{line}'
                        attrs = ' / '.join(dict.fromkeys(normalized(h[col]) for h in data[:9]
                                                 if col<len(h) and isinstance(h[col],str) and normalized(h[col])))
                        adjust = ('seasonally_adjusted' if '季節調整' in sheet.title else
                                  'original' if '原数値' in sheet.title else 'unconfirmed')
                        unit = '%' if re.search(r'[%％]',attrs) else 'unconfirmed'
                        check = ('ooxml_match' if verify_cell(independent,cell,value) else 'ooxml_mismatch'
                                 if type(value) in (int,float) else 'symbol_unverified')
                        yield ('C11_candidate',path.name,sheet.title,cell,*stamp,attrs,unit,adjust,
                               '', '', '', '', 'not_applicable',str(value),check)
    finally:
        book.close()


FIELDS = ('family','source','sheet','cell','frequency','period','metric','unit','adjustment',
          'source_kind','industry','size','employment','nominal_real','raw','verification')


def c13_rows(previous):
    for r in csv.DictReader(io.StringIO(previous.read('observations.csv').decode())):
        yield ('C13',r['source'],r['sheet'],r['cell'],r['frequency'],r['period'],r['metric'],
               r['unit'],r['adjustment'],'','','','','',r['raw'],'preserved_previous')
    for r in csv.DictReader(io.StringIO(previous.read('followup/absence_monthly.csv').decode())):
        yield ('C13',r['source'],'DB',r['coordinate'],r['frequency'],r['period'],'07 / '+r['sex_code'],
               r['unit'],r['adjustment'],'','','','','',''+r['raw'],'prior_independent_readback')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('baseline',type=Path)
    p.add_argument('output',type=Path)
    a = p.parse_args()
    root = a.output
    root.mkdir(parents=True,exist_ok=True)
    if (root/'employment_wage_c14.zip').exists():
        raise FileExistsError('Use a new output directory')
    raw = root/'raw'
    verify(a.baseline)
    baseline_sha = digest(a.baseline)
    manifest = list(acquire(raw,{'labor_catalog.html':CATALOG}))
    specs = []
    if manifest[0]['status']=='acquired':
        for article in html.parse(raw/'labor_catalog.html').xpath('//article'):
            links = article.xpath('.//a[contains(@href,"fileKind=0")]/@href')
            if len(links)==1 and (m:=re.search(r'statInfId=(\d+)',links[0])):
                specs.append((f'lfs_{m[1]}.xlsx',ESTAT+links[0],' '.join(article.text_content().split()),'総務省統計局'))
    specs.append(('wage_real.csv',ESTAT+'/stat-search/file-download?statInfId=000032189776&fileKind=1',
                  '毎月勤労統計 実数・指数累積データ 実数','厚生労働省'))
    def fetch(spec):
        n,u,t,publisher = spec
        return dict(next(acquire(raw,{n:u})),title=t,publisher=publisher,
                    publication_date=(re.search(r'公開（更新）日 (\d{4}-\d\d-\d\d)',t) or ['','不明'])[1])
    with ThreadPoolExecutor(max_workers=6) as pool:
        manifest.extend(pool.map(fetch,specs))

    stats = Counter()
    duplicate_count = Counter()
    issues = []
    coord_seen = set()
    observed_periods = defaultdict(set)
    variables = set()
    c13_keys = defaultdict(list)
    historical = Path(__file__).resolve().parents[1]/'data/audits/rebuild_2026/healthcare_worker_20261127/monthly_labour_longitudinal_acquisition.json'
    legacy = json.loads(historical.read_text())['sources'] if historical.exists() else {}
    with ZipFile(a.baseline) as previous:
        old_manifest = json.loads(previous.read('source_manifest.json'))
        extra_manifest = json.loads(previous.read('followup/source_manifest_addendum.json'))
        manifest[0].update(publisher='総務省統計局',title='労働力調査 基本集計 長期時系列データ',publication_date='不明')
        original_index = next(r for r in old_manifest if r['filename']=='wage_index.csv')
        index_path = raw/'wage_index.csv'
        if not index_path.exists():
            index_path.write_bytes(previous.read('raw/wage_index.csv'))
        if digest(index_path)!=original_index['sha256']:
            raise ValueError('C13 wage index hash mismatch')
        manifest.append(original_index)
        old_keys = {r['sha256'] for r in old_manifest+extra_manifest if r.get('status')=='acquired'}
        for r in manifest:
            if r['status']=='acquired' and digest(raw/r['filename'])!=r['sha256']:
                raise ValueError(f"SHA-256 mismatch: {r['filename']}")
        with gzip.open(root/'analysis_candidates.csv.gz','wt',encoding='utf-8',newline='') as out, \
             gzip.open(root/'exclusions.csv.gz','wt',encoding='utf-8',newline='') as exc, \
             gzip.open(root/'duplicates.csv.gz','wt',encoding='utf-8',newline='') as dup:
            writers = [csv.writer(f) for f in (out,exc,dup)]
            writers[0].writerow(FIELDS)
            writers[1].writerow((*FIELDS,'reason'))
            writers[2].writerow(('kind','source','sheet','cell','reason'))
            def accept(rows):
                for row in rows:
                    family,source,sheet,cell,freq,date,metric,unit,adjust,kind,industry,size,form,price,value,check = row
                    numeric = bool(NUM.fullmatch(value))
                    stats[family,'rows'] += 1
                    stats[family,'numeric' if numeric else 'blank' if not value else 'symbol'] += 1
                    stats[family,check] += 1
                    observed_periods[family,freq].add(date)
                    key = (source,sheet,cell)
                    if family=='C13' and source=='wage_index.csv':
                        c13_keys[key].append((date,value))
                    if key in coord_seen:
                        prior = c13_keys.get(key)
                        status = ('same_coordinate_equal' if prior and (date,value) in prior else
                                  'same_coordinate_conflict' if prior else 'same_coordinate_unresolved')
                        duplicate_count[status] += 1
                        writers[2].writerow((status,source,sheet,cell,'同一原表の座標'))
                        if prior and (date,value) not in prior:
                            writers[1].writerow((*row,'coordinate_conflict'))
                            stats[family,'excluded'] += 1
                            continue
                    coord_seen.add(key)
                    variables.add((family,source,sheet,metric,unit,adjust,kind,industry,size,form,price))
                    if (not numeric or check in ('ooxml_mismatch','preserved_previous') or unit=='unconfirmed'
                            or freq=='unknown' or family in ('WC01','WC02') and adjust=='unconfirmed'):
                        reason = ('non_numeric' if not numeric else 'coordinate_mismatch' if check=='ooxml_mismatch'
                                  else 'classification_or_independent_check_pending')
                        writers[1].writerow((*row,reason))
                        stats[family,'excluded'] += 1
                    else:
                        writers[0].writerow(row)
                        stats[family,'candidate'] += 1
            accept(c13_rows(previous))
            for r in manifest:
                if r['status']!='acquired':
                    continue
                source = raw/r['filename']
                try:
                    if source.suffix=='.xlsx' and r['sha256'] not in old_keys:
                        accept(labor_rows(source))
                    elif source.name in ('wage_real.csv','wage_index.csv'):
                        accept(wage_rows(source,'WC01' if source.name=='wage_real.csv' else 'WC02'))
                except (ValueError,KeyError,IndexError) as error:
                    issues.append(dict(source=source.name,error=str(error)))
            # Distinguish distinct-publication reason cells with the same defined semantic axes.
            reasons = defaultdict(list)
            for row in c13_rows(previous):
                if row[1].startswith('reason_'):
                    reasons[row[5],row[6]].append(row)
            for group in reasons.values():
                if len({r[1] for r in group})>1:
                    kind = 'cross_publication_conflict' if len({r[-2] for r in group})>1 else 'cross_publication_equal'
                    duplicate_count[kind] += 1
                    for row in group:
                        writers[2].writerow((kind,*row[1:4],'四半期・性別・理由同一。公表版は保持'))
        with gzip.open(root/'variable_inventory.csv.gz','wt',encoding='utf-8',newline='') as f:
            csv.writer(f).writerows([('family','source','sheet','metric','unit','adjustment','source_kind',
                                      'industry','size','employment','nominal_real'),*sorted(variables)])
        old_hash_values = {k:v.get('sha256') for k,v in legacy.items()}
        qa = dict(executed_jst=now(),baseline_sha256=baseline_sha,exact_c13_baseline=baseline_sha==C13_SHA,
                  requested_cells={'C11':52795,'C12':1206046,'C13':89938,'total':1348779},
                  observed={f:{k:n for (family,k),n in stats.items() if family==f} for f in sorted({f for f,_ in stats})},
                  exact_legacy_c11_c12_inventory='未確認。旧バッチの明細・原資料対応台帳を確認できず',
                  prior_wage_source_hashes={k:dict(old=old_hash_values.get(k),new=next(
                      (r.get('sha256') for r in manifest if r['filename']==name),None))
                      for k,name in [('000032189776','wage_real.csv'),('000032189777','wage_index.csv')]},
                  coverage=[dict(family=f,frequency=k,count=len(v),first=min(v),last=max(v))
                            for (f,k),v in sorted(observed_periods.items())],
                  duplicates=dict(duplicate_count),issues=issues,
                  c13_followup_preserved=['69版間差','2020-03男女計差','未取得15四半期'],
                  continuity={'labor':'2020年国勢調査への切替。原表見出し・版は保持、横断接続は保留',
                              'WC02':'C13収録版2020年平均=100。増減率と指数・名目と実質を分離',
                              'missing':'空欄・記号は補完しない。行の未収録はCSVの空欄とは別'},
                  analysis_status='候補。定義・版・頻度の横断結合は保留')
        save(root/'quality_audit.json',qa)
        save(root/'source_manifest.json',{'c11_c12_current':manifest,'c13_original':old_manifest,'c13_followup':extra_manifest})
        package = root/'employment_wage_c14.zip'
        members = [*sorted(root.glob('*.gz')),root/'quality_audit.json',root/'source_manifest.json',a.baseline,
                   *(raw/r['filename'] for r in manifest if r['status']=='acquired')]
        with ZipFile(package,'x',ZIP_DEFLATED) as z:
            hashes = {}
            for path in members:
                member = ('previous/c13_integrated.zip' if path==a.baseline else path.relative_to(root).as_posix())
                z.write(path,member)
                hashes[member] = digest(path)
            z.writestr('internal_sha256.json',json.dumps(hashes))
        count = verify(package)
        save(root/'package_verification.json',dict(bytes=package.stat().st_size,sha256=digest(package),crc='pass',members=count))
        print(json.dumps(qa,ensure_ascii=False))


if __name__=='__main__':
    main()

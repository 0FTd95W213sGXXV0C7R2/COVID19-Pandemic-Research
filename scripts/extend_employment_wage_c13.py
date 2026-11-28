"""Extend a verified C-13 ZIP without changing its original members."""
import argparse
import base64
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
from hashlib import sha256, file_digest
import io
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import html

from acquire_employment_wage_c13 import ESTAT, MHLW, STAT, YEARS, normalized, verify
from education_sources import acquire, now

SID = '?sid=0002060002'
DB = ESTAT+'/dbview'
MODEL = DB+'/api_get_model'+SID
RESULT = DB+'/api_get_result'+SID
CODES = {'matter18':'01','matter3':'000','matter5':'07','matter6':'00','matter1':'00000'}
SEX = {'0':'総数','1':'男','2':'女'}
CATALOG = ESTAT+'/stat-search/files?page=1&layout=datalist&toukei=00200531&tstat=000001226583&cycle=2&tclass1=000001226833&tclass2=000001226861&tclass3val=0'
MONTHS = {f'{y}-{m:02}' for y in YEARS for m in range(1,13)}
BASE_SHA = 'eda32d11903e395103b2cf9ed37927f190e6dfec39f7dba57869bed58d3f9bab'


def query(model, sex):
    request = {k:v for k,v in model.items() if k not in ('matters','use_record')}
    request.update(mode='table',inputNumberOfRows=100,inputNumberOfCols=10,movementId=0)
    groups = {key:[] for key in ('rows','cols','tops')}
    selected = dict(CODES,matter4=sex)
    for key,axis in model['matters'].items():
        if key not in selected and key!='matter2':
            raise ValueError(f'Unrecognized official axis {key}')
        entries = [v for v in axis['listData'].values()
                   if (v['code']==selected[key] if key in selected
                       else re.fullmatch(r'20(?:1[789]|2[0-4])年\d{1,2}月',v['name']))]
        if len(entries)!=(96 if key=='matter2' else 1):
            raise ValueError(f'Incomplete official axis {key}')
        target = {k:axis[k] for k in ('matterId','tableName','dispTableName','positionNum')}
        target.update(listData=[{a:v.get(a) for a in ('name','code','explanation')} for v in entries],
                      allSelected=0)
        groups[axis['position']+'s'].append(target)
    for key,entries in groups.items():
        request[key] = base64.b64encode(gzip.compress(json.dumps(entries,ensure_ascii=False).encode())).decode()
    request['apiTops'] = request['tops']
    return request


def monthly_rows(response, sex):
    args = response['requestData']
    if [args.get(f'etcItem{i}') for i in range(1,6)]!=['01','000',sex,'07','00000'] or args.get('colItemList1')!='00':
        raise ValueError('Response classification mismatch')
    table = html.fromstring(response['table'])
    rows = []
    for tr in table.xpath('.//tr[td]'):
        title = tr.xpath('./th[@data-unique]')
        cells = tr.xpath('./td')
        if len(title)!=1 or len(cells)!=1:
            raise ValueError('Unexpected table coordinates')
        m = re.fullmatch(r'(20\d{2})年(\d{1,2})月',title[0].text_content().strip())
        if not m:
            raise ValueError('Unrecognized month')
        period = f'{m[1]}-{int(m[2]):02}'
        time_code = title[0].get('data-unique')
        month = f'{int(m[2]):02}'
        if time_code!=f'{m[1]}00{month}{month}':
            raise ValueError(f'Time coordinate mismatch: {time_code} / {period}')
        raw = cells[0].text_content().strip()
        if not re.fullmatch(r'\d+',raw):
            raise ValueError(f'Unexpected observation symbol: {raw}')
        rows.append(dict(table_id='0002060002',period=period,time_code=time_code,sex_code=sex,sex=SEX[sex],
                         employment_status='07',industry='000',age='00',region='00000',measure='01',
                         frequency='month',adjustment='original',unit='万人',raw=raw,
                         source=f'absence_{sex}.json',coordinate=f'tr[{time_code}]/td[1]'))
    if len(rows)!=96 or {r['period'] for r in rows}!=MONTHS:
        raise ValueError('Monthly coverage is not exactly 96 unique months')
    return rows


def csv_text(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def revision_candidates(rows, evidence):
    groups = defaultdict(list)
    for row in rows:
        if row['source'].startswith('reason_'):
            groups[row['period'],row['metric']].append(row)
    result = []
    for (period,metric),group in sorted(groups.items()):
        if len({r['raw'] for r in group})<2:
            continue
        year = int(period[:4])
        options = []
        for r in group:
            notice = evidence[r['source']]
            if year in notice['revised_years']:
                options.append(r)
        candidate = max(options,key=lambda r:evidence[r['source']]['release']) if options else None
        result.append(dict(period=period,metric=metric,versions=json.dumps([
            {k:r[k] for k in ('source','sheet','cell','raw')} for r in group],ensure_ascii=False),
            candidate_source=candidate['source'] if candidate else '',
            candidate_raw=candidate['raw'] if candidate else '',
            rationale='当該年を明記した新ベンチマーク補正注記。差分の個別原因は未確定' if candidate
            else '当該年を明記した補正根拠なし。公表時点・定義差等は個別未確定'))
    return result


def reason_evidence(z, manifest):
    out = {}
    for row in manifest:
        name = row['filename']
        if row['status']!='acquired' or not name.startswith('reason_'):
            continue
        text = normalized(subprocess.run(['pdftotext','-layout','-','-'],input=z.read('raw/'+name),
                                        capture_output=True,check=True).stdout.decode())
        first = text.split('\f')[0]
        m = re.search(r'追加参考表の\s*(20\d{2})\s*年(?:から\s*(20\d{2})\s*年まで)?',first)
        stamp = re.search(r'令\s*和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日',first)
        years = list(range(int(m[1]),int(m[2] or m[1])+1)) if m and 'ベンチマーク' in first and '遡及' in first else []
        out[name] = dict(revised_years=years,release=f'{2018+int(stamp[1])}-{int(stamp[2]):02}-{int(stamp[3]):02}'
                         if stamp else '不明',definition_change='原表脚注の版間同等性は未確定',url=row['url'])
    return out


def overlap(new, prior):
    """Compare a prior CSV explicitly mapped to the same official coordinates."""
    fields = ('table_id','time_code','sex_code','employment_status','industry','age','region','measure','unit')
    counts = Counter()
    def index(rows):
        result = {}
        for r in rows:
            k = tuple(r[f] for f in fields)
            if k in result:
                raise ValueError('Duplicate comparison coordinate')
            result[k] = r['raw']
        return result
    left,right = index(new),index(prior)
    for k in left.keys() & right.keys():
        counts['matching' if left[k]==right[k] else 'different'] += 1
    counts.update(new_only=len(left.keys()-right.keys()),prior_only=len(right.keys()-left.keys()))
    return dict(counts)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('baseline',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--prior',type=Path,help='prior CSV mapped to the official monthly coordinate fields')
    a = p.parse_args()
    output = a.output
    output.mkdir(exist_ok=False,parents=True)
    raw = output/'raw'
    specs = {
        'absence_model.json':MODEL,
        'reason_catalog.html':CATALOG,
        'results_index.html':STAT+'/data/roudou/2.html',
        'benchmark.pdf':STAT+'/data/roudou/pdf/10.pdf',
        'wage_rebase.pdf':MHLW+'/content/10700000/001770931.pdf',
    }
    records = list(acquire(raw,specs))
    for r in records:
        r.update(publisher='厚生労働省' if r['filename']=='wage_rebase.pdf' else '総務省統計局',
                 publication_date='不明')
    additions = []
    model = raw/'absence_model.json'
    if model.exists():
        for sex in SEX:
            name = f'absence_{sex}.json'
            params = query(json.loads(model.read_text()),sex)
            record = dict(filename=name,url=RESULT,landing_url=DB+SID,publisher='総務省統計局',
                          publication_date='DB表示版・更新日は未確認',sex_code=sex,checked_jst=now())
            try:
                with urlopen(Request(RESULT,data=urlencode(params).encode()),timeout=45) as resp:
                    data = resp.read()
                    record.update(http_status=resp.status,bytes=len(data),sha256=sha256(data).hexdigest())
                (raw/name).write_bytes(data)
                additions.extend(monthly_rows(json.loads(data),sex))
                record.update(status='acquired',acquired_jst=now())
            except (OSError,ValueError,KeyError) as exc:
                record.update(status='pending',error=str(exc))
            records.append(record)

    if additions:
        (output/'absence_monthly.csv').write_text(csv_text(additions))
    verify(a.baseline)
    with a.baseline.open('rb') as stream:
        baseline_sha = file_digest(stream,'sha256').hexdigest()
    with ZipFile(a.baseline) as previous:
        baseline = list(csv.DictReader(io.StringIO(previous.read('observations.csv').decode())))
        manifest = json.loads(previous.read('source_manifest.json'))
        evidence = reason_evidence(previous,manifest)
        changes = revision_candidates(baseline,evidence)
        if changes:
            (output/'reason_vintage_candidates.csv').write_text(csv_text(changes))
        monthly = defaultdict(dict)
        for r in additions:
            monthly[r['period']][r['sex_code']] = int(r['raw'])
        complete = [v for v in monthly.values() if set(v)==set(SEX)]
        difference = Counter(v['0']-v['1']-v['2'] for v in complete)
        total_flags = [period for period,v in monthly.items() if set(v)==set(SEX) and abs(v['0']-v['1']-v['2'])>1]
        prior = None
        if a.prior:
            with a.prior.open(encoding='utf-8-sig',newline='') as f:
                prior = overlap(additions,csv.DictReader(f))
        periods = {row['period'] for row in baseline if row['source'].startswith('reason_')}
        archive = html.fromstring(previous.read('raw/labor_archive.html').decode('cp932',errors='replace'))
        linked = {m[1]:urljoin(STAT,a) for a in archive.xpath('//a/@href')
                  if (m:=re.search(r'/dt/pdf/(20\d{2}_[1-4])\.pdf$',a))}
        missing = [{'period':f'{y}-Q{q}','general_release_url':linked.get(f'{y}_{q}',''),
                    'reason_table_status':'同形式の理由別参考表の確認なし'}
                   for y in YEARS for q in range(1,5) if f'{y}-Q{q}' not in periods]
        catalog = raw/'reason_catalog.html'
        edition_urls = {}
        if catalog.exists():
            doc = html.parse(catalog,html.HTMLParser(encoding='utf-8'))
            for one in doc.xpath('//ul[contains(@class,"stat-cycle_ul_other")]'):
                title = one.xpath('string(./li[contains(@class,"stat-cycle_header")])').strip()
                for link in one.xpath('./li//a[@href]'):
                    q = re.fullmatch(r'(1|4|7|10)[~〜](3|6|9|12)月期',normalized(link.text_content()))
                    if re.fullmatch(r'20\d{2}年',title) and q:
                        edition_urls[f'{title[:4]}-Q{(int(q[1])+2)//3}'] = urljoin(ESTAT,link.get('href'))
        def retrieve(item):
            period = item['period']
            catalog_url = edition_urls.get(period)
            item['catalog_url'] = catalog_url or ''
            address = item['general_release_url'] or catalog_url
            if not address:
                return []
            suffix = '.pdf' if address.endswith('.pdf') else '.html'
            name = f'reason_search_{period}'+suffix
            current = list(acquire(raw,{name:address}))
            row = current[0]
            if row['status']!='acquired':
                item['reason_table_status'] = f'原資料取得失敗（{row.get("http_status","不明")}）'
                return current
            path = raw/name
            if suffix=='.html':
                doc = html.parse(path,html.HTMLParser(encoding='utf-8'))
                for a in doc.xpath('//a[contains(@href,"fileKind=2")]'):
                    href = urljoin(ESTAT,a.get('href'))
                    title = ' '.join(a.xpath('ancestor::tr[1]//text()'))
                    if '正誤' in title:
                        continue
                    pdf_records = list(acquire(raw,{f'reason_search_{period}_release.pdf':href}))
                    current.extend(pdf_records)
                    if pdf_records[0]['status']=='acquired':
                        path = raw/pdf_records[0]['filename']
                    break
            if path.suffix=='.pdf':
                text = subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,check=True,text=True).stdout
                found = bool(re.search(r'休業の理由別休業者',text))
                item['reason_table_status'] = ('理由別表見出しを確認。列定義・数値は保留' if found else
                                               '取得した概要PDFに理由別表見出しなし')
            else:
                item['reason_table_status'] = '公表一覧取得。対象の概要PDFを確認できず'
            return current
        with ThreadPoolExecutor(max_workers=5) as pool:
            for batch in pool.map(retrieve,missing):
                for row in batch:
                    row.update(publisher='総務省統計局',publication_date='不明')
                records.extend(batch)
        for r in records:
            r.setdefault('landing_url', r['url'])
            if r['status']=='acquired' and sha256((raw/r['filename']).read_bytes()).hexdigest()!=r['sha256']:
                raise ValueError(f'Source hash mismatch: {r["filename"]}')
        (output/'source_manifest_addendum.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        qa = dict(executed_jst=now(),baseline_sha256=baseline_sha,original_codex_baseline=baseline_sha==BASE_SHA,
                  baseline_rows=len(baseline),baseline_sources=sum(r['status']=='acquired' for r in manifest),
                  acquired_sources=sum(r['status']=='acquired' for r in records),
                  monthly_rows=len(additions),monthly_periods=len(complete),
                  sex_total_difference_counts=dict(difference),sex_totals_beyond_one=total_flags,reason_changed_keys=len(changes),
                  reason_rebased_candidate_keys=sum(bool(r['candidate_source']) for r in changes),
                  missing_reason_quarters=missing,reason_release_evidence=evidence,
                  prior_comparison=prior,prior_candidates={
                      'monthly_absence':'同一DBコードの既存数値明細は未確認',
                      'wages':'000032189777は既存監査と同じ資料ID。版・対象・行の一致は未確認'},
                  wage_definition=dict(industry='TL',establishment_size='T',employment_type='0',
                      index_base=2020,index_base_value=100,index_unit='指数',growth_unit='%',
                      nominal='現金給与総額',real='実質賃金指数（現金給与総額）',
                      deflator='2020年基準CPI（持家の帰属家賃を除く総合）',
                      research_id_mapping='WC01・WC02の正式な研究内対応台帳は未確認'))
        (output/'quality_audit_addendum.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
        package = output/'employment_wage_c13_integrated.zip'
        hashes = json.loads(previous.read('internal_sha256.json'))
        with ZipFile(package,'x',ZIP_DEFLATED) as target:
            for member in hashes:
                target.writestr(member,previous.read(member))
            for path in [*sorted(output.glob('*.json')),*sorted(output.glob('*.csv')),*sorted(raw.iterdir())]:
                if path.parent==raw and path.name.endswith(('.pdf.json','.html.json','.json.json')):
                    continue
                member = 'followup/'+path.relative_to(output).as_posix()
                b = path.read_bytes()
                target.writestr(member,b)
                hashes[member] = sha256(b).hexdigest()
            target.writestr('internal_sha256.json',json.dumps(hashes,indent=2))
    count = verify(package)
    with package.open('rb') as stream:
        digest = file_digest(stream,'sha256').hexdigest()
    (output/'package_verification.json').write_text(json.dumps(
        dict(verified_members=count,crc='pass',bytes=package.stat().st_size,sha256=digest),indent=2)+'\n')


if __name__=='__main__':
    main()

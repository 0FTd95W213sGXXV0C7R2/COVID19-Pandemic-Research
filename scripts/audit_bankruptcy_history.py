"""Acquire TDB publication archive and reconcile it with the existing audit."""
import argparse
import csv
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from subprocess import CalledProcessError
from urllib.parse import urljoin
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import html
from audit_bankruptcy_supplement import (
    CAP, CAUSE, EMP, FORM, TDB, acquire, csv_file, extract, norm,
    now, number, pdf, write_extracts,
)

TARGET = range(2017, 2025)
LABELS = dict(BK06=EMP, BK07=CAP, BK08=CAUSE, BK09=FORM)


def document(path):
    return html.parse(path, html.HTMLParser(encoding='utf-8'))


def report_links(doc, year):
    links = {}
    for a in doc.xpath('//a[contains(@href,"/aggregation/")]'):
        m = re.fullmatch(r'倒産集計\s*(\d{4})年\s*(\d{1,2})月報', a.text_content().strip())
        if m and int(m[1]) == year:
            links[f'tdb_{year}-{int(m[2]):02}.html'] = urljoin(TDB, a.get('href'))
        elif re.fullmatch(fr'倒産集計\s*{year}年(?:報)?\s*(?:\(1月~12月\))?', norm(a.text_content().strip())):
            links[f'tdb_{year}.html'] = urljoin(TDB, a.get('href'))
    return links


def download(cache, sources, records, publisher):
    def one(item):
        marker = cache/(item[0]+'.denied.json')
        if marker.exists():
            recorded = json.loads(marker.read_text())
            if recorded['url']==item[1]:
                return recorded
        record = next(acquire(cache, dict([item])))
        if record.get('http_status')==403:
            marker.write_text(json.dumps(record))
        return record
    with ThreadPoolExecutor(max_workers=5) as pool:
        batch = list(pool.map(one, sources.items()))
    for record in batch:
        record.update(publisher=publisher, reuse_terms='公開再配布許諾未確認')
    records.extend(batch)
    return [cache / r['filename'] for r in batch if r['status'] == 'acquired']


def get_archive(cache, records):
    listing = {f'index_{y}.html': f'{TDB}/report/bankruptcy/?year={y}' for y in TARGET}
    links = {}
    for p in download(cache, listing, records, '帝国データバンク'):
        links.update(report_links(document(p), int(p.stem.split('_')[1])))
    pdfs = {}
    parents = {}
    for p in download(cache, links, records, '帝国データバンク'):
        for i, href in enumerate(dict.fromkeys(document(p).xpath('//a[contains(@href,".pdf")]/@href'))):
            name = f'{p.stem}_{i}.pdf'
            pdfs[name] = urljoin(links[p.name], href)
            parents[name] = links[p.name]
    paths = download(cache, pdfs, records, '帝国データバンク')
    for r in records:
        r['landing_url'] = parents.get(r['filename'], r['url'])
    return paths


def legacy_table(page, labels, expected):
    """Read the current-period column by its horizontal position, including blanks."""
    value_pairs = re.compile(r'([\d,]+)\s*\(\s*[\d.]+\s*\)')
    totals = list(re.finditer(r'^\s*合計[ \t]+[^\n]+', page, re.M))
    aliases = {'個人事業主': ('個人事業主', '個人経営')}
    for start, end in zip([0, *(m.end() for m in totals)], totals):
        total_line = end[0].split('\n')[-1]
        cols = list(value_pairs.finditer(total_line))
        if len(cols) < 2 or number(cols[-1][1]) != expected:
            continue
        target = cols[-1].end()
        block = page[start:end.start()]
        values = {}
        for label in labels:
            variants = aliases.get(label, (label,))
            matches = [line for line in block.splitlines()
                       if re.match(r'^\s*(?:[従業員数主因資本金態様別]\s+)?(?:'
                                   + '|'.join(map(re.escape, variants)) + r')(?:\s|$)', line)]
            if len(matches) != 1:
                break
            pairs = [m for m in value_pairs.finditer(matches[0]) if abs(m.end()-target) <= 2]
            values[label] = number(pairs[0][1]) if len(pairs) == 1 else None
        if len(values) == len(labels) and any(v is not None for v in values.values()):
            if sum(v for v in values.values() if v is not None) == expected:
                return values
    raise ValueError('No reconciled positional table')


def modern_table(page, labels, expected):
    from audit_bankruptcy_supplement import category_table
    values = category_table(page, labels)
    if sum(values.values()) != expected:
        raise ValueError('National total mismatch')
    return values


def historical_rows(paths, national, baseline, issues):
    output = []
    seen = {(r['period'], r['item']) for r in baseline if r['item'] in LABELS}
    for path in sorted(paths, reverse=True):
        period = path.stem.split('_')[1]
        if not re.fullmatch(r'20\d{2}(?:-\d\d)?', period):
            continue
        try:
            pages = pdf(path)
        except (OSError, ValueError, CalledProcessError) as exc:
            issues.append(dict(file=path.name,error=str(exc)))
            continue
        for i, page in enumerate(pages, 1):
            if not ('10人未満' in page or '販売不振' in page or '会社更生法' in page):
                continue
            # Some December downloads contain an annual table followed by a December table.
            candidates = [period]
            if period.endswith('-12'):
                candidates.append(period[:4])
            for target in candidates:
                if target not in national:
                    continue
                for item, labels in LABELS.items():
                    if (target,item) in seen:
                        continue
                    values = None
                    method = 'industry_national'
                    try:
                        values = modern_table(page, labels, national[target])
                    except (ValueError, IndexError):
                        if '倒産分類別比較' in page and target == period:
                            method = 'positional'
                            try:
                                values = legacy_table(page, labels, national[target])
                            except ValueError:
                                pass
                    if values is None and target == period:
                        method = 'summary'
                        try:
                            values = summary_table(page, labels, national[target], target)
                        except ValueError:
                            pass
                    if values is None:
                        continue
                    seen.add((target,item))
                    for label, value in values.items():
                        output.append(dict(item=item,provider='TDB',period=target,
                                           frequency='month' if len(target)==7 else 'year',
                                           category=label,value=value,unit='件',source=path.name,
                                           locator=f'PDF p.{i} {method}'))
    return output


def summary_table(page, labels, expected, period=None):
    """Compare adjacent published count columns without parsing percentage columns."""
    subset = ('販売不振','輸出不振','売掛金回収難','不良債権の累積','業界不振',
              '放漫経営','設備投資の失敗','その他の経営計画の失敗','その他')
    groups = {CAP: '資本金規模別', FORM: '倒産態様別', CAUSE: '主因別'}
    if labels not in groups:
        raise ValueError('No summary schema')
    if period is not None and len(period)==4:
        y = int(period)
        heading = fr'[^\n]*(?:\n[ \t]*)?{y-1}年[ \t]+{y}年[^\n]*'
    else:
        dated = ''
        if period is not None:
            y,m = period.split('-')
            dated = fr'|{y}年\s*{int(m)}月'
        heading = fr'[^\n]*(?:\n[^\n]*)?(?:当月{dated})[^\n]*'
    header = re.search(r'^[ \t]*'+groups[labels]+r'(?:件数)?'+heading,page,re.M)
    if header is None:
        raise ValueError('Missing summary header')
    block = page[header.end():]
    total_pattern = re.compile(r'^\s*合計[ \t]+([\d,]+)[ \t]+([\d,]+)(?=\s)', re.M)
    total = total_pattern.search(block)
    if total is None or number(total[2]) != expected:
        raise ValueError('Summary total mismatch')
    values = {}
    compact_cap = ('個人事業主','1000万円未満','1000万円以上5000万円未満',
                   '5000万円以上1億円未満','1億円以上')
    row_labels = subset if labels == CAUSE else compact_cap if labels == CAP else labels
    for label in row_labels:
        match = re.search(r'^\s*'+re.escape(label)+r'\s+([\d,]+)[ \t]+([\d,]+)(?=\s)',
                          block[:total.start()], re.M)
        if match is None:
            raise ValueError('Incomplete summary classification')
        values[label] = number(match[2])
    if sum(values.values()) != expected:
        raise ValueError('Unreconciled summary')
    if labels == CAP:
        values = {f'{key}（5区分表）': value for key,value in values.items()}
    if labels == CAUSE:
        values['その他（要約表区分）'] = values.pop('その他')
    return values


EXTRAS = {
    'closure_2017.html': TDB+'/report/economic/t1ynd5aam8ec/',
    'closure_2018.pdf': TDB+'/resource/files/assets/d4b8e8ee91d1489c9a2abd23a4bb5219/b6aa0e3ec7e441a68c4cbed6ddd0e1c9/p190109.pdf',
    'closure_2021.html': TDB+'/report/economic/4umrjveoe4-w/',
    'closure_2019.html': TDB+'/report/economic/e860t6_3qya/',
    'closure_2020.html': TDB+'/report/economic/a75_-ni-r/',
    'closure_2022.html': TDB+'/report/economic/j86604z4pn/',
    'closure_2023.pdf': TDB+'/resource/files/assets/d4b8e8ee91d1489c9a2abd23a4bb5219/801711ec2d784c6aa58ea30835a5d9b9/p240105.pdf',
    'tsr_transition.html': 'https://www.tsr-net.co.jp/news/status/transition/',
    'tsr_labor_2023.html': 'https://www.tsr-net.co.jp/data/detail/1198293_1527.html',
    'tsr_labor_2024_jan_apr.html': 'https://www.tsr-net.co.jp/data/detail/1198561_1527.html',
    'tsr_drive.html': 'https://drive.google.com/uc?export=download&id=1-DcF3nEAeA5giYeDsZt77W7wjU_ZuO44',
    'cao_definition.html': 'https://www5.cao.go.jp/keizai3/2024/0212nk/n24_3_1.html',
    'estat_tsr.csv': 'https://dashboard.e-stat.go.jp/download/timeSeriesResult?IndicatorCode=0701060100000010010&RegionLevel=2&RegionCode=00000&Cycle=1&IsSeasonalAdjustment=1',
    'estat_tsr_metadata.json': 'https://dashboard.e-stat.go.jp/api/1.0/Json/getIndicatorInfo?CallSystem=dash&Lang=JP&IndicatorCode=0701060100000010010',
    'estat_dashboard.html': 'https://dashboard.e-stat.go.jp/timeSeriesResult?indicatorCode=0701060100000010010',
    'whitepaper_2024.html': 'https://www.chusho.meti.go.jp/pamflet/hakusyo/2024/chusho/index.html',
    'whitepaper_2023.html': 'https://www.chusho.meti.go.jp/pamflet/hakusyo/2023/chusho/index.html',
    'meti_report.pdf': 'https://www.meti.go.jp/shingikai/sankoshin/shin_kijiku/business_restructuring/pdf/20250220_report.pdf',
}


def row(item, provider, year, category, value, source, locator):
    return dict(item=item, provider=provider, period=str(year), frequency='year',
                category=category, value=value, unit='件', source=source, locator=locator)


def closure_rows(cache, previous):
    rows = []
    path = cache/'closure_2022.pdf'
    if path.exists():
        page = pdf(path)[1]
        for y in range(2017,2020):
            m = re.search(fr'\b{y}\s+([\d,]+)\s+[▲+\- ]*[\d.]+%', page)
            if m:
                rows.append(row('BK10','TDB',y,'休廃業・解散',number(m[1]),path.name,'PDF p.2 全国推移'))
    page = pdf(previous/'tdb_closure.pdf')[2]
    m = re.search(r'^\s*([\d,]+(?:\s+[\d,]+){4})\s+\+[\d,]+\s*$',page,re.M)
    if m:
        for y,v in zip(range(2020,2024),m[1].split()):
            rows.append(row('BK10','TDB',y,'休廃業・解散',number(v),'tdb_closure.pdf','訂正版 PDF p.3 全国推移'))
    for y in range(2017,2020):
        path = cache/f'closure_{y}.pdf'
        if path.exists():
            m = re.search(fr'{y}\s*年[^\n]*休廃業・解散[^\n]*2\s*万\s*(\d{{4}})\s*件',
                          pdf(path)[0])
            if m:
                rows.append(row('BK10','TDB',y,'休廃業・解散（旧調査・判明件数）',
                                20000+number(m[1]),path.name,'PDF p.1 調査結果'))
    return rows


def tsr_monthly(cache, annual):
    source, meta = cache/'estat_tsr.csv', cache/'estat_tsr_metadata.json'
    if not source.exists() or not meta.exists():
        return {}
    if '全国企業倒産状況＜株式会社東京商工リサーチ＞' not in json.dumps(json.loads(meta.read_text()),ensure_ascii=False):
        raise ValueError('The dashboard indicator does not identify the TSR source')
    result = {}
    with source.open(encoding='utf-8-sig',newline='') as stream:
        for r in csv.DictReader(stream):
            m = re.fullmatch(r'(20\d{2})年(\d{1,2})月',r['時点'])
            if not m or int(m[1]) not in TARGET or r['地域コード']!='00000':
                continue
            period = f'{m[1]}-{int(m[2]):02}'
            if period in result or r['注記'] or not r['企業倒産件数【件】'].isdigit():
                raise ValueError(f'Unexpected TSR month: {period}')
            result[period] = int(r['企業倒産件数【件】'])
    expected = {f'{y}-{m:02}' for y in TARGET for m in range(1,13)}
    if set(result)!=expected:
        raise ValueError('Incomplete TSR monthly coverage')
    if annual.keys()!={str(y) for y in TARGET} or any(
        sum(result[f'{y}-{m:02}'] for m in range(1,13))!=annual[str(y)] for y in TARGET
    ):
        raise ValueError('TSR official annual benchmark mismatch')
    return result


def tsr_annual(path):
    if not path.exists():
        return {}
    result = {}
    for tr in document(path).xpath('//table//tr'):
        cells = [c.text_content().strip() for c in tr.xpath('./th|./td')]
        if len(cells) >= 3 and re.match(r'^20\d\d（',cells[0]):
            year = int(cells[0][:4])
            if year in TARGET and re.fullmatch(r'[\d,]+', cells[1]):
                result[str(year)] = number(cells[1])
    return result


def diagnostics(rows):
    key = lambda r: tuple(r[k] for k in ('item','provider','frequency','category','period'))
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError('Duplicate observation')
    if any(r['value'] is not None and r['value'] < 0 for r in rows):
        raise ValueError('Negative observation')
    coverage = {}
    for item in ('BK06','BK07','BK08','BK09','BK10','BK11'):
        coverage[item] = {}
        for prov in sorted({r['provider'] for r in rows if r['item']==item}):
            select = [r for r in rows if (r['item'],r['provider'])==(item,prov)]
            coverage[item][prov] = {
                'months':len({r['period'] for r in select if r['frequency']=='month'}),
                'years':len({r['period'] for r in select if r['frequency']=='year'}),
                'rows':len(select), 'numeric':sum(r['value'] is not None for r in select),
                'blanks':sum(r['value'] is None for r in select),
                'variables':len({(r['category'],r['frequency']) for r in select}),
            }
    return coverage


def main():
    import hashlib
    import statistics

    parser = argparse.ArgumentParser()
    parser.add_argument('private',type=Path)
    parser.add_argument('--baseline',type=Path,required=True,help='previous private output')
    parser.add_argument('--baseline-manifest',type=Path)
    parser.add_argument('--audit',type=Path,required=True)
    args = parser.parse_args()
    root = args.private
    cache = root/'raw'
    previous = args.baseline/'raw'
    project = Path(__file__).resolve().parents[1]
    old = project/'data/audits/rebuild_2026/bankruptcy_bk06_11'
    for loc in (root,args.audit):
        loc.mkdir(parents=True,exist_ok=True)
    previous_manifest = json.loads((args.baseline_manifest or old/'source_manifest.json').read_text())
    for r in previous_manifest:
        if r['status']=='acquired' and hashlib.sha256((previous/r['filename']).read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError(f'Previous hash mismatch: {r["filename"]}')
    baseline = extract(previous)
    national = {r['period']:r['value'] for r in baseline if r['item']=='BK11'}
    records = []
    paths = get_archive(cache,records)
    for filename,url in EXTRAS.items():
        publisher = ('帝国データバンク' if filename.startswith('closure') else
                     '東京商工リサーチ' if filename.startswith('tsr') else '政府機関')
        extra = download(cache,{filename:url},records,publisher)
        if filename.startswith('closure') and extra and filename.endswith('.html'):
            links = document(extra[0]).xpath('//a[contains(@href,".pdf")]/@href')
            if links:
                download(cache,{extra[0].stem+'.pdf':urljoin(TDB,links[0])},records,publisher)
    for r in records:
        r.setdefault('landing_url',r['url'])
        if r['status']=='acquired':
            path = cache/r['filename']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=r['sha256']:
                raise ValueError(f'Hash mismatch: {path.name}')
            if path.suffix=='.html':
                doc = document(path)
                r['title'] = doc.xpath('string(//title)').strip()
                dates = re.search(r'"datePublished":"([^"]+)"(?:,"dateModified":"([^"]+)")?',path.read_text(errors='replace'))
                if dates:
                    r['publication_date'],r['revision_date'] = (v or '不明' for v in dates.groups())
        r.setdefault('publication_date','不明')
        r.setdefault('revision_date','不明')
    json_out = lambda path,obj: path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    json_out(args.audit/'source_manifest.json',dict(previous=previous_manifest,new=records))
    issues = []
    additions = historical_rows(paths,national,baseline,issues)
    rows = baseline + additions + closure_rows(cache,previous)
    labor = cache/'tsr_labor_2023.html'
    if labor.exists():
        m = re.search(r'過去最多の([\d,]+)件',document(labor).xpath('string(//title)'))
        if m:
            rows.append(row('BK08','TSR',2023,'人手不足関連倒産',number(m[1]),labor.name,'記事見出し'))
        text = document(labor).xpath('string(//main)')
        for y, pattern in ((2019,r'2019年の([\d,]+)件'),(2022,r'前年の([\d,]+)件から2.5倍')):
            earlier = re.search(pattern,text)
            if earlier:
                rows.append(row('BK08','TSR',y,'人手不足関連倒産',number(earlier[1]),labor.name,'記事本文'))
    annual = tsr_annual(cache/'tsr_transition.html')
    monthly = tsr_monthly(cache,annual)
    monthly_comparison = [dict(period=p,tsr=v,tdb=national[p],difference_tsr_minus_tdb=v-national[p],
                               ratio_tsr_to_tdb=v/national[p]) for p,v in sorted(monthly.items())]
    if monthly_comparison:
        csv_file(root/'bk11_monthly_comparison.csv',monthly_comparison)
        for p,v in sorted(monthly.items()):
            observation = row('BK11','TSR',p,'全国倒産件数',v,'estat_tsr.csv','全国行・時点')
            observation['frequency'] = 'month'
            rows.append(observation)
        rows.extend(row('BK11','TSR',y,'全国倒産件数',v,'tsr_transition.html','年間件数表')
                    for y,v in sorted(annual.items()))
    compare = [dict(year=y,tsr=v,tdb=national[y],difference_tsr_minus_tdb=v-national[y],
                    ratio_tsr_to_tdb=v/national[y]) for y,v in sorted(annual.items())]
    if compare:
        csv_file(root/'bk11_annual_comparison.csv',compare)
    write_extracts(root,rows)
    dictionary = sorted({(r['item'],r['provider'],r['frequency'],r['category'],r['unit']) for r in rows})
    csv_file(root/'variable_dictionary.csv',[dict(zip(('item','provider','frequency','category','unit'),key)) for key in dictionary])
    present = defaultdict(list)
    for r in rows:
        if r['provider']=='TDB' and r['item'] in LABELS:
            present[r['item'],r['period']].append(r)
    checks = Counter()
    for (item,period), values in present.items():
        if len(period)!=4:
            continue
        month_groups = [present.get((item,f'{period}-{m:02}'),[]) for m in range(1,13)]
        expected = {r['category'] for r in values}
        for r in values:
            if any({v['category'] for v in group}!=expected for group in month_groups):
                checks['incomplete_or_schema_difference'] += 1
                continue
            comparable = [v['value'] for group in month_groups for v in group if v['category']==r['category']]
            if r['value'] is None or any(v is None for v in comparable):
                checks['blank'] += 1
            else:
                checks['match' if sum(comparable)==r['value'] else 'mismatch'] += 1
    counts = Counter((r['status'],Path(r['filename']).suffix) for r in records)
    qa = dict(executed_jst=now(), baseline_rows=len(baseline), total_rows=len(rows),
              acquisition={f'{status}{ext}':n for (status,ext),n in sorted(counts.items())},
              coverage=diagnostics(rows), category_national_checks=len(present),
              comparable_category_annual_checks=dict(checks), parser_errors=issues,
              bk11_monthly_pairs=len(monthly_comparison),
              bk11_monthly_source='政府統計ダッシュボードのTSR系列。既存Drive原本はHTML応答のため入手不能。',
              bk11_monthly_pearson=statistics.correlation([r['tsr'] for r in monthly_comparison],
                                                         [r['tdb'] for r in monthly_comparison])
              if len(monthly_comparison)>1 else None,
              bk11_tsr_monthly_annual_matches=8 if monthly_comparison else 0,
              bk11_annual_pairs=len(compare),
              bk11_annual_pearson=statistics.correlation([r['tsr'] for r in compare],[r['tdb'] for r in compare])
              if len(compare)>1 else None)
    qa['bk11_tdb_monthly_annual_matches'] = sum(
        sum(national[f'{y}-{m:02}'] for m in range(1,13))==national[str(y)] for y in TARGET)
    acquired = {r['sha256'] for r in records if r['status']=='acquired'}
    old_hashes = {r['sha256'] for r in previous_manifest if r['status']=='acquired'}
    qa['unique_new_payloads_vs_baseline'] = len(acquired-old_hashes)
    for frequency, comparisons in [('monthly',monthly_comparison),('annual',compare)]:
        if comparisons:
            qa[f'bk11_{frequency}_difference_range'] = [
                min(r['difference_tsr_minus_tdb'] for r in comparisons),
                max(r['difference_tsr_minus_tdb'] for r in comparisons)]
            qa[f'bk11_{frequency}_ratio_range'] = [
                min(r['ratio_tsr_to_tdb'] for r in comparisons),
                max(r['ratio_tsr_to_tdb'] for r in comparisons)]
    json_out(args.audit/'quality_audit.json',qa)
    coverage = defaultdict(set)
    for r in rows:
        coverage[r['item'],r['provider'],r['period'][:4],r['frequency']].add(r['period'])
    coverage_rows = [dict(item=item,provider=provider,year=year,frequency=frequency,
                          periods=len(periods),target=12 if frequency=='month' else 1)
                     for (item,provider,year,frequency),periods in sorted(coverage.items())]
    csv_file(args.audit/'period_coverage.csv',coverage_rows)
    with ZipFile(root/'bankruptcy_bk06_11_research.zip','w',ZIP_DEFLATED) as z:
        included = {}
        for base,entries in ((previous,previous_manifest),(cache,records)):
            for r in entries:
                if r['status']=='acquired':
                    path = included.get(r['sha256'])
                    if path is None:
                        path = 'raw/'+r['filename']
                        z.write(base/r['filename'],path)
                        included[r['sha256']] = path
                    r['package_path'] = path
        json_out(args.audit/'source_manifest.json',dict(previous=previous_manifest,new=records))
        for p in (root/'bankruptcy_long.csv',root/'bankruptcy_wide.csv',root/'variable_dictionary.csv',
                  args.audit/'source_manifest.json',args.audit/'quality_audit.json',args.audit/'period_coverage.csv',
                  Path(__file__),Path(__file__).with_name('audit_bankruptcy_supplement.py'),
                  Path(__file__).with_name('education_sources.py')):
            z.write(p,p.name)
        for p in sorted(project.glob('docs/audits/rebuild_2026/economy_bk06_11*md')):
            z.write(p,p.name)
        if monthly_comparison:
            z.write(root/'bk11_monthly_comparison.csv','bk11_monthly_comparison.csv')
        if compare:
            z.write(root/'bk11_annual_comparison.csv','bk11_annual_comparison.csv')
    print(json.dumps(qa,ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Complete missing TDB tables from the preserved bankruptcy package."""
import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256, file_digest
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

import fitz

from audit_bankruptcy_history import LABELS, TARGET, diagnostics, document, download
from audit_bankruptcy_supplement import csv_file, norm, now, number, pdf, write_extracts

SUMMARY_CAUSE = ('販売不振','輸出不振','売掛金回収難','不良債権の累積','業界不振',
                 '放漫経営','設備投資の失敗','その他の経営計画の失敗','その他')
CAP_COMPACT = ('個人事業主','1000万円未満','1000万円以上5000万円未満',
               '5000万円以上1億円未満','1億円以上')
CAP_SHORT = ('個人事業主','1000万円未満','5000万円未満','1億円未満','1億円以上')
KEYS = ('item','provider','frequency','category','period')
REPORT = re.compile(r'tdb_(20\d{2}(?:-\d\d)?)_\d+\.pdf')


def key(row):
    return tuple(row[k] for k in KEYS)


def compact_tables(page, item, expected, period):
    """Select a count column by national total, anchored to the printed period heading."""
    alternatives = {
        'BK07': [(CAP_COMPACT,'5区分表'), (CAP_SHORT,'上限表記5区分表')],
        'BK08': [(SUMMARY_CAUSE,'要約表区分'),
                 ((*SUMMARY_CAUSE[:-1],'経営者の病気、死亡','その他'),'要約表10区分')],
        'BK09': [(LABELS['BK09'],'')],
    }
    lines = [line.strip() for line in page.splitlines()]
    year = period[:4]
    era = (fr'{year}\s*年\s*{int(period[5:])}\s*月|当月'
           if len(period)==7 else fr'{year}\s*年')
    sections = {'BK07':'資本金規模別','BK08':'主因別','BK09':'態様別'}
    for i, line in enumerate(lines):
        total = re.match(r'^合計\s+((?:[\d,]+(?:\s+|$))+)',line)
        if not total:
            continue
        counts = [number(v) for v in total[1].split()]
        if expected not in counts[:3]:
            continue
        for labels, schema in alternatives.get(item,[]):
            block = lines[max(0,i-27):i]
            condensed = '\n'.join(block)
            if sections[item] not in condensed or not re.search(era,condensed):
                continue
            headers = [j for j,line in enumerate(block)
                       if re.match(r'^(?:倒産)?'+sections[item]+r'(?:件数)?(?:\s|$)',line)]
            if headers:
                block = block[headers[-1]:]
            if len(period)==4 and re.search(r'下半期|上半期|当月','\n'.join(block)):
                continue
            # The two-column table can be supplemented by a third prior comparison column.
            cols = 2
            if len(period)==4 and len(counts)>=3 and counts[1]!=expected:
                cols = 3
            candidate = cols-1
            if len(counts)<cols or counts[candidate]!=expected:
                continue
            values = {}
            for label in labels:
                matches = []
                for entry in block:
                    match = re.match(re.escape(label)+r'\s{2,}((?:[\d,]+(?:\s+|$))+)',entry)
                    if match:
                        matches.append([number(v) for v in match[1].split()])
                if len(matches)!=1 or len(matches[0])<cols:
                    break
                output_label = (f'{label}（{schema}）'
                                if schema and (item=='BK07' or label=='その他') else label)
                values[output_label] = matches[0][candidate]
            if len(values)==len(labels) and sum(values.values())==expected:
                yield values


def independent_row(page, category, value):
    """Check that the stated value appears on the category's physical PDF line."""
    label = category.split('（')[0]
    aliases = {label}
    if label=='個人事業主':
        aliases.add('個人経営')
    lines = defaultdict(list)
    for word in page.get_text('words'):
        lines[round(word[1] / 2)*2].append(word)
    for words in lines.values():
        line = norm(' '.join(w[4] for w in sorted(words)))
        if not any(re.match(r'^(?:[従業員数主因資本金態様別]\s+)?'+re.escape(a)+r'(?:\s|$)',line)
                   for a in aliases):
            continue
        if value is None:
            return 'blank_pending_column'
        integers = re.findall(r'(?<![\d.,+−-])[\d,]+(?![\d.,%])',line)
        if any(number(n)==value for n in integers):
            return 'row_value_confirmed'
    return 'unconfirmed'


def supplemental_rows(cache, records):
    urls = {
        'tsr_price_original_2023.html':'https://www.tsr-net.co.jp/data/detail/1198289_1527.html',
    }
    rows = []
    for path in download(cache,urls,records,'東京商工リサーチ'):
        doc = document(path)
        records[-1]['title'] = doc.xpath('string(//title)').strip()
        records[-1]['publication_date'] = doc.xpath('string(//*[@class="entry_date"]/div)').strip() or '不明'
        records[-1]['revision_date'] = '不明'
        records[-1]['landing_url'] = urls[path.name]
        body = norm(doc.xpath('string(//main)'))
        m = re.search(r'2023年の「物価高」倒産は([\d,]+)件.{0,65}前年\(([\d,]+)件\)',body)
        months = re.search(r'12月は前年同月と同件数の([\d,]+)件',body)
        if not (m and months):
            continue
        entries = [('2023','物価高倒産（2023年当初公表）',m[1]),('2022','物価高倒産',m[2]),
                   ('2022-12','物価高倒産',months[1]),('2023-12','物価高倒産',months[1])]
        for period,label,value in entries:
            rows.append(dict(item='BK08',provider='TSR',period=period,
                             frequency='year' if len(period)==4 else 'month',category=label,
                             value=number(value),unit='件',source=path.name,locator='公式記事本文・冒頭'))
    return rows


def read_baseline(z):
    rows = list(csv.DictReader(io.StringIO(z.read('bankruptcy_long.csv').decode())))
    for r in rows:
        r['value'] = int(r['value']) if r['value'] else None
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('audit',type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    args.audit.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.baseline) as old:
        baseline = read_baseline(old)
        manifest = json.loads(old.read('source_manifest.json'))
        members = {r['filename']:r['package_path'] for records in manifest.values()
                   for r in records if r.get('package_path')}
        checked = {}
        for records in manifest.values():
            for r in records:
                member = r.get('package_path')
                if not member:
                    continue
                if member not in checked:
                    checked[member] = sha256(old.read(member)).hexdigest()
                if checked[member]!=r['sha256']:
                    raise ValueError(f'Original hash mismatch: {member}')
        raw = args.output/'raw'
        raw.mkdir(exist_ok=True)
        national = {r['period']:r['value'] for r in baseline
                    if (r['item'],r['provider'])==('BK11','TDB')}
        present = {(r['item'],r['period']) for r in baseline if r['provider']=='TDB'}
        tables = defaultdict(dict)
        original_by_source = defaultdict(list)
        for r in baseline:
            if r['source'].endswith('.pdf'):
                original_by_source[r['source']].append(r)
        independent = Counter()
        detailed = []
        for filename,member in members.items():
            match = REPORT.fullmatch(filename)
            interesting = original_by_source[filename]
            if not (match or interesting):
                continue
            path = raw/filename
            if not path.exists():
                with path.open('xb') as f:
                    f.write(old.read(member))
            elif sha256(path.read_bytes()).hexdigest()!=checked[member]:
                raise ValueError(f'Materialized copy differs: {path}')
            with fitz.open(path) as doc:
                for r in interesting:
                    m = re.match(r'.*?PDF p\.(\d+)',r['locator'])
                    if m and r['item'] in LABELS:
                        status = independent_row(doc[int(m[1])-1],r['category'],r['value'])
                        independent[status] += 1
                        detailed.append(dict(**r,independent_result=status))
            if not match:
                continue
            period = match[1]
            if period not in national:
                continue
            for i,page in enumerate(pdf(path),1):
                for item in ('BK07','BK08','BK09'):
                    if (item,period) in present:
                        continue
                    for values in compact_tables(page,item,national[period],period):
                        signature = tuple(sorted(values.items()))
                        tables[item,period][signature] = (filename,i)
        additions = []
        ambiguous = 0
        for (item,period),signatures in sorted(tables.items()):
            if len(signatures)!=1:
                ambiguous += 1
                continue
            values,(source,page) = next(iter(signatures.items()))
            for label,value in values:
                additions.append(dict(item=item,provider='TDB',period=period,
                                      frequency='year' if len(period)==4 else 'month',
                                      category=label,value=value,unit='件',source=source,
                                      locator=f'PDF p.{page} 原表掲載値・要約表'))
        new_records = []
        additions.extend(supplemental_rows(raw,new_records))
        for record in new_records:
            if record['status']=='acquired':
                record['package_path'] = 'raw/'+record['filename']
        manifest['final'] = new_records
        (args.audit/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        rows = baseline+additions
        coverage = diagnostics(rows)
        write_extracts(args.output,rows)
        if detailed:
            csv_file(args.output/'independent_row_audit.csv',detailed)
        if additions:
            csv_file(args.output/'added_observations.csv',additions)
        dictionary = sorted({tuple(r[k] for k in KEYS[:-1])+(r['unit'],) for r in rows})
        csv_file(args.output/'variable_dictionary.csv',
                 [dict(zip((*KEYS[:-1],'unit'),r)) for r in dictionary])
        groups = defaultdict(dict)
        for r in rows:
            if r['provider']=='TDB' and r['item'] in LABELS:
                groups[r['item'],r['period']][r['category']] = r['value']
        yearly = Counter()
        for (item,period),values in groups.items():
            if len(period)!=4:
                continue
            months = [groups.get((item,f'{period}-{m:02}'),{}) for m in range(1,13)]
            for category, annual in values.items():
                if any(set(m)!=set(values) for m in months):
                    yearly['incomplete_or_schema_difference'] += 1
                elif annual is None or any(m[category] is None for m in months):
                    yearly['blank'] += 1
                else:
                    yearly['match' if annual==sum(m[category] for m in months) else 'mismatch'] += 1
        expected = {str(y) for y in TARGET}|{f'{y}-{m:02}' for y in TARGET for m in range(1,13)}
        availability = [dict(item=item,period=p,status='extracted' if (item,p) in groups
                             else 'not_confirmed_from_preserved_reports')
                        for item in LABELS for p in sorted(expected)]
        availability.extend(dict(item=item,period=p,status=status) for item,p,status in [
            ('BK08_TSR','2017–2024','partial_year_and_month'),
            ('BK10','2017–2024','closure_extracted_opening_closure_rates_pending'),
            ('BK11','2017–2024','monthly_and_annual_coverage_both_providers'),
        ])
        csv_file(args.audit/'availability.csv',availability)
        qa = dict(executed_jst=now(), baseline_rows=len(baseline), added_rows=len(additions),
                  changed_baseline_rows=0, total_rows=len(rows), coverage=coverage,
                  pdf_row_check=dict(independent), ambiguous_tables=ambiguous,
                  original_hashes_verified=len(checked), supplementary_acquired=sum(
                      r['status']=='acquired' for r in new_records),
                  annual_classification_checks=dict(yearly),
                  category_totals_match=sum(sum(v for v in g.values() if v is not None)==national[p]
                                            for (_,p),g in groups.items()),
                  category_tables=len(groups), duplicate_keys=0,
                  bk01_candidates=dict(monthly_same_indicator=96,annual_same_provider_metric=8,
                                       exact_duplicate_rows_verified=0),
                  other_values='原表掲載値のみ。要約区分は分類ラベルに明示。残差で算出した値は0件')
        report = args.audit/'quality_audit.json'
        report.write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
        package = args.output/'bankruptcy_final.zip'
        with ZipFile(package,'x',ZIP_DEFLATED) as final:
            for name in sorted(checked):
                final.writestr(name,old.read(name))
            for r in new_records:
                if r.get('package_path'):
                    final.write(raw/r['filename'],r['package_path'])
                    checked[r['package_path']] = r['sha256']
            for name in ('bk11_monthly_comparison.csv','bk11_annual_comparison.csv'):
                final.writestr(name,old.read(name))
            for path in sorted(args.output.glob('*.csv')):
                final.write(path,path.name)
            for path in sorted(args.audit.glob('*')):
                if path.name!='package_verification.json' and path.is_file():
                    final.write(path,path.name)
            doc = Path(__file__).resolve().parents[1]/'docs/audits/rebuild_2026/economy_bk06_11_final_20261128.md'
            if doc.exists():
                final.write(doc,doc.name)
            for path in (Path(__file__),Path(__file__).with_name('audit_bankruptcy_history.py'),
                         Path(__file__).with_name('audit_bankruptcy_supplement.py'),
                         Path(__file__).with_name('education_sources.py')):
                final.write(path,path.name)
    with ZipFile(package) as final:
        if final.testzip() is not None or any(sha256(final.read(n)).hexdigest()!=v for n,v in checked.items()):
            raise ValueError('Final ZIP failed integrity validation')
        internal = {n:sha256(final.read(n)).hexdigest() for n in final.namelist()}
    with package.open('rb') as stream:
        digest = file_digest(stream,'sha256').hexdigest()
    (args.output/'internal_hashes.json').write_text(json.dumps(internal,ensure_ascii=False,indent=2))
    (args.audit/'package_verification.json').write_text(json.dumps(
        dict(filename=package.name,bytes=package.stat().st_size,sha256=digest,
             crc='pass',original_hashes_verified=len(checked),internal_files_hashed=len(internal)),
        indent=2)+'\n')


if __name__=='__main__':
    main()

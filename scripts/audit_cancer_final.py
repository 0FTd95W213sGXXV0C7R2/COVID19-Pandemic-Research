"""Check the historical ASR keys directly against the two original workbooks."""
import argparse
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import xlrd

from audit_cancer_integration import colnum, normalized_standard, now, num, sha
from audit_cancer_residual import rows, save, status

WEIGHTS = {
    'japan_1985': (8180,8338,8497,8655,8814,8972,9130,9289,9400,8651,7616,6581,5546,4511,3476,2441,1406,784),
    'world_segi_1960': (12,10,9,9,8,8,6,6,6,6,5,4,4,3,2,1,.5,.5),
}
FILES = ('0b738a50d454_cancer_incidenceNCR(2016-2023).xls',
         'f2f514f223cc_pref_cancer_incidenceNCR(2016-2023).xls')
SEX = {'総数':'total','男':'male','女':'female'}


def records(sheet, regional, geo_col=0):
    for row in sheet.get_rows():
        cells = [cell.value for cell in row]
        if not regional or cells[geo_col] == 0:
            yield cells


def index(sheet, regional, measure):
    offset = 2 if regional else 0
    result = {}
    for row in records(sheet, regional, 1 if measure=='population' else 0):
        if measure=='population':
            if row[offset+1] not in SEX:
                continue
            k = int(row[offset+2]), SEX[row[offset+1]]
        else:
            if row[offset+3] not in SEX:
                continue
            k = int(row[offset+4]), str(int(row[offset])), row[offset+2].strip(), SEX[row[offset+3]]
        assert k not in result
        result[k] = dict(zip(sheet.row_values(0),row))
    return result


def cell(sheet, address):
    column, row = re.fullmatch(r'([A-Z]+)([0-9]+)',address).groups()
    return int(row)-1,colnum(column)


def weighted(rate, weights, regional):
    age = [f'{k}-{k+4}歳' for k in range(0,85,5)] + [
        '85歳以上' if regional else '85歳以上（再掲）']
    values = [num(rate[a]) for a in age]
    if any(v is None for v in values):
        return None
    return sum(v*w for v,w in zip(values,weights))/sum(weights)


def errata(root):
    folder = root/'raw/hospital_registry'
    report = folder/'adb7bb894af9_2022_report.pdf'
    history = folder/'c0479f8021b3_2022_syusei.pdf'
    def page(path, n):
        return subprocess.check_output(
            ['pdftotext','-layout','-f',str(n),'-l',str(n),str(path),'-'],
            text=True, stderr=subprocess.PIPE)
    assert '以下略' in page(history,1)
    assert '2020年症例以降' in page(report,4)
    lung = page(report,47)
    assert any("小細胞癌" in line and "8,080" in line and "885" in line for line in lung.splitlines())
    assert re.search(r'男性\s+6,450',lung) and re.search(r'女性\s+1,630',lung)
    ovaries = page(report,110)
    assert all(f'表4-17-5({i})' in ovaries for i in (1,2,3))
    pages = {int(r['pdf_page']) for path in (root/'hbcr_priority_review').glob('HBCR_2022*.csv')
             for r in rows(path) if r.get('pdf_page','').isdigit()}
    assert not pages & {4,47,110}
    return {'published_correction_pages':[4,47,110], 'reviewed_extract_pages':sorted(pages),
            'direct_page_overlap':[], 'omitted_history':True,
            'sha256':{p.name:sha(p) for p in (report,history)}}


def audit(root):
    started = now()
    paths = [root/'raw/cancer_statistics'/name for name in FILES]
    books = [xlrd.open_workbook(p,on_demand=True) for p in paths]
    rates = [index(b.sheet_by_name('rate'),i,'rate') for i,b in enumerate(books)]
    counts = [index(b.sheet_by_name('number'),i,'count') for i,b in enumerate(books)]
    pops = [index(b.sheet_by_name('pop'),i,'population') for i,b in enumerate(books)]
    table = defaultdict(lambda: defaultdict(Counter))
    maximum = defaultdict(float)
    source = root/'analysis_ready/national_prefecture_comparison.csv.gz'
    seen = set()
    for row in rows(source):
        if row['measure']!='incidence_asr':
            continue
        year, site, icd, sex, std = (row[k] for k in ('year','site_code','icd10','sex','standard_population'))
        k = int(year),site,icd,sex
        assert (*k,std) not in seen
        seen.add((*k,std))
        published = []
        for i,side in enumerate(('national','prefecture')):
            name = 'asr' if not i else 'asrW' if std=='world_segi_1960' else 'asrJ'
            sheet = books[i].sheet_by_name(name)
            r,c = cell(sheet,row['source_cell_'+side])
            dims = sheet.row_values(r)
            offset = 2*i
            assert (not i or dims[0]==0) and sheet.cell_value(0,c)==int(year)
            assert (str(int(dims[offset])),dims[offset+2].strip(),SEX[dims[offset+3]])==(site,icd,sex)
            assert name=='asrW' or normalized_standard(dims[offset+4])==std
            value = num(dims[c])
            published.append(value)
            table[std][side+'_within_source'][status(value,weighted(rates[i][k],WEIGHTS[std],i),1e-7)] += 1
        table[std]['cross_source'][status(*published,1e-7)] += 1
        table[std]['historical_cross_source'][row['comparison_status']] += 1
        if all(v is not None for v in published):
            maximum[std] = max(maximum[std],abs(published[0]-published[1]))
    checks = defaultdict(Counter)
    age_components = ('85-89歳','90-94歳','95-99歳','100歳以上')
    for i, side in enumerate(('national','prefecture')):
        for k, count in counts[i].items():
            if k[0]<2017:
                continue
            all85 = num(count['85歳以上（再掲）'])
            components = [num(count[a]) for a in age_components]
            checks[side+'_case_85plus_sum'][status(all85,sum(components) if None not in components else None,0)] += 1
            denom = num(pops[i][k[0],k[3]]['85歳以上' if i else '85歳以上（再掲）'])
            checks[side+'_rate_85plus'][status(num(rates[i][k]['85歳以上' if i else '85歳以上（再掲）']),
                                              all85/denom*100000 if all85 is not None and denom else None,1e-7)] += 1
    for k, pop in pops[0].items():
        if k[0]<2017:
            continue
        total = pop['85歳以上（再掲）']
        checks['national_population_85plus_sum'][status(total,sum(pop[a] for a in age_components),0)] += 1
        checks['cross_source_population_85plus'][status(total,num(pops[1][k]['85歳以上']),0)] += 1
    assert [sum(table[std]['cross_source'].values()) for std in WEIGHTS] == [721,728]
    correction = errata(root)
    return {'started_at_jst':started,'finished_at_jst':now(),'errata':correction,'input_sha256':{p.name:sha(p) for p in [*paths,source]},
            'absolute_tolerance':1e-7,'asr':table,'maximum_cross_source_absolute_difference':maximum,
            'age_85plus_checks':checks}


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_root',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    save(args.output,audit(args.source_root))

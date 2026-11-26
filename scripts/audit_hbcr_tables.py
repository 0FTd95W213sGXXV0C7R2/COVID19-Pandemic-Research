"""Independently enumerate HBCR source tables using layout and header keys."""
import re
import unicodedata
from collections import Counter

import pdfplumber


def normalize(text):
    return ''.join(unicodedata.normalize('NFKC',str(text or '')).split())


def count(text):
    m=re.match(r'^([0-9][0-9,]*)(?:\s|$)',str(text or '').strip())
    return int(m[1].replace(',','')) if m else None


def extract(pdf_path,page):
    with pdfplumber.open(pdf_path) as pdf:
        tables=pdf.pages[page-1].extract_tables()
    output={}
    for index,t in enumerate(tables):
        if page in (121,122):
            site={121:('胃','大腸','肺','乳房'),122:('子宮頸部',)}[page][index]
            for cells in t[3:]:
                period=normalize(cells[0]).replace('年','')
                period='2018-2019_mean' if '平均' in period else period
                for col in (1,2):
                    output[(site,period,'screen' if col==1 else 'other')]=count(cells[col])
            continue
        if page==137:
            labels=[]
            for i,cells in enumerate(t):
                if any(re.fullmatch(r'20\d\d年',normalize(v)) for v in cells):
                    site=''
                    labels=[]
                    for c in range(1,len(cells)):
                        site=normalize(t[i-1][c]) or site
                        v=normalize(cells[c])
                        if site and re.fullmatch(r'20\d\d年',v):
                            labels.append((c,site,v[:-1]))
                    continue
                field=normalize(cells[0])
                for c,site,year in labels:
                    if field and count(cells[c]) is not None:
                        output[site,year,field]=count(cells[c])
            continue
        starts={124:(0,6),125:(0,6),126:(0,6),129:(0,6),132:(0,),133:(0,),225:(0,8)}[225 if page==125 and len(t[0])==15 else page]
        # 2023 p125 uses seven data columns plus a separator.
        for start in starts:
            site=''
            years=[]
            for i,cells in enumerate(t):
                tag=normalize(cells[start])
                if i+1<len(t) and start+1<len(cells) and re.fullmatch(r'20\d\d年',normalize(t[i+1][start+1])):
                    if tag:
                        site=tag.split('(')[0]
                    years=[]
                if start+1<len(cells) and re.fullmatch(r'20\d\d年',normalize(cells[start+1])):
                    years=[(c,normalize(cells[c])[:-1]) for c in range(start+1,min(len(cells),start+7))
                           if re.fullmatch(r'20\d\d年',normalize(cells[c]))]
                    continue
                if not site or not years or not tag:
                    continue
                for c,year in years:
                    n=count(cells[c])
                    if n is None:
                        continue
                    if page in (124,126) or (page==125 and len(t[0])==12):
                        if tag=='総数' and page!=124:
                            continue
                        key=(site,year,tag,'screen' if start==0 else 'other')
                    elif page in (132,133):
                        key=(site,year,tag)
                    else:
                        key=(site,year,tag)
                    output[key]=n
    return output


def reconcile(name,rows,source):
    records=list(rows)
    actual={}
    expected={}
    denominator_checks=Counter()
    for r in records:
        page=int(float(r['pdf_page']))
        if page not in expected:
            expected[page]=extract(source,page)
        year=r.get('diagnosis_year') or r.get('year')
        if 'discovery' in name or 'prostate' in name:
            pathway='other' if normalize(r['discovery_pathway']).startswith('非') else 'screen'
            site=normalize(r.get('cancer_group') or r['site']).split('(')[0]
            if '2023' in name:
                key=(site,r['period'],pathway)
            else:
                m=r.get('diagnosis_month')
                key=(site,year,'総数' if not m else str(int(float(m)))+'月',pathway)
            metric='registration_count'
        elif 'stage_counts' in name:
            key=(normalize(r.get('cancer_site') or r['site']),year,normalize(r['stage']))
            metric='count'
        elif 'site_treatment' in name:
            key=(normalize(r['site']),year,normalize(r['treatment']))
            metric='count'
            total=expected[page].get((key[0],year,'総数'))
            denominator_checks['denominator_checked']+=1
            denominator_checks['denominator_mismatch']+=int(total!=count(r['総数']))
            if total and count(r['count']) is not None:
                denominator_checks['rate_checked']+=1
                denominator_checks['rate_mismatch']+=int(abs(count(r['count'])/total*100-float(r['rate_percent']))>1e-7)
        else:
            month=int(float(r['month']))
            key=(normalize(r['method']),year,'総数' if not month else str(month)+'月')
            metric='count'
        value=count(r[metric])
        actual.setdefault((page,key),[]).append(value)
    checks=denominator_checks
    for (page,key),values in actual.items():
        if len(values)>1:
            checks['duplicate_rows']+=len(values)-1
        for value in values:
            checks['match' if key in expected[page] and value==expected[page][key] else
                   'key_unresolved' if key not in expected[page] else 'difference']+=1
    checks['source_keys_in_selected_pages']=sum(len(d) for d in expected.values())
    checks['source_keys_absent_from_extract']=sum((page,k) not in actual for page,d in expected.items() for k in d)
    return dict(checks)

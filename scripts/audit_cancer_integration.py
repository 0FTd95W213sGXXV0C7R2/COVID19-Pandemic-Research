"""Read-only audit of the Drive snapshot. Publish aggregate results only."""
import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
import unicodedata
from urllib.request import urlopen
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fitz
import xlrd
from audit_hbcr_tables import reconcile

JST = ZoneInfo('Asia/Tokyo')
LONG = 'ncc_annual_long_2017_2024.csv.gz'
EXPECTED = '525d33421dcc1d1d288341346cb4f219feaf538887c19f7a2cf7305c01b23812'


def now():
    return datetime.now(JST).isoformat(timespec='seconds')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def num(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def string(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def equivalent(a, b):
    x, y = num(a), num(b)
    return abs(x-y)<=1e-7 if x is not None and y is not None else str(a).strip()==str(b).strip()


def word(value):
    return unicodedata.normalize('NFKC',string(value))


def normalized_age(header):
    text=word(header)
    if '全年齢' in text or '粗率' in text:
        return 'all_ages'
    if '不詳' in text:
        return 'unknown_age'
    text=text.replace('歳','').replace('(再掲)','').replace('合計','').replace('～','-').replace('~','-')
    if text.endswith('以上'):
        return text[:-2]+'+'
    return text[:-1]+'+' if text.endswith('-') else text


def normalized_standard(text):
    text=word(text)
    if '世界' in text:
        return 'world_segi_1960'
    if any(word in text for word in ('2015','平成27')):
        return 'japan_2015'
    if any(word in text for word in ('1985','昭和60')):
        return 'japan_1985'
    return ''


def colnum(label):
    n=0
    for c in label:
        n=n*26+ord(c)-64
    return n-1


def write_csv(path, headers, rows):
    with path.open('w',encoding='utf8',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(headers)
        writer.writerows(rows)


def inventory(root,out):
    expected={}
    manifest=root/'metadata/manifest.json'
    if manifest.exists():
        for row in json.loads(manifest.read_text()):
            rel=row['local_path'].split('NCC_CANCER_2017_2024/')[-1]
            expected[rel]=(row['sha256'],row['bytes'])
    for folder in ('analysis_ready','hbcr_priority_review'):
        manifest=root/folder/'output_manifest.json'
        if manifest.exists():
            details=json.loads(manifest.read_text())
            if isinstance(details,list):
                for r in details:
                    expected[folder+'/'+r['filename']]=(r['sha256'],r['bytes'])
    expected['analysis_ready/'+LONG]=(EXPECTED,21331833)
    paths=set(expected)
    for folder in ('analysis_ready','hbcr_priority_review'):
        paths.update(str(p.relative_to(root)) for p in (root/folder).glob('*') if p.is_file())
    histogram=Counter()
    result=[]
    received={}
    for rel in sorted(paths):
        p=root/rel
        previous,size=expected.get(rel,('',None))
        if not p.is_file():
            result.append((rel,'missing','','',previous,'not_checked'))
            histogram['missing']+=1
            continue
        digest=sha(p)
        status='match' if digest==previous and size==p.stat().st_size else ('difference' if previous else 'no_baseline')
        histogram[status]+=1
        readable='readable'
        try:
            if p.suffix=='.xls':
                xlrd.open_workbook(p,on_demand=True).release_resources()
            elif p.suffix=='.pdf':
                with fitz.open(p) as pdf:
                    if pdf.needs_pass or not len(pdf):
                        raise ValueError('inaccessible PDF')
            elif p.suffix=='.gz':
                with gzip.open(p,'rb') as f:
                    while f.read(1024*1024):
                        pass
            elif p.suffix=='.json':
                json.loads(p.read_text(encoding='utf-8-sig'))
            elif p.suffix=='.csv':
                with p.open(encoding='utf-8-sig',newline='') as f:
                    for _ in csv.reader(f,strict=True):
                        pass
            elif p.suffix=='.zip':
                from zipfile import ZipFile
                with ZipFile(p) as archive:
                    if archive.testzip() is not None:
                        raise ValueError('CRC failure')
            else:
                readable='not_checked'
        except Exception as error:
            readable='encrypted' if 'encrypted' in str(error).lower() else 'read_error'
        histogram[readable]+=1
        if rel.startswith('raw/') and status=='match':
            received[p.name.split('_',1)[1]]=p
        result.append((rel,status,p.stat().st_size,digest,previous,readable))
    write_csv(out/'file_integrity_audit.csv',['path','integrity','bytes','sha256','expected_sha256','readability'],result)
    return received,dict(histogram)


def expected_cells(s,d):
    # Walk source rows and headers, independently of all extract pointers.
    headers=s.row_values(0)
    for r in range(1,s.nrows):
        attrs={name:s.cell_value(r,c) for name,c in d['dims'].items()}
        for c in range(d['start'],s.ncols):
            year=num(headers[c] if d['mode']=='year' else attrs.get('year'))
            if year is not None and 2017<=year<=(2023 if d['scope'].startswith('incidence') else 2024) and headers[c]!='':
                yield r,c


def national(root,out,sources):
    extract=root/'analysis_ready'/LONG
    specs=root/'analysis_ready/schema.json'
    if not extract.exists() or not specs.exists():
        return {'status':'BLOCKED','reason':'extract or scope specification missing'}
    descriptions=json.loads(specs.read_text())
    books={name:xlrd.open_workbook(sources[name],on_demand=True) for name in {d['file'] for d in descriptions} if name in sources}
    sheets={}
    for d in descriptions:
        if d['file'] not in books:
            continue
        s=books[d['file']].sheet_by_name(d['sheet'])
        bitmap=bytearray(s.nrows*s.ncols)
        for r,c in expected_cells(s,d):
            bitmap[r*s.ncols+c]=1
        sheets[d['file'],d['sheet']]=(s,d,bitmap)
    stats=Counter()
    fields=Counter()
    bysheet=defaultdict(Counter)
    rates=defaultdict(dict)
    standardized=[]
    logical=set()
    population={}
    comparison=defaultdict(dict)
    with gzip.open(extract,'rt',encoding='utf8',newline='') as f:
        for row in csv.DictReader(f):
            stats['rows']+=1
            name,tab=row['source_filename'],row['sheet']
            if (name,tab) not in sheets:
                stats['blocked_source_rows']+=1
                continue
            s,d,seen=sheets[name,tab]
            addr=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',row['source_cell'])
            if not addr:
                stats['invalid_coordinates']+=1
                continue
            r,c=int(addr[2])-1,colnum(addr[1])
            if r>=s.nrows or c>=s.ncols:
                stats['invalid_coordinates']+=1
                continue
            pos=r*s.ncols+c
            if seen[pos] in (0,3):
                stats['out_of_scope']+=1
            if seen[pos] in (2,3):
                stats['coordinate_duplicates']+=1
            seen[pos]=2 if seen[pos] in (1,2) else 3
            raw=s.cell_value(r,c)
            header=s.cell_value(0,c)
            value=num(raw)
            matched=equivalent(raw,row['raw_value'])
            stats['raw_match' if matched else 'raw_difference']+=1
            stats['numeric_match' if (equivalent(value,row['value']) if value is not None else row['value']=='')
                  else 'numeric_difference']+=1
            source_year=header if d['mode']=='year' else s.cell_value(r,d['dims']['year'])
            checks={'year': equivalent(source_year,row['year']),
                    'scope':d['scope']==row['source_scope'],
                    'raw_age':str(header)==row['age_raw'] if d['mode']=='age' else True,
                    'source_sha256': sources[name].name.startswith(row['source_sha256'][:12]),
                    'measure':d['measure']==row['measure'] if d['mode']!='detail' else True}
            for key in ('prefecture','prefecture_code','site','site_code','icd10','sex','standard_population'):
                if key in d['dims']:
                    field={'sex':'sex_raw','standard_population':'standard_population_raw'}.get(key,key)
                    original=s.cell_value(r,d['dims'][key])
                    checks[field]=equivalent(original,row[field])
            measure=d['measure']
            standard=d['standard']
            if 'standard_population' in d['dims']:
                standard=normalized_standard(s.cell_value(r,d['dims']['standard_population']))
            if d['mode']=='detail':
                measure='incidence_asr' if '年齢調整' in header else 'incidence_rate' if '率' in header else 'incidence_count'
                standard=normalized_standard(header)
            unit={'incidence_count':'registered_incidence_count','mortality_count':'deaths','population':'persons'}.get(measure,'per_100000')
            sex={'男女計':'total','総数':'total','男':'male','女':'female'}.get(word(s.cell_value(r,d['dims']['sex'])))
            age='0-74' if measure=='mortality_asr75' else normalized_age(header) if d['mode']=='age' else 'all_ages'
            period='calendar_year' if measure=='population' else 'death_year' if measure.startswith('mortality') else 'diagnosis_year'
            state='reported_zero' if value==0 else 'reported' if value is not None else 'dash_unresolved' if word(raw) in ('-','‐','−','―','–','—') else None
            checks.update(unit=unit==row['unit'],sex=sex==row['sex'],age=age==row['age_group'],
                          reprint=str(d['mode']=='age' and ('再掲' in str(header) or '合計' in str(header)))==row['age_is_reprint'],
                          standardized=standard==row['standard_population'], normalized_measure=measure==row['measure'],
                          period_type=period==row['period_type'],value_status=state==row['value_status'])
            for key,ok in checks.items():
                fields[key+':checked']+=1
                if not ok:fields[key+':difference']+=1
            bysheet[name+'|'+tab]['observed']+=1
            logical_key=tuple(row[k] for k in ('source_scope','measure','year','prefecture_code','site_code',
                                               'site','icd10','sex','age_group','standard_population'))
            if logical_key in logical:
                stats['logical_duplicate_rows']+=1
            logical.add(logical_key)
            scope=row['source_scope']
            measure=row['measure']
            age=row['age_group']
            if measure in ('incidence_asr','mortality_asr75') and scope!='incidence_national_detail':
                standardized.append((scope,row['prefecture_code'],row['year'],row['sex'],row['site_code'],row['standard_population'],value))
            if scope in ('incidence_national','incidence_prefecture','mortality_prefecture') and d['mode']=='age':
                geo=(scope,row['prefecture_code'],row['year'],row['sex'],age)
                if measure=='population':
                    population[geo]=value
                elif measure.endswith(('_rate','_count')):
                    rates[geo+(row['site_code'],)][measure.rsplit('_',1)[-1]]=value
                if scope.startswith('incidence') and row['prefecture_code'] in ('','0'):
                    comparison[measure,row['year'],row['sex'],age,row['site_code']][scope]=value
    for (name,tab),(_,_,seen) in sheets.items():
        key=name+'|'+tab
        bysheet[key]['missing_source_cells']=seen.count(1)
        bysheet[key]['in_scope_seen']=seen.count(2)
    arithmetic=Counter()
    for (*geo,_site),vals in rates.items():
        denom=population.get(tuple(geo))
        group=geo[0]
        count,rate=vals.get('count'),vals.get('rate')
        if count is None or rate is None or not denom:
            arithmetic[group+':held']+=1
        elif abs(count/denom*100000-rate)<=1e-7:
            arithmetic[group+':match']+=1
        else:
            arithmetic[group+':difference']+=1
    weights={
        'japan_1985':(8180,8338,8497,8655,8814,8972,9130,9289,9400,8651,7616,6581,5546,4511,3476,2441,1406,784),
        'world':(12,10,9,9,8,8,6,6,6,6,5,4,4,3,2,1,.5,.5),
        'japan_2015':(5026,5369,5711,6053,6396,6738,7081,7423,7766,8108,8451,8793,9135,9246,7892,6306,4720,3134,1548,423)}
    for scope,pref,year,sex,site,standard,published in standardized:
        if scope=='mortality_site_prefecture':
            arithmetic[scope+':held_no_age_specific_counts']+=1
            continue
        w=weights.get(standard)
        if standard in ('world_segi','segi','world_segi_1960'):
            w=weights['world']
        if w is None:
            arithmetic[scope+':unmapped_standard:'+standard]+=1
            continue
        if scope=='mortality_prefecture':
            w=w[:15]
        age=[f'{5*i}-{5*i+4}' for i in range(len(w))]
        if len(w)==18:
            age[-1]='85+'
        if len(w)==20:
            age[-1]='95+'
        values=[rates.get((scope,pref,year,sex,a,site),{}).get('rate') for a in age]
        key=scope+':ASR:'+standard+(':approximation' if len(w)==20 else '')
        if published is None or any(v is None for v in values):
            arithmetic[key+':held']+=1
        elif abs(sum(v*n for v,n in zip(values,w))/sum(w)-published)<=1e-7:
            arithmetic[key+':match']+=1
        else:
            arithmetic[key+':difference']+=1
    for a in comparison.values():
        if len(a)==2:
            x,y=a.values()
            arithmetic['national_vs_prefecture:'+('held' if x is None or y is None else 'match' if abs(x-y)<=1e-7 else 'difference')]+=1
    return {'counts':dict(stats),'metadata':dict(fields),'coverage':bysheet,'arithmetic':dict(arithmetic),
            'absolute_tolerance':1e-7,'age_standardized':'2015 is approximate; site mortality not recalculated','extract_hash_matches':sha(extract)==EXPECTED}


HBCR_FILES={
 'HBCR_2022_discovery_page124.csv':('registration_count',260),
 'HBCR_2022_discovery_page125.csv':('registration_count',480),
 'HBCR_2022_prostate_monthly.csv':('registration_count',120),
 'HBCR_2022_stage_counts.csv':('count',255),
 'HBCR_2022_treatment_monthly.csv':('count',300),
 'HBCR_2022_treatment_annual.csv':('count',25),
 'HBCR_2022_site_treatment_annual.csv':('count',210),
 'HBCR_2023_stage_counts.csv':('count',210),
 'HBCR_2023_discovery_annual.csv':('registration_count',40),
 'HBCR_treatment_interval_candidates.csv':('days',29),
}


def hbcr(root,sources,out):
    results={}
    cache={}
    intervals=[]
    for name,(metric,expect) in HBCR_FILES.items():
        path=root/'hbcr_priority_review'/name
        stats=Counter()
        if not path.exists():
            results[name]={'status':'BLOCKED'}
            continue
        with path.open(encoding='utf-8-sig',newline='') as f:
            for i,row in enumerate(csv.DictReader(f),2):
                stats['rows']+=1
                pdfname=(row.get('source_filename') or row['source_url'].split('/')[-1])
                page=int(float(row['pdf_page']))
                key=(pdfname,page)
                if key not in cache:
                    if pdfname in sources:
                        with fitz.open(sources[pdfname]) as pdf:
                            cache[key]=pdf[page-1].get_text() if 0<page<=len(pdf) else ''
                    else:
                        cache[key]=None
                text=cache[key]
                if text is None:
                    stats['blocked_source_rows']+=1
                    continue
                value=num(row.get(metric))
                tokens={int(v.replace(',','')) for v in re.findall(r'(?<![.\d])\d{1,3}(?:,\d{3})+|(?<![.,\d])\d+(?![.,\d])',word(text))}
                stats['page_token_found' if value is not None and value in tokens else 'page_token_not_found']+=1
                if metric=='days':
                    intervals.append((i,row.get('year'),row.get('site'),row.get('statistic'),page,
                                      'DEFINITION_PENDING','病期・年齢・起点・終点・対象施設は独立同定未完'))
        results[name]={'status':'PARTIALLY_REPRODUCED','expected_reference':expect or None,**stats}
        if metric!='days' and 'pdfname' in locals() and pdfname in sources:
            with path.open(encoding='utf-8-sig',newline='') as f:
                results[name]['table_reconciliation']=reconcile(name,csv.DictReader(f),sources[pdfname])
    write_csv(out/'hbcr_interval_definition_audit.csv',['csv_row','year','site','statistic','pdf_page','status','reason'],intervals)
    return {'files':results,'limit':'Table counts and keys checked where layout is recognized. Additional PDF keys can include out-of-scope sections; denominator and interval definitions remain pending.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    start=now()
    def save(name,obj):
        tmp=out/(name+'.tmp')
        tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        tmp.replace(out/name)
    def event(phase, status):
        with (out/'execution_log.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(dict(at_jst=now(),phase=phase,status=status))+'\n')
    event('integrity','started')
    sources,counts=inventory(args.root,out)
    event('integrity','finished')
    save('audit_summary.json',dict(started_jst=start,integrity=counts,status='PENDING_QA'))
    event('national','started')
    result=national(args.root,out,sources)
    for target,key in [('source_cell','counts'),('metadata','metadata'),('completeness','coverage'),('rate_recalculation','arithmetic')]:
        save('national_'+target+'_audit.json',result.get(key,result))
    event('national','finished')
    hospital=hbcr(args.root,sources,out)
    save('hbcr_source_reconciliation.json',hospital)
    event('hbcr','finished')
    errata=[]
    for year in (2019,2020,2022,2023):
        for suffix in ('report','syusei'):
            name=f'{year}_{suffix}.pdf'
            url='https://ganjoho.jp/public/qa_links/report/hosp_c/pdf/'+name
            local=sha(sources[name]) if name in sources else ''
            try:
                with urlopen(url,timeout=30) as response:
                    content=response.read()
                if not content.startswith(b'%PDF'):
                    raise ValueError('expected PDF')
                online=hashlib.sha256(content).hexdigest()
                status='byte_match' if local==online else 'difference' if local else 'no_saved_baseline'
            except (OSError,ValueError):
                online=''
                status='fetch_error'
            errata.append((year,name,url,local,online,status,'ERRATA_PENDING'))
    write_csv(out/'errata_impact_audit.csv',['year','document','url','saved_sha256','online_sha256','comparison','impact_status'],errata)
    event('errata','finished')
    original_manifest=args.root/'metadata/manifest.json'
    if original_manifest.exists():
        raw_manifest=json.loads(original_manifest.read_text())
        save('source_manifest.json',[{k:r[k] for k in ('filename','source_url','institution','bytes','sha256','retrieved_at_jst','redistribution_status')}
                                     for r in raw_manifest])
    with gzip.open(out/'discrepancies.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['check','count','kind'])
        for section in ('counts','metadata','arithmetic'):
            for key,value in result.get(section,{}).items():
                if any(token in key for token in ('difference','duplicate','held','blocked','invalid','out_of_scope')) and value:
                    writer.writerow([key,value,'aggregate'])
    save('audit_summary.json',dict(started_jst=start,finished_jst=now(),integrity=counts,national=result,
                                   hbcr=hospital,status='PENDING_QA',code_sha256=sha(Path(__file__))))


if __name__=='__main__':
    main()

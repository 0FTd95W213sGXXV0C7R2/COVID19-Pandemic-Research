"""Build conservative, source-addressed longitudinal audit tables."""
import csv
import gzip
import io
import re
from collections import Counter
from contextlib import ExitStack, contextmanager
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook
from build_dpc_audit_tables import clean, read_book

REL = Path('non_covid_access/ndb_dpc_longitudinal')
AUDIT, RAW, OUT = (Path('data') / name / REL for name in ('audits','raw','processed'))
PREVIOUS = Path('data/audits/non_covid_access/ndb_open_data')
COUNTS = Path('data/processed/non_covid_access/ndb_open_data/claims_counts.csv.gz')
FEES = {'111000110':'A000','112007410':'A001','112011310':'A002'}
GROUPS = {'内視鏡検査':'D','CT・MRI':'E','病理診断':'N','悪性腫瘍関連手術':'K','放射線治療':'M',
          '化学療法関連診療行為':'BG','PCI':'K','CABG':'K','脳血管内治療':'K','脳卒中関連診療行為':'HK',
          'リハビリテーション':'H'}


def records(path):
    op = gzip.open if path.suffix=='.gz' else open
    with op(path,'rt',encoding='utf-8',newline='') as stream:
        yield from csv.DictReader(stream)


@contextmanager
def output(path, headers):
    op = gzip.open if path.suffix=='.gz' else open
    with op(path,'wt',encoding='utf-8',newline='') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(headers.split())
        yield writer.writerow


def excluded_2023():
    source = RAW/'r10_excluded.zip'
    with ZipFile(source) as z:
        for member in z.namelist():
            if '初再診料_' not in member or not member.endswith('.xlsx'):
                continue
            if ('都道府県別' not in member and '診療月別' not in member):
                continue
            axis = 'month' if '診療月別' in member else 'prefecture'
            book = load_workbook(io.BytesIO(z.read(member)),read_only=True,data_only=True)
            sheet = book['外来']
            rows = sheet.values
            next(rows)
            next(rows)
            header = next(rows)
            next(rows)
            index = next(i for i,v in enumerate(header) if clean(v)=='診療行為コード')
            total = next(i for i,v in enumerate(header) if clean(v).startswith('総計'))
            for row, cells in enumerate(rows,5):
                code = clean(cells[index])
                if code not in FEES:
                    continue
                for c in range(total,len(header)):
                    dim = clean(header[c])
                    match = re.fullmatch(r'(\d+)月',dim)
                    if match:
                        month=int(match[1])
                        dim=f'{2023+(month<4)}-{month:02}'
                    if axis=='prefecture' and c!=total or axis=='month' and not match:
                        continue
                    raw=cells[c]
                    yield dict(fiscal_year='2023',release='10',scope='public_funding_excluded',section='A',
                               axis=axis,source=str(source),member=member,sheet='外来',row=row,column=c+1,
                               procedure_code=code,label=cells[index+1],points=cells[index+2],dimension=dim,
                               raw_value=raw,count=raw if isinstance(raw,(int,float)) else '',
                               status='numeric' if isinstance(raw,(int,float)) else 'unresolved_symbol')
            book.close()


def build_ndb():
    with ZipFile(RAW/'fee_master.zip') as z:
        master = {r[2]:r for r in csv.reader(z.read(z.namelist()[0]).decode('cp932').splitlines()) if len(r)>12}
    candidates = []
    for r in records(COUNTS):
        if (r['procedure_code'] in FEES and r['sheet']=='外来' and r['section']=='A'
                and int(r['fiscal_year'])>=2017
                and ((r['axis']=='prefecture' and r['dimension'].startswith('総計'))
                     or (r['axis']=='month' and re.fullmatch(r'20\d{2}-\d{2}',r['dimension'])
                         and r['dimension']<='2024-12'))):
            candidates.append(r)
    candidates.extend(excluded_2023())
    observed = {(r['fiscal_year'],r['procedure_code'],str(r['points']),r['label']) for r in candidates}
    with output(AUDIT/'procedure_decisions.csv','group code fee_section year published_name published_points master_name decision rationale') as put:
        for year,code,points,label in sorted(observed):
            put(('初診・再診',code,FEES[code],year,label,points,master[code][4],'conditional',
                 '本体算定コード単独。別コード・加算・診断推定を含めない'))
        for group,section in GROUPS.items():
            put((group,'',section,'2017–2024','','','','pending','改定時点別の算定要件と代替コードが未確定'))
    keys = set()
    with ExitStack() as stack:
        writers = {grain:stack.enter_context(output(OUT/f'ndb_{grain}.csv',
                   'period fiscal_year code fee_section label points payer_series source_scope comparison_segment raw_value count status source member sheet row column'))
                   for grain in ('fiscal_year','month')}
        for r in sorted(candidates,key=lambda v:(v['fiscal_year'],v['procedure_code'],v['scope'],v['axis'],v['dimension'])):
            grain = 'month' if r['axis']=='month' else 'fiscal_year'
            period = r['dimension'] if grain=='month' else r['fiscal_year']
            payer = 'includes_public' if r['scope']=='public_funding_included' else 'excludes_public_only'
            key = (grain,period,r['procedure_code'],payer)
            if key in keys:
                raise ValueError(f'Duplicate NDB observation {key}')
            keys.add(key)
            # Each release/code/point combination stays separable, including FY2024’s in-year change.
            segment = f"{payer}:{r['fiscal_year']}:{r['procedure_code']}:{r['points']}"
            writers[grain]((period,r['fiscal_year'],r['procedure_code'],FEES[r['procedure_code']],r['label'],
                            r['points'],payer,r['scope'],segment,r['raw_value'],r['count'],r['status'],
                            r['source'],r['member'],r['sheet'],r['row'],r['column']))


def disease(icd):
    if re.fullmatch(r'C\d\d.*',icd):
        return '悪性新生物'
    return {'I21':'急性心筋梗塞','I63':'脳梗塞','I61':'脳内出血','I60':'くも膜下出血'}.get(icd[:3],'')


def build_dpc():
    selected = set()
    with output(AUDIT/'disease_definitions.csv','edition disease dpc6 icd10 icd_label change_flag reserved valid_from valid_to source sheet row') as put:
        for path in sorted(RAW.glob('dpc_*.xlsx')):
            book=load_workbook(path,read_only=True,data_only=True)
            sheet=book['４）ＩＣＤ']
            rows=list(sheet.values)
            if not clean(rows[0][3]).startswith('ICD'):
                raise ValueError(path)
            for i,r in enumerate(rows[2:],3):
                icd=clean(r[3])
                name=disease(icd)
                if name:
                    code=clean(r[0])+clean(r[1])
                    selected.add(code)
                    put((path.stem[-4:],name,code,icd,r[2],r[4],'',r[5],r[6],path,sheet.title,i))
            book.close()

    counts=Counter()
    with ExitStack() as stack:
        emit=stack.enter_context(output(OUT/'dpc_annual_detail.csv.gz',
               'fiscal_year table entity disease_code label surgery metric raw_value value status source sheet row column comparison_segment'))
        facilities=stack.enter_context(output(AUDIT/'facility_correspondence.csv',
                     'fiscal_year local_id public_notice_id municipality prefecture name submitted_months external_facility_code linkage_status source sheet row'))
        for src in records(PREVIOUS/'dpc_medias_manifest.csv'):
            title,source,year=src['title'],src['path'],int(src['period'][:4])
            is_los='診断群分類別在院日数' in title
            is_detail=any(f'疾患別手術別集計_MDC{i}' in title for i in ('01','05'))
            if not (is_los or is_detail or '施設概要表' in title):
                continue
            for sheet, rows in read_book(source):
                if not rows:
                    continue
                if '施設概要表' in title and any('施設名' in clean(v) for v in rows[0]):
                    month=next((i for i,v in enumerate(rows[0]) if '提出月数' in clean(v)),None)
                    for i,r in enumerate(rows[1:],2):
                        if len(r)>=5 and re.fullmatch(r'\d{5}(?:\.0)?',clean(r[1])):
                            facilities((year,*[r[c] for c in (1,0,2,3,4)],r[month] if month is not None else '',
                                        '','within_year_only',source,sheet,i))
                    continue
                def cell(row,col,table,entity,code,name,surgery,metric):
                    val=rows[row-1][col]
                    raw='' if val is None else val
                    number=raw if isinstance(raw,(int,float)) else ''
                    status=('zero' if number==0 else 'numeric') if number!='' else ('blank' if raw=='' else 'withheld_or_unresolved')
                    emit((year,table,entity,code,name,surgery,metric,raw,number,status,source,sheet,row,col+1,f'FY{year}'))
                    counts[year,table,status]+=1
                if is_los and '診断群分類番号' in clean(rows[0][0]):
                    yhead=f'平成{year-1988}年度' if year<2019 else ('令和元年度' if year==2019 else f'令和{year-2018}年度')
                    enabled=False
                    entity=''
                    cols=[]
                    for c in range(2,len(rows[2])):
                        if clean(rows[0][c]):
                            enabled=clean(rows[0][c])==yhead
                        entity=rows[1][c] or entity
                        metric=clean(rows[2][c])
                        if enabled and metric in ('件数','平均値'):
                            cols.append((c,entity,metric))
                    if not cols:
                        raise ValueError(f'No current-year columns: {source}')
                    for i,r in enumerate(rows[3:],4):
                        code=clean(r[0])
                        if re.fullmatch(r'\d{6}[0-9a-zA-Z]{8}',code):
                            for c,entity,metric in cols:
                                cell(i,c,'dpc14_length_of_stay',entity,code,r[1],'',metric)
                if is_detail and len(rows)>4 and clean(rows[3][1])=='通番':
                    code=name=metric=''
                    cols=[]
                    for c,surgery in enumerate(rows[3][3:],3):
                        code=clean(rows[0][c]) or code
                        name=rows[1][c] or name
                        metric=clean(rows[2][c]) or metric
                        if code in selected and clean(surgery) and '再掲' not in clean(surgery) and metric in ('件数','在院日数'):
                            cols.append((c,code,name,surgery,metric))
                    for i,r in enumerate(rows[4:],5):
                        if re.fullmatch(r'\d{5}(?:\.0)?',clean(r[1])):
                            for c,code,name,surgery,metric in cols:
                                cell(i,c,'mdc01_05_disease_surgery',r[1],code,name,surgery,metric)
    with output(AUDIT/'dpc_quality_flags.csv','fiscal_year table status rows') as put:
        for k,n in sorted(counts.items()):
            put((*k,n))


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    build_ndb()
    build_dpc()

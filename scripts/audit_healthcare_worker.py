"""Extract explicitly located published aggregates and check source bytes and ratios."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from lxml import html

from acquire_healthcare_worker import now

REGULAR = '正規雇用看護職員離職率'
NEW = '新卒採用者離職率'
EXPERIENCED = '既卒採用者離職率'


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).split())


def located(pages, pattern):
    for number,page in enumerate(pages,1):
        match = re.search(pattern,page)
        if match:
            return number,match
    raise ValueError(pattern)


def pdf_pages(path):
    text = subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
    return [normalized(p) for p in text.split('\f')]


def nursing(path):
    pages = pdf_pages(path)
    survey_year = int(path.stem[-4:])
    rates = []
    for metric in ((REGULAR,NEW) if survey_year<=2018 else (REGULAR,NEW,EXPERIENCED)):
        label = "新卒看護職員離職率" if metric==NEW and survey_year<=2018 else metric
        page, m = located(pages,rf'{label}\s+(?:(\d[\d,]*)\s+)?(\d+\.\d)%')
        period = str(survey_year-1)+'年度'
        body = pages[page-1]
        def count(label):
            matches = re.findall(rf'{label}\s+(?:[\d,]+\s+)?([\d,]+) 人',body)
            if len(matches)!=1:
                raise ValueError((path.name,label,matches))
            return int(matches[0].replace(',',''))
        if metric==REGULAR:
            numerator = count('の総退職者数')
            denominator = count('の正規雇用看護職員数') + (
                count('の新卒採用者数') + count('の既卒採用者数') - numerator)/2
        else:
            group = '新卒' if metric==NEW else '既卒'
            numerator = count(f'退職した{group}採用者数')
            denominator = count(f'の{group}採用者数')
        rates.append([path.name,metric,period,m[2],'%',numerator,denominator,m[1],f'PDF p.{page}'])
    target_page,target = located(pages,r'全国(?:の病院)?\s*(8,[0-9]{3})\s*(?:病院|施設)')
    response_page,response = located(pages,r'有効回収数\s*([\d,]+)\s*\(有効回収率\s*(\d+\.\d)%')
    if survey_year == 2024:
        page,_ = located(pages,r'表 41 一般病棟に勤務する看護職員の夜勤状況.*?83,195 人.*?34\.3%')
        rates.append([path.name,'月72時間超夜勤者率','2024-09','34.3','%',83195,242355,2035,f'PDF p.{page} 表41'])
        page,_ = located(pages,r'表 46 正規雇用看護職員を対象に導入している多様な働き方.*?1,090 31\.9%')
        rates.append([path.name,'短時間勤務正職員制度導入病院率','2024年調査','31.9','%',1090,3417,3417,f'PDF p.{page} 表46'])
    return rates,dict(invited=target[1],responded=response[1],response_rate=response[2],
                      sample_unit='病院',sample_locator=f'PDF p.{target_page}, {response_page}')


def html_records(root):
    specs = {
        '10020069': [
            ('COVID-19関連差別経験割合','2020-10～2021-03','8.4',484,5703,'Results・表1',r'484\s*\(8\.4%\)'),
            ('重度心理的苦痛（K6≥13）','2020-10～2021-03','8.5',486,5703,'Results・表3',r'486\s*\(8\.5%\)')],
        '8590925': [
            ('ICU職員の偏見・差別経験','2020-07-06～19','38.1',None,189,'Results',r'38\.1% answered')],
        '11027999': [
            ('抗N抗体陽性割合','2023-06-07～19','54.1',1944,3594,'表1',r'1944\s*\(54\.1\)'),
            ('PCR陽性既往割合','2023年健診時まで','37.1',1335,3594,'Results',r'1,335\s*\(37\.1%\)')],
    }
    result = []
    records = {}
    for pmc,spec in specs.items():
        name = f'pmc_{pmc}.html'
        tree = html.parse(root/name)
        doc = normalized(tree.getroot().text_content())
        for metric,period,value,n,d,loc,pattern in spec:
            if not re.search(pattern,doc):
                raise ValueError((name,pattern))
            result.append([name,metric,period,value,'%',n,d,None,loc])
        records[name] = {k:tree.xpath('//meta[@name=$k]/@content',k='citation_'+k)
                         for k in ('title','author','doi','publication_date')}
    iasr = [
        ('iasr_sapporo.html','A病棟看護師の感染','2020-04',19,28,r'看護師28名中19名が感染'),
        ('iasr_sapporo.html','A病棟看護師の濃厚接触','2020-04',9,28,r'9名が濃厚接触者'),
        ('iasr_kochi.html','クラスター職員陽性者数','2022-01-14～02-28',60,None,r'職員陽性例\(n=60\)'),
    ]
    for name,metric,period,value,scope,pattern in iasr:
        tree = html.parse(root/name)
        if not re.search(pattern,normalized(tree.getroot().text_content())):
            raise ValueError((name,pattern))
        result.append([name,metric,period,str(value),'人',None,scope,None,'IASR本文'])
    return result,records


def selected_pdf_rows(root):
    name = 'jma_2022.pdf'
    pages = pdf_pages(root/name)
    page,_ = located(pages,r'抑うつ症状尺度QIDS中等度以上\s+8\.7%\s+6\.5%\s+8\.8%')
    result = [[name,'QIDS中等度以上','2021-12～2022-01','8.8','%',None,None,None,f'PDF p.{page}']]
    page,_ = located(pages,r'最近1か月間で休日なし\s+8\.7%\s+5\.8%\s+6\.3%')
    result.append([name,'直近1か月の休日なし','2021-12～2022-01','6.3','%',None,None,None,f'PDF p.{page}'])
    name = 'mhlw_2019.pdf'
    pages = pdf_pages(root/name)
    page,_ = located(pages,r'3,967施設\s*\(回収率20\.8%\)')
    result.append([name,'医師勤務調査・施設回収率','2019-09-02～08','20.8','%',3967,19112,3967,f'PDF p.{page}'])
    page,_ = located(pages,r'今回調査の上位10%\(時間外年1,824時間換算\)')
    result.append([name,'病院常勤医の時間外労働上位10%境界・年換算','2019-09-02～08',
                   '1824','時間',None,None,None,f'PDF p.{page} 公表換算値'])
    name = 'work_compensation.pdf'
    page,m = located(pdf_pages(root/name),r'医療従事者等 (195,724) \(46\) (182,415) \(42\) (181,944)')
    for label,value in zip(('労災請求累計','労災決定累計','労災支給決定累計'),m.groups()):
        result.append([name,label,'2025-03-31現在',value.replace(',',''),'件',None,None,None,f'PDF p.{page}'])
    name = 'estat_employment_2024.pdf'
    page,m = located(pdf_pages(root/name),r'医療,福祉 1,158\.6 (1,135\.4)')
    result.append([name,'医療・福祉産業の離職者数','2024年',m[1].replace(',',''),'千人',None,None,None,f'PDF p.{page}'])
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('originals','manifest','output'):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    started = now()
    manifest = json.loads(args.manifest.read_text())
    for row in manifest:
        if row['status']=='acquired':
            data = (args.originals/row['filename']).read_bytes()
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
                raise ValueError(row['filename'])
    all_rows = []
    samples = {}
    for p in sorted(args.originals.glob('jna_20[0-9][0-9].pdf')):
        rows,sample = nursing(p)
        all_rows.extend(rows)
        samples[p.name] = sample
    article_rows,metadata = html_records(args.originals)
    all_rows.extend(article_rows)
    all_rows.extend(selected_pdf_rows(args.originals))
    if len({tuple(r[:3]) for r in all_rows})!=len(all_rows):
        raise ValueError('duplicate observation')
    checks = []
    for filename,metric,period,value,unit,n,d,_,_ in all_rows:
        if unit=='%' and n is not None and d:
            calculated = n/d*100
            checks.append(dict(filename=filename,metric=metric,reported=value,calculated=calculated,
                               pass_at_one_decimal=abs(calculated-float(value))<=0.05000001))
    with (args.output/'healthcare_worker_published_aggregates.csv').open('w',newline='') as f:
        w = csv.writer(f,lineterminator='\n')
        w.writerow(['filename','metric','period','published_value','unit','numerator','denominator_or_candidate',
                    'metric_reporting_facilities','source_locator'])
        w.writerows(all_rows)
    data = dict(started_at_jst=started,finished_at_jst=now(),published_rows=len(all_rows),
                source_hash_checks=sum(r['status']=='acquired' for r in manifest),
                ratio_checks=checks,nursing_sample=samples,article_metadata=metadata)
    (args.output/'healthcare_worker_quality_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    main()

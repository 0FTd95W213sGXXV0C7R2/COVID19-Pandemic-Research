#!/usr/bin/env python3
"""Acquire public weekly reports with numeric tables and preserve publication vintages."""
import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import quote, urljoin
from urllib.request import urlopen

from build_mhlw_resource_handoff import OUT, ROOT, now, write
from pathlib import Path

ARCHIVE = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00438.html"
PUBLIC = [
    ("crisis_public_page","https://crisis.ecmonet.jp/en-general/","html"),
    ("ecmonet_crisis","https://www.ecmonet.jp/crisis","html"),
    ("crisis_application","https://www.ecmonet.jp/archives/crisis-data","html"),
    ("crisis_rules","https://www.ecmonet.jp/wp-content/themes/Ecmonet/assets/files/"+quote("CRISISデータ利用要領.pdf"),"pdf"),
    ("jsicm_index","https://www.jsicm.org/covid-19.html","html"),
]
WEEK = r"第\s*(\d+)\s*週\s*\(\s*(\d{1,2})/(\d{1,2})\s*[-~〜～－–]\s*(\d{1,2})/(\d{1,2})\s*\)"
NUMBER = r"([\d,]+)"
TABLE_ROW = re.compile(r"^\s*"+WEEK+r"\s+"+NUMBER+r"\s+"+WEEK+r"\s+"+NUMBER+r"\s+"+NUMBER+r"\s*$")


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = ""
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag=="a":
            self.href=dict(attrs).get("href","")
            self.label=[]

    def handle_data(self,data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            label=unicodedata.normalize("NFKC","".join(self.label))
            self.links.append((self.href,label))
            self.href=""


def fetch(spec, directory):
    identifier,url,kind=spec
    row=dict(id=identifier,url=url,format=kind,retrieved_at_jst=now(),http_status="",mime="",size="",sha256="",status="failed",error="")
    try:
        with urlopen(url,timeout=18) as response:
            data=response.read()
            row.update(http_status=response.status,mime=response.headers.get("Content-Type",""))
        if kind=="pdf" and not data.startswith(b"%PDF-") or kind=="xlsx" and not data.startswith(b"PK"):
            raise ValueError("Unexpected response format")
        if kind=="html" and b"<html" not in data.lower():
            raise ValueError("Unexpected response format")
        (directory/f"{identifier}.{kind}").write_bytes(data)
        row.update(size=len(data),sha256=hashlib.sha256(data).hexdigest(),status="downloaded")
        return row,data
    except (OSError,ValueError) as exc:
        if isinstance(exc,HTTPError):
            row["http_status"]=exc.code
        row["error"]=str(exc)
        return row,b""


def reports(html):
    parser=Anchors()
    parser.feed(html.decode())
    sources=[]
    for path,label in parser.links:
        found=re.search(r"2023年\s*(\d+)月\s*(\d+)日",label)
        if path.endswith(".pdf") and found and "発生状況" in label:
            day=date(2023,int(found[1]),int(found[2]))
            if date(2023,6,1)<=day<=date(2023,10,6):
                sources.append((day.isoformat(),urljoin(ARCHIVE,path),"pdf"))
        if path.endswith("001154303.xlsx"):
            sources.append(("sentinel_new_admissions",urljoin(ARCHIVE,path),"xlsx"))
    return sorted(set(sources))


def extract(path, source):
    text=subprocess.run(["pdftotext","-layout",str(path),"-"],capture_output=True,check=True).stdout.decode()
    records=[]
    for page, layout in enumerate(unicodedata.normalize("NFKC",text).split("\f"),1):
        dense=re.sub(r"\s+","",layout)
        if not ("ICU入院中の患者数" in dense and "7日間平均" in dense and "新規入院患者数" in dense):
            continue
        cutoff_day=re.search(r"令和5年\s*(\d+)月\s*(\d+)日\s*(\d+)\s*時時点",layout)
        for line in layout.splitlines():
            match=TABLE_ROW.fullmatch(line)
            if not match:
                continue
            left,right=match.groups()[:5],match.groups()[6:11]
            if left!=right:
                raise ValueError(f"Mismatched printed week columns: {source['url']} p{page}")
            wk,m,d,endm,endd=map(int,left)
            start=date(2023,m,d)
            end=date(2023,endm,endd)
            if start.isocalendar().week!=wk or start.weekday()!=0 or (end-start).days!=6:
                raise ValueError(f"Invalid printed week: {source['url']} p{page}")
            values=[int(match[index].replace(",","")) for index in (6,12,13)]
            records.append(dict(week=wk,start=start.isoformat(),end=end.isoformat(),publication_date=source["id"],
                data_cutoff_jst=(f"2023-{int(cutoff_day[1]):02}-{int(cutoff_day[2]):02} {int(cutoff_day[3]):02}:00" if cutoff_day else ""),
                page=page,url=source["url"],sha256=source["sha256"],new_admissions_week_total=values[0],
                icu_current_patients_7d_average=values[1],ecmo_or_ventilator_current_patients_7d_average=values[2]))
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir",type=Path,required=True)
    args=parser.parse_args()
    directory=args.private_dir.resolve()
    if directory.is_relative_to(ROOT):
        parser.error("Originals must be stored outside Git")
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    OUT.mkdir(exist_ok=True)
    start=now()
    archive,html=fetch(("press_archive",ARCHIVE,"html"),directory)
    specs=reports(html) if html else []
    with ThreadPoolExecutor(max_workers=8) as pool:
        batch=list(pool.map(lambda item:fetch(item,directory),specs+PUBLIC))
    data=[]
    documents=[dict(**archive,table_rows=0,public_numeric_download_links="")]
    for source,body in batch:
        series=extract(directory/(source["id"]+".pdf"),source) if source["status"]=="downloaded" and source["id"][:4]=="2023" else []
        data.extend(series)
        anchors=Anchors()
        if body and source["format"]=="html":
            anchors.feed(body.decode(errors="replace"))
        links=[urljoin(source["url"],url) for url,_ in anchors.links if re.search(r"\.(csv|xlsx?|json)(?:[?#]|$)",url,re.I)]
        documents.append(dict(**source,table_rows=len(series),public_numeric_download_links="|".join(links)))
    write(OUT/"critical_care_acquisition.csv",documents)
    if not data:
        raise SystemExit("No numeric tables; see acquisition manifest")
    keys={(row["publication_date"],row["week"]) for row in data}
    if len(keys)!=len(data):
        raise ValueError("Duplicate week within publication")
    latest={}
    for row in sorted(data,key=lambda row:(row["week"],row["publication_date"])):
        latest[row["week"]]=row
    write(OUT/"gmis_critical_care_weekly_vintages.csv",data)
    write(OUT/"gmis_critical_care_weekly_latest.csv",list(latest.values()))
    result=dict(start_jst=start,end_jst=now(),downloaded=sum(row["status"]=="downloaded" for row in documents),
         targets=len(documents),numeric_report_count=sum(row["table_rows"]>0 for row in documents),
         week_count=len(latest),vintage_count=len(data),first=min(row["start"] for row in data),last=max(row["end"] for row in data))
    (OUT/"critical_care_summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print(result)


if __name__=="__main__":
    main()

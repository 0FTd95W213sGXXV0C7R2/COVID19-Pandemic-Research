#!/usr/bin/env python3
"""Discover annual Hospital Report tables on e-Stat and preserve official bytes."""
import argparse
import csv
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/audits/non_covid_access/hospital_report_2017_2024"
RAW = ROOT / "data/raw/non_covid_access/hospital_report_2017_2024"
ESTAT = "https://www.e-stat.go.jp"
INDEX = ESTAT + "/stat-search/files?toukei=00450023&tstat=000001030749"
TERMS = ESTAT + "/terms-of-use"
MHLW = "https://www.mhlw.go.jp"
JST = ZoneInfo("Asia/Tokyo")
YEARS = {
    2017: "000001123703", 2018: "000001133404", 2019: "000001144167",
    2020: "000001165066", 2021: "000001169606", 2022: "000001209840",
    2023: "000001222980", 2024: "000001232426",
}
DB_CANDIDATES = {2021: ["0004019963"], 2023: ["0004029012"],
                 2024: ["0004045391","0004045392","0004045393"]}
REQUIRED_REGIONAL = ("在院患者延数", "新入院患者数", "退院患者数", "外来患者延数")


def now():
    return datetime.now(JST).isoformat(timespec="seconds")


def tidy(node):
    return " ".join(node.text_content().split())


def write(name, records):
    with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream,list(records[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def acquire(identifier, url, path, expected):
    result=dict(id=identifier,url=url,download_url=url,jst=now(),http_status="",format=expected,bytes="",sha256="",
                saved_path=str(path),status="failed",error="")
    for _ in range(2):
        try:
            with urlopen(url,timeout=25) as response:
                content=response.read()
                result.update(http_status=response.status,download_url=response.geturl())
            if expected=="csv" and identifier.isdigit() and ("病院報告" not in content.decode("cp932")[:300]):
                raise ValueError("CSV header does not identify Hospital Report")
            if expected=="pdf" and not content.startswith(b"%PDF-"):
                raise ValueError("Unexpected PDF signature")
            if expected=="html" and b"<html" not in content.lower():
                raise ValueError("Unexpected HTML response")
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists() and path.read_bytes() != content and identifier.isdigit():
                raise ValueError("Publisher bytes changed; preserve the existing raw file and review the revision")
            if not path.exists() or path.read_bytes()!=content:
                path.write_bytes(content)
            result.update(status="downloaded",bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),error="")
            break
        except (OSError,ValueError) as exc:
            result["error"]=str(exc)
            if hasattr(exc,"code"):
                result["http_status"]=exc.code
    if path.is_relative_to(ROOT):
        result["saved_path"]=str(path.relative_to(ROOT))
    return result


def doc(spec, work):
    identity,url,kind=spec
    return acquire(identity,url,work/f"{identity}.{kind}",kind)


def catalog_urls(index):
    for year,group in YEARS.items():
        found={}
        for node in index.xpath(f'//a[contains(@href,"tclass1={group}")]'):
            ancestor=node.getparent().getparent().getparent()
            label=tidy(ancestor)
            for key, fragment in (("national","月別推移"),("regional","都道府県・指定都市・特別区・中核市"),("correction","訂正情報")):
                if (label.startswith(fragment+" ") or tidy(node).startswith(fragment+" [")) and key not in found:
                    found[key]=urljoin(ESTAT,node.get("href"))
        for key,url in found.items():
            yield year,key,url


def table_specs(catalog,year,group):
    used=set()
    for node in catalog.xpath('//a[@data-key="uid" and contains(@href,"stat_infid=")]'):
        title=tidy(node)
        if group=="regional":
            kind=next((key for key in REQUIRED_REGIONAL if title.startswith(key+"，")),None)
            if not kind:
                kind = next((label for label in ("病床利用率", "病床数", "平均在院日数")
                             if title.startswith(label+"，病院－病床の種類")), None)
            if not kind or kind in used:
                continue
            used.add(kind)
        container=node.getparent().getparent()
        link=container.xpath('.//a[contains(@href,"file-download")]')
        if not link:
            continue
        identifier=node.get("data-value")
        pub=re.search(r"公開（更新）日\s*(\d{4}-\d\d-\d\d)",tidy(container))
        yield year,group,identifier,title,urljoin(ESTAT,node.get("href")),urljoin(ESTAT,link[0].get("href")),pub[1] if pub else ""


def details(page):
    fields = {}
    for row in page.xpath('//tr'):
        cells = row.xpath('./th|./td')
        if len(cells) > 1 and tidy(cells[1]):
            fields[tidy(cells[0])] = tidy(cells[1])
    return fields


def fetch_table(spec,work,prior):
    year,group,identity,title,_,download,published=spec
    url=ESTAT+f"/stat-search/files?layout=dataset&stat_infid={identity}"
    metadata=doc((f"meta_{identity}",url,"html"),work)
    fields = {}
    checked = "not_verified"
    if metadata["status"] == "downloaded":
        fields = details(html.parse(metadata["saved_path"]))
        expected_grain = ("全国編", "上巻（全国）") if group == "national" else ("都道府県編", "下巻（都道府県）")
        if (fields.get("統計表名") == title and fields.get("提供分類2") in expected_grain
                and fields.get("調査年月") == str(year)+"年" and fields.get("政府統計コード") == "00450023"
                and fields.get("提供周期") == "年次"):
            checked = "verified"
    path = RAW/f"{year}_{group}_{identity}.csv"
    previous = prior.get(identity)
    if (previous and previous["status"] == "downloaded" and previous["publication_or_update"] == published
            and previous["download_url"] == download and path.exists()
            and hashlib.sha256(path.read_bytes()).hexdigest() == previous["sha256"]):
        result = {key: previous[key] for key in (
            "id", "url", "download_url", "jst", "http_status", "format", "bytes", "sha256", "saved_path", "status", "error")}
    else:
        result=acquire(identity,download,path,"csv")
    return dict(**{**result,"url":url},publisher="厚生労働省",stat_code="00450023",statistics="病院報告",
        year=year,period_start=f"{year}-01",period_end=f"{year}-12",grain=group,table_number=fields.get("表番号", ""),title=title,
        publication_or_update=published,official_release_time=fields.get("公開年月日時分", ""),
        revision_date="不明（取得対象表固有の改訂日は未確認）",edition="annual_release",official_metadata=checked,
        redistribution=TERMS),metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work",type=Path,required=True)
    args=parser.parse_args()
    work=args.work.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    work.mkdir(parents=True,exist_ok=True)
    configured=doc(("estat_index",INDEX,"html"),work)
    if configured["status"]!="downloaded":
        raise SystemExit(configured["error"])
    definitions=list(catalog_urls(html.parse(configured["saved_path"])))
    jobs=[(f"catalog_{y}_{kind}",url,"html") for y,kind,url in definitions]
    jobs.extend([
        ("estat_terms",TERMS,"html"),
        ("mhlw_method",MHLW+"/toukei/list/80-1b.html","html"),
        ("monthly_provisional_index",INDEX+"&cycle=1&month=24101212&tclass1=000001218480&year=20240&layout=datalist","html"),
        ("provisional_2024_04",MHLW+"/toukei/saikin/hw/byouin/m24/dl/2404kekka.pdf","pdf"),
        ("provisional_2024_12",MHLW+"/toukei/saikin/hw/byouin/m24/dl/2412kekka.pdf","pdf"),
    ])
    jobs.append(("provisional_db_catalog", ESTAT+"/stat-search/database?cycle=1&layout=datalist&toukei=00450023&tstat=000001030749&tclass1=000001218480", "html"))
    jobs.extend((f"provisional_view_{sid}", ESTAT+f"/dbview?sid={sid}", "html")
                for sid in ("0004024120", "0004024140", "0004024141"))
    for year,candidates in DB_CANDIDATES.items():
        jobs.extend((f"db_{year}_{identity}",ESTAT+f"/stat-search/database?layout=dataset&statdisp_id={identity}","html") for identity in candidates)
    jobs.extend((f"mhlw_annual_{year}",MHLW+f"/toukei/saikin/hw/iryosd/{str(year)[-2:]}/index.html","html") for year in YEARS)
    prior = {}
    if (OUT / "source_manifest.csv").exists():
        with (OUT / "source_manifest.csv").open(encoding="utf-8", newline="") as file:
            prior = {row["id"]: row for row in csv.DictReader(file)}
    with ThreadPoolExecutor(max_workers=12) as pool:
        docs=list(pool.map(lambda item:doc(item,work),jobs))
        indexed={row["id"]:row for row in docs}
        tables=[]
        for y,group,_ in definitions:
            if group=="correction":
                continue
            page=indexed[f"catalog_{y}_{group}"]
            if page["status"]=="downloaded":
                tables.extend(table_specs(html.parse(page["saved_path"]),y,group))
        pairs=list(pool.map(lambda item:fetch_table(item,work,prior),tables))
        refs=[]
        for item in docs:
            tag=item["id"]
            if item["status"]!="downloaded" or not (tag.startswith("mhlw_annual_") or tag.endswith("_correction")):
                continue
            p=html.parse(item["saved_path"])
            for idx,a in enumerate(p.xpath('//a[@href]')):
                href=a.get("href")
                label=tidy(a)
                if tag.endswith("_correction"):
                    if "file-download" not in href:
                        continue
                    extension="pdf"  # The correction notices are PDFs even for e-Stat fileKind=2.
                elif href.endswith(".pdf") and ("調査の概要" in label or label=="病院報告" or "訂正" in label):
                    extension="pdf"
                else:
                    continue
                refs.append((f"{tag}_{idx}",urljoin(item["url"],href),extension))
        refs=list(pool.map(lambda item:doc(item,work),refs))
    candidates = []
    for item in docs:
        if item["id"].startswith("db_") and item["status"] == "downloaded":
            fields = details(html.parse(item["saved_path"]))
            candidates.append(dict(id=item["id"].split("_")[-1], url=item["url"],
                                   stat_code=fields.get("政府統計コード"), period=fields.get("調査年月"),
                                   table=fields.get("表番号"), title=fields.get("表題"),
                                   released=fields.get("公開年月日時分"), variant="e-Stat database"))
    if candidates:
        write("candidate_database_tables.csv", candidates)
    write("source_manifest.csv",[item for item,_ in pairs])
    write("reference_manifest.csv",[configured]+docs+refs+[item for _,item in pairs])
    print(f"Tables {len(pairs)}; obtained {sum(row['status']=='downloaded' for row,_ in pairs)}")


if __name__=="__main__":
    main()

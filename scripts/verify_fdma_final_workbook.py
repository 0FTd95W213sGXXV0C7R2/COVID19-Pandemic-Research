#!/usr/bin/env python3
"""Independently reconstruct cell identities and compare the FDMA workbook with its CSV."""
import csv
import hashlib
import json
import posixpath
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/"data/raw/fdma/emergency_transport/coronavirus_data.xlsx"
OLD = ROOT/"data/audits/fdma/emergency_transport"
OUT = OLD/"final_20261126"
SOURCE = ROOT/"data/processed/fdma/emergency_transport/weekly_long.csv"
JST = ZoneInfo("Asia/Tokyo")
GATE = "2024-04-08"
MONDAY = timedelta(days=7)
WEEK = re.compile(r"(\d+)/\s*(\d+)\s*\(?(.)\)\s*[~〜]\s*(\d+)/\s*(\d+)\s*\((.)\)")
INCOMPLETE_WEEK = "2022-03-07"
SHEET_ROLE = {
    "搬送困難事案（今回）": ("current_overall", "transport_difficulty_overall_current"),
    "搬送困難事案（前年同期）": ("previous_year_comparator", "transport_difficulty_overall_previous_year"),
    "うちコロナ疑い事案（今回）": ("current_subgroup", "transport_difficulty_covid_suspected_current"),
    "うち非コロナ疑い事案（今回）": ("current_subgroup", "transport_difficulty_non_covid_suspected_current"),
}


def now():
    return datetime.now(JST).isoformat(timespec="seconds")


def rows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def write(name, data, fields=None):
    with (OUT/name).open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fields or list(data[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)


def normalize(value):
    return unicodedata.normalize("NFKC",value)


def raw_sheets():
    with ZipFile(RAW) as package:
        booklet=ET.fromstring(package.read("xl/workbook.xml"))
        relationships=ET.fromstring(package.read("xl/_rels/workbook.xml.rels"))
        locations={node.get("Id"):node.get("Target") for node in relationships}
        strings=[]
        if "xl/sharedStrings.xml" in package.namelist():
            strings=["".join(t.text or "" for t in (si.findall("{*}t")+si.findall("{*}r/{*}t"))) for si in
                     ET.fromstring(package.read("xl/sharedStrings.xml"))]
        for sheet in booklet.findall("{*}sheets/{*}sheet"):
            rel=next(a for k,a in sheet.attrib.items() if k.endswith("}id"))
            target=locations[rel]
            member=target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl",target))
            document=ET.fromstring(package.read(member))
            values={}
            shared={}
            for c in document.findall("{*}sheetData/{*}row/{*}c"):
                kind=c.get("t","n")
                data=c.findtext("{*}v") or ""
                if kind=="s":
                    data=strings[int(data)]
                if kind=="inlineStr":
                    data="".join(t.text or "" for t in c.findall("{*}is//{*}t"))
                formula=c.find("{*}f")
                equation = ""
                if formula is not None:
                    equation = formula.text or ""
                    if formula.get("t")=="shared":
                        reference=formula.get("si")
                        if equation:
                            shared[reference]=(c.get("r"),equation)
                        else:
                            origin,expression=shared[reference]
                            before=re.fullmatch(r"([A-Z]+)(\d+)",origin)
                            after=re.fullmatch(r"([A-Z]+)(\d+)",c.get("r"))
                            if before[2]!=after[2] or not re.fullmatch(rf"SUM\({before[1]}6:{before[1]}57\)",expression):
                                raise ValueError(f"Unexpected shared formula: {origin}")
                            equation=f"SUM({after[1]}6:{after[1]}57)"
                    equation="="+equation
                values[c.get("r")]=(data,kind,equation)
            yield sheet.get("name"),values,[m.get("ref") for m in document.findall("{*}mergeCells/{*}mergeCell")]


def metadata(values, merges):
    areas={}
    for name in merges:
        if match:=re.fullmatch(r"B(\d+):B(\d+)",name):
            first,last=map(int,match.groups())
            for row in range(first+1,last+1):
                areas[row]=(values[f"B{first}"][0],f"merged_range:{name}")
    for number in range(6,58):
        if values.get(f"B{number}",("",))[0]:
            areas[number]=(values[f"B{number}"][0],"explicit_cell")
    return areas


def periods(values):
    year=2018+int(re.search(r"R\s*(\d+)",values["D3"][0])[1])
    last_month=0
    for location,(text,_,_) in values.items():
        anchor=re.fullmatch(r"([A-Z]+)4",location)
        if not anchor or not (match:=WEEK.search(normalize(text))):
            continue
        sm,sd,sw,em,ed,ew=match.groups()
        start_month,end_month=int(sm),int(em)
        if last_month>start_month:
            year+=1
        last_month=start_month
        start=date(year,start_month,int(sd))
        printed=date(year+(end_month<start_month),end_month,int(ed))
        expected=start+timedelta(days=6)
        yield anchor[1],start,printed,expected,sw,ew,text


def workbook_checks():
    digest=hashlib.sha256(RAW.read_bytes()).hexdigest()
    old=rows(SOURCE)
    index={(row["source_sheet"],row["source_cell"]):row for row in old}
    found=set()
    differences=[]
    totals=[]
    flags=[]
    validated=[]
    identities={}
    periods_by_sheet={}
    for sheet,values,merges in raw_sheets():
        areas=metadata(values,merges)
        identities[sheet]=[(areas[i][0],values[f"C{i}"][0]) for i in range(6,58)]
        weeks=list(periods(values))
        periods_by_sheet[sheet]=[entry[1] for entry in weeks]
        for week_idx,(col,start,printed,expected,sw,ew,heading) in enumerate(weeks,1):
            official_week=start.isoformat()
            details=[]
            for num in [*range(6,58),58]:
                address=f"{col}{num}"
                key=sheet,address
                actual,kind,formula=values.get(address,("","n",""))
                published=index.get(key)
                found.add(key)
                category="blank" if not actual else "number" if kind=="n" else "non_numeric"
                number=Decimal(actual) if category=="number" else None
                prefecture,area_source=areas[num] if num!=58 else (published["prefecture"],published["prefecture_value_source"])
                if num!=58:
                    details.append(number)
                value_matches=published["value"]==actual if number is None else bool(published["value"]) and Decimal(published["value"])==number
                record=dict(period_start_date=official_week,period_end_date_expected=expected.isoformat(),
                    period_end_date_printed=printed.isoformat(),source_sheet=sheet,source_cell=address,
                    prefecture=prefecture,fire_department=values[f"C{num}"][0],raw_value=actual)
                expected_status=("cached_excel_total_formula" if formula else "source_total_value") if num==58 else (
                    "blank_in_source" if category=="blank" else "reported_zero" if number==0 else "reported_numeric_value")
                if not value_matches or any([
                    published["period_start_date"]!=official_week,
                    published["period_end_date_expected"]!=expected.isoformat(),
                    published["period_end_date"]!=(expected.isoformat() if expected==printed else ""),
                    published["date_header_status"]!=("matched" if expected==printed else "printed_end_date_or_weekday_mismatch"),
                    (published["series_role"],published["metric_code"])!=SHEET_ROLE[sheet],
                    published["aggregation_level"]!=("52_fire_department_total" if num==58 else "fire_department"),
                    published["paired_current_week_start_date"]!=(
                        (start+timedelta(days=364)).isoformat() if SHEET_ROLE[sheet][0]=="previous_year_comparator" else ""
                    ),
                    published["period_end_date_printed"]!=printed.isoformat(),
                    published["raw_week_header"]!=heading,
                    published["week_index"]!=str(week_idx),
                    published["source_formula"]!=formula,
                    published["source_file_sha256"]!=digest,
                    published["fire_department"]!=record["fire_department"],
                    published["prefecture"]!=prefecture,
                    published["prefecture_value_source"]!=area_source,
                    published["observation_status"]!=expected_status,
                    sw!="月" or ew!="日" or start.weekday()!=0,
                ]):
                    differences.append(record)
                if category!="number" or number==0:
                    flags.append(dict(**record,flag=category if category!="number" else "reported_zero",evidence="official_workbook"))
                if num==58 and re.search(r"/\d+\s*月\)",normalize(heading)):
                    flags.append(dict(**record,flag="weekday_left_parenthesis_missing",evidence="workbook printed header"))
                if printed!=expected:
                    flags.append(dict(**record,flag="printed_end_date_mismatch",evidence="boundary PDF R6.4/1–4/7"))
                validated.append((published,record,number))
            known=[v for v in details if v is not None]
            total=sum(known)
            result=("incomplete_known_sum_matches" if len(known)!=52 and total==number else "incomplete" if len(known)!=52
                    else "match" if total==number else "mismatch")
            totals.append(dict(source_sheet=sheet,week_start=official_week,cached_total=str(number),numeric_departments=len(known),
                               known_sum=str(total),result=result))
    reference=next(iter(identities.values()))
    test=dict(raw_matches_archived_manifest=digest==json.loads((OLD/"source_manifest.json").read_text())["sha256"],
        independent_cells_44308=len(found)==len(index)==len(old)==44308 and found==index.keys() and not differences,
        continuous_monday_weeks=all(all(b-a==MONDAY for a,b in zip(weeks,weeks[1:])) for weeks in periods_by_sheet.values()),
        identical_52_departments_in_workbook=all(v==reference for v in identities.values()) and len(set(reference))==52,
        one_incomplete_national_reconciliation=Counter(r["result"] for r in totals)=={"match":835,"incomplete_known_sum_matches":1})
    return validated,totals,flags,differences,test,periods_by_sheet,digest


def build(validated, official_date_confirmed):
    analysis=[]
    partition=defaultdict(dict)
    for row,source,value in validated:
        if row["series_role"]=="previous_year_comparator":
            continue
        day=row["period_start_date"]
        area=row["fire_department"]
        partition[day,area][row["source_sheet"]]=value
        if day<"2020-04-27" or value is None or (day=="2024-04-01" and not official_date_confirmed):
            continue
        if day==INCOMPLETE_WEEK and area in {"秋田市消防本部","52本部合計"}:
            continue
        scope = ("covid_legacy_before_class5" if day<"2023-05-08" else "covid_legacy_class5"
                 ) if row["series_role"]=="current_subgroup" else (
                     "overall_old_form" if day<GATE else "overall_new_form")
        analysis.append(dict(week_start=day,week_end=source["period_end_date_expected"],
            week_end_printed=source["period_end_date_printed"],series_definition_id=scope+"|"+row["metric_code"],
            metric=row["metric_code"],prefecture=row["prefecture"],fire_department=area,geography=row["aggregation_level"],
            value=str(value),unit="件",observation_status=row["observation_status"],source_sheet=row["source_sheet"],
            source_cell=row["source_cell"],sha256=row["source_file_sha256"],
            date_evidence="FDMA_weekly_PDF_confirmed" if day=="2024-04-01" else "workbook",denominator_in_workbook=""))
    columns=("搬送困難事案（今回）","うちコロナ疑い事案（今回）","うち非コロナ疑い事案（今回）")
    overlaps=[tuple(values[key] for key in columns) for values in partition.values() if set(values)==set(columns)]
    return analysis, overlaps

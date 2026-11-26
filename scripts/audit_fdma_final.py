#!/usr/bin/env python3
"""Final FDMA analysis gate, archival acquisition, and matched dispatch denominators."""
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import urlopen

import fitz

from verify_fdma_final_workbook import (
    INCOMPLETE_WEEK, GATE, OUT, RAW, ROOT, build, normalize, now, workbook_checks, write,
)

DOMAIN="https://www.fdma.go.jp"
OLD_PAGE=DOMAIN+"/disaster/coronavirus/post-1.html"
NEW_PAGE=DOMAIN+"/disaster/coronavirus-situ/post-1.html"
SOURCES={
    "workbook":"/disaster/coronavirus/items/coronavirus_data.xlsx",
    "notice_103":"/disaster/coronavirus/items/200423_kyuuki_103.pdf",
    "notice_105":"/disaster/coronavirus-situ/items/240408_kyuuki_01.pdf",
    "legacy_scope":"/singi_kento/kento/items/r5-1/01/shiryou2-2.pdf",
    "legacy_end_week":"/disaster/coronavirus-situ/items/coronavirus_kekka.pdf",
    "workbook_end_week":"/disaster/coronavirus/items/coronavirus_kekka.pdf",
    "annual_dispatch":"/publication/rescue/items/kkkg_r07_01_kyukyu.pdf",
    "annual_index":"/publication/rescue/post-7.html",
}
HEADER=re.compile(r"R\s*(\d+)\.\s*(\d+)/(\d+)\s*\(月\)\s*[~〜]\s*R\s*(\d+)\.\s*(\d+)/(\d+)\s*\(日\)")
COUNT=r"([0-9][0-9,]*)"
CHANGE=r"(?:[+\-−]?[0-9][0-9,.]*%|皆[増減]|[ー—―−-])"
COLUMNS=re.compile(r"^\s*"+r"\s+".join([COUNT]*3+[CHANGE]*2+[COUNT]*3)+r"(?=\s|$)")


class Reports(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]

    def handle_starttag(self,tag,attrs):
        link=dict(attrs).get("href","")
        if tag=="a" and re.fullmatch(r"/disaster/coronavirus-situ/items/(?:r\d+/)?coronavirus_kekka_r\d+\.pdf",link):
            self.links.append(link)


def get(spec, directory):
    key,url,extension=spec
    row=dict(id=key,url=url,format=extension,local_filename=f"{key}.{extension}",checked_jst=now(),
             http_status="",content_type="",bytes="",sha256="",status="failed",error="")
    for attempt in range(2):
        try:
            with urlopen(url,timeout=20) as response:
                data=response.read()
                row.update(http_status=response.status,content_type=response.headers.get("Content-Type",""))
            signature={"pdf":b"%PDF-","xlsx":b"PK"}
            if extension in signature and not data.startswith(signature[extension]):
                raise ValueError("Unexpected file signature")
            if extension=="html" and b"<html" not in data.lower():
                raise ValueError("Unexpected HTML response")
            (directory/row["local_filename"]).write_bytes(data)
            row.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),status="downloaded",error="")
            break
        except (OSError,ValueError) as exc:
            if isinstance(exc,HTTPError):
                row["http_status"]=exc.code
            row["error"]=str(exc)
    return row


def pdf_text(directory, source, first_page=False):
    command=["pdftotext","-layout"]
    if first_page:
        command+=["-f","1","-l","1"]
    return normalize(subprocess.run(command+[str(directory/source["local_filename"]),"-"],capture_output=True,check=True).stdout.decode())


def weekly_pdf(source, directory, roster, text=None):
    if text is None:
        text=pdf_text(directory,source,first_page=True)
    title=HEADER.search(" ".join(text.splitlines()[:5]))
    data={}
    notes=[" ".join(line.split()) for line in text.splitlines()
           if re.search(r"システム|集計対象外|データ.*反映|訂正|修正",line)]
    aliases={**{name: name for name in roster},"合計":"52本部合計"}
    scanner=re.compile("|".join(re.escape(name) for name in sorted(roster,key=len,reverse=True))+r"|(?<!前回)合\s*計")
    for line in text.splitlines():
        # A line may contain a left and right panel. '前回 合計' is a separate comparator.
        line=re.sub(r"前\s*回\s*合\s*計.*$","",line)
        for match in scanner.finditer(line):
            name=aliases.get(re.sub(r"\s+","",match[0]),match[0])
            segment=line[match.end():]
            if name=="52本部合計":
                segment=re.sub(r"^\s*"+CHANGE+r"\s+"," ",segment,count=1)
            fields=COLUMNS.match(segment)
            if fields:
                data.setdefault(name,[]).append([int(token.replace(",","")) for token in fields.groups()])
    clean={key:items[0] for key,items in data.items() if len(items)==1}
    full=set(roster)|{"52本部合計"}
    header_ok="搬送困難事案件数" in re.sub(r"\s+","",text) and "救急出動件数" in text and "計52本部" in re.sub(r"\s+","",text)
    totals_match=full==clean.keys() and all(sum(clean[name][i] for name in roster)==clean["52本部合計"][i] for i in (0,3))
    coverage=dict(id=source["id"],url=source["url"],week_start="",week_end="",observed_departments=len(set(roster)&clean.keys()),
                missing_departments="|".join(sorted(set(roster)-clean.keys())),total_reconciled=totals_match,
                difficulty_total=clean["52本部合計"][0] if "52本部合計" in clean else "",
                dispatch_total=clean["52本部合計"][3] if "52本部合計" in clean else "",
                difficulty_known_sum=sum(values[0] for name,values in clean.items() if name in roster),
                dispatch_known_sum=sum(values[3] for name,values in clean.items() if name in roster),
                scope_or_revision_notes=" | ".join(notes),
                status="accepted" if title and header_ok and totals_match else "hold")
    if not title:
        return coverage,{}
    y,sm,sd,ey,em,ed=map(int,title.groups())
    day=date(2018+y,sm,sd)
    end=date(2018+ey,em,ed)
    if day.weekday()!=0 or (end-day).days!=6:
        coverage["status"]="hold_invalid_week"
        return coverage,{}
    coverage.update(week_start=day.isoformat(),week_end=end.isoformat())
    return coverage,clean


def ratios(accepted,roster, workbook):
    result=[]
    revisions=[]
    pdf_by_date={}
    workbook_matches=[]
    for source,cov,table in accepted:
        day=cov["week_start"]
        if day in pdf_by_date:
            raise ValueError(f"Multiple current-week PDFs for {day}")
        pdf_by_date[day]=(source,table)
        for area,values in table.items():
            current,_,_, dispatch,_,_ = values
            if not 0<=current<=dispatch or dispatch<=0:
                continue
            compiled=workbook.get((day,area))
            if compiled is not None:
                workbook_matches.append(dict(week_start=day,fire_department=area,workbook_value=compiled,
                    official_pdf_value=current,result="match" if compiled==current else "different",
                    url=source["url"]))
                if compiled!=current:
                    revisions.append(dict(week_start=day,fire_department=area,metric="difficulty_cases",earlier=compiled,
                        later=current,earlier_url=DOMAIN+SOURCES["workbook"],later_url=source["url"],kind="workbook_pdf_difference"))
            result.append(dict(week_start=day,week_end=cov["week_end"],prefecture=roster.get(area,""),fire_department=area,
                geography="52_fire_department_total" if area=="52本部合計" else "fire_department",
                namespace="boundary_pdf_legacy" if day<GATE else "dispatch_matched_reporting_pdf_new_form",
                difficult_cases=current,emergency_dispatches=dispatch,
                cases_per_100_dispatches=f"{100*current/dispatch:.6f}",period_match="same_printed_week",
                population_match="same_fire_department_and_report",source_url=source["url"],
                source_sha256=source["sha256"],page=1,release_status="preliminary"))
    for day,(source,table) in sorted(pdf_by_date.items()):
        previous=(date.fromisoformat(day)-timedelta(days=7)).isoformat()
        if previous not in pdf_by_date:
            continue
        old,old_table=pdf_by_date[previous]
        for area,current in table.items():
            for name,before,new in (("difficulty_cases",old_table[area][0],current[1]),
                                    ("dispatches",old_table[area][3],current[4])):
                if before!=new:
                    revisions.append(dict(week_start=previous,fire_department=area,metric=name,earlier=before,later=new,
                        earlier_url=old["url"],later_url=source["url"],kind="same_week_later_vintage"))
    return result,revisions,workbook_matches


def eligible_periods(analysis, rates):
    groups=defaultdict(set)
    for item in analysis:
        key=item["series_definition_id"],item["prefecture"],item["fire_department"],item["geography"]
        groups[key].add(item["week_start"])
    for item in rates:
        key=item["namespace"]+"|difficulty_cases_per_100_dispatches",item["prefecture"],item["fire_department"],item["geography"]
        groups[key].add(item["week_start"])
    output=[]
    for (definition,prefecture,area,level),available in sorted(groups.items()):
        previous=None
        windows=[]
        for day in sorted(map(date.fromisoformat,available)):
            if previous is None or day-previous!=timedelta(days=7):
                windows.append([day,day,1])
            else:
                windows[-1][1]=day
                windows[-1][2]+=1
            previous=day
        for first,last,weeks in windows:
            output.append(dict(series_definition_id=definition,prefecture=prefecture,fire_department=area,geography=level,
                first=first,last=last+timedelta(days=6),weeks=weeks))
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir",type=Path,required=True)
    parser.add_argument("--reuse-downloads",action="store_true",help="Reuse and rehash the recorded working copies")
    args=parser.parse_args()
    directory=args.private_dir.resolve()
    if directory.is_relative_to(ROOT):
        parser.error("Outside-repository source directory required")
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    OUT.mkdir(exist_ok=True)
    started=now()
    validated,national,flags,diff,tests,sheet_dates,digest=workbook_checks()
    roster={r["fire_department"]:r["prefecture"] for r,_,_ in validated if r["aggregation_level"]=="fire_department"}
    frozen={(r["period_start_date"],r["fire_department"]):int(v) for r,_,v in validated
            if r["series_role"]=="current_overall" and v is not None}
    if args.reuse_downloads:
        from verify_fdma_final_workbook import rows
        recorded=rows(OUT/"source_manifest.csv")
        for recorded_source in recorded:
            if recorded_source["status"]=="downloaded":
                path=directory/recorded_source["local_filename"]
                if hashlib.sha256(path.read_bytes()).hexdigest()!=recorded_source["sha256"]:
                    raise ValueError(f"Wrong source version: {path}")
        base,fetched=recorded[:2],recorded[2:]
    else:
        base=[get((key,url,"html"),directory) for key,url in (("old_index",OLD_PAGE),("new_index",NEW_PAGE))]
        link_parser=Reports()
        if base[-1]["status"]=="downloaded":
            link_parser.feed((directory/base[-1]["local_filename"]).read_text())
        targets=[(key,DOMAIN+path,path.rsplit(".",1)[-1]) for key,path in SOURCES.items()]
        links=sorted(set(link_parser.links))
        targets.extend((Path(link).stem, urljoin(NEW_PAGE,link),"pdf") for link in links)
        with ThreadPoolExecutor(max_workers=8) as workers:
            fetched=list(workers.map(lambda spec:get(spec,directory),targets))
    source_index={r["id"]:r for r in fetched}
    tests["fresh_official_workbook_matches_saved_bytes"]=(source_index["workbook"]["sha256"]==digest)
    coverage=[]
    accepted=[]
    for source in fetched:
        if source["id"] not in {"legacy_end_week","workbook_end_week"} and not source["id"].startswith("coronavirus_kekka_r"):
            continue
        if source["status"]!="downloaded":
            continue
        status,table=weekly_pdf(source,directory,roster)
        method="poppler"
        secondary_evidence=""
        if status["status"]!="accepted":
            with fitz.open(directory/source["local_filename"]) as document:
                extra=normalize(document[0].get_text(sort=True))
            alternative,alternate_table=weekly_pdf(source,directory,roster,text=extra)
            common=table.keys() & alternate_table.keys()
            agreement=bool(common) and all(table[key]==alternate_table[key] for key in common)
            if alternative["status"]=="accepted" and agreement and len(common)>=51:
                status,table=alternative,alternate_table
                method="pymupdf_with_poppler_overlap"
                secondary_evidence=f"common_exact_rows:{len(common)}"
            elif len(common)==53 and agreement:
                secondary_evidence="both_readers_confirm_same_printed_rows"
        status.update(table_reader=method,secondary_evidence=secondary_evidence)
        coverage.append(status)
        if status["status"]=="accepted":
            accepted.append((source,status,table))
    rates,revisions,match=ratios(accepted,roster,frozen)
    boundary=any(r["week_start"]=="2024-04-01" and r["geography"]=="52_fire_department_total" for r in rates)
    boundary_matches=[r for r in match if r["week_start"]=="2024-04-01"]
    analysis,triplets=build(validated,boundary and len(boundary_matches)==53 and all(r["result"]=="match" for r in boundary_matches))
    for row,loc,_ in validated:
        day=row["period_start_date"]
        if day==INCOMPLETE_WEEK and row["fire_department"] in {"秋田市消防本部","52本部合計"} and row["series_role"]!="previous_year_comparator":
            flags.append(dict(**loc,flag="incomplete_cross_partition",evidence="overall Akita blank, both subgroups report zero"))
        if day in {"2023-05-08",GATE} and row["series_role"]!="previous_year_comparator" and row["aggregation_level"]=="52_fire_department_total":
            flags.append(dict(**loc,flag="definition_or_reporting_boundary",evidence="5-classification or notice 105"))
    tests.update(classification_partition_total_and_facility=Counter("incomplete" if None in v else "match" if v[0]==v[1]+v[2] else "mismatch"
            for v in triplets)=={"match":8320,"incomplete":1},
        boundary_20240401_verified_53_pdf_cells=boundary and len(boundary_matches)==53 and all(r["result"]=="match" for r in boundary_matches),
        weekly_dispatch_rate_has_matching_period_scope=bool(rates) and all(r["emergency_dispatches"]>0 and r["namespace"] for r in rates),
        no_cross_form_ids_or_missing_values=all(r["value"]!="" and r["denominator_in_workbook"]=="" for r in analysis)
            and len({(r["source_sheet"],r["source_cell"]) for r in analysis})==len(analysis),
        paired_comparator_not_double_counted=all("previous_year" not in r["metric"] for r in analysis))
    note=source_index["notice_105"]
    simple=re.sub(r"\s+","",pdf_text(directory,note)) if note["status"]=="downloaded" else ""
    tests["notice_105_verifies_reporting_changes"]=all(token in simple for token in ("4月8日","救急出動件数","月報告は終了","(内数)の調査"))
    # Count the exact partition outcomes alongside the validation assertion.
    outcomes=Counter("incomplete" if None in v else "match" if v[0]==v[1]+v[2] else "mismatch" for v in triplets)
    tests["rate_observation_keys_unique_and_same_53_records"]=(
        len({(row["week_start"],row["fire_department"]) for row in rates})==len(rates)
        and all(n==53 for n in Counter(row["week_start"] for row in rates).values()))
    assert not diff, "Workbook reconciliation failed; accepted analysis counts were not regenerated"
    for name,dataset in [("eligible_periods_by_area.csv",eligible_periods(analysis,rates)),("source_manifest.csv",base+fetched),("national_reconciliation.csv",national),
        ("quality_flags.csv",flags),("analysis_weekly_counts.csv",analysis),("weekly_publication_coverage.csv",coverage),
        ("analysis_matched_dispatch_rates.csv",rates),("revision_evidence.csv",revisions),("pdf_workbook_reconciliation.csv",match)]:
        if dataset:
            write(name,dataset)
    write("independent_differences.csv",diff,list(flags[0])[:-2])
    report=dict(start_jst=started,end_jst=now(),compared_rows=len(validated),mismatches=len(diff),
        workbook_periods={k:[min(v).isoformat(),(max(v)+timedelta(days=6)).isoformat(),len(v)] for k,v in sheet_dates.items()},
        national_outcomes=dict(Counter(r["result"] for r in national)),partitions=dict(outcomes),
        acquisition=dict(Counter(r["status"] for r in base+fetched)),
        pdf_weeks_accepted=len(accepted),pdf_weeks_held=len(coverage)-len(accepted),count_rows=len(analysis),
        rate_rows=len(rates),revision_rows=len(revisions),pdf_workbook_differences=sum(r["result"]!="match" for r in match),tests=tests)
    (OUT/"validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return all(tests.values())


if __name__=="__main__":
    raise SystemExit(0 if main() else 1)

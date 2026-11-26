#!/usr/bin/env python3
"""Acquire supplemental sources, verify originals, and install scoped survey definitions."""
import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import fitz

from audit_mhlw_early_pdfs import compact, csv_rows, now
from build_mhlw_current_metadata import ACTIVE, AUDIT, META, ROOT, load_active_crosswalk, sha, write_csv
from finalize_mhlw_early_series import OUT

PREVIOUS = AUDIT / "early_pdf_audit"
V2 = META / "variable_crosswalk_candidate_v2.csv"
PDL = "https://www.mhlw.go.jp/chosakuken/"
NOTICE = {
    "sep": ("survey_2022", "2022-09-28", "2023-05-03"),
    "may": ("survey_may", "2023-05-10", "2023-09-27"),
    "oct": ("survey_oct", "2023-10-04", "2024-03-27"),
}
DEFINITIONS = {
    "total_inpatients": ("調査時点で病院又は診療所に入院しているCOVID-19患者。確保病床外を含む。", "病院又は診療所に入院している者", "記述分析"),
    "total_severe_patients": ("在院者のうち国の報告基準でICU入室又は人工呼吸器が必要。対象は通知に列挙された診療報酬上の病床を含む。", "は人工呼吸器が必要", "地域の運用基準確認まで分析保留"),
    "total_moderate_II_patients": ("在院者のうち診療の手引きの中等症Ⅱに該当し酸素投与が必要。", "酸素投与が必要", "記述分析"),
    "hotel_accommodation_patients": ("調査時点に宿泊療養施設で療養している患者。", "宿泊療養施設で", "記述分析"),
    "social_welfare_facility_patients": ("自宅療養者等の内数。社会福祉施設等の入所施設・居住系サービス等で安静・療養中の患者。", "居住系サービス", "記述分析"),
}


def request(url):
    with urlopen(url, timeout=25) as response:
        return response.read(), response.status, response.geturl(), response.headers.get("Content-Type", "")


def acquire(row, directory):
    record = dict(**row, acquired_at_jst=now(), http_status="", final_url="", mime="", bytes="", sha256="", status="failed", error="")
    try:
        payload, status, final, mime = request(row["url"])
        record.update(http_status=status, final_url=final, mime=mime)
        if row["format"]=="pdf" and not payload.startswith(b"%PDF-"):
            raise ValueError("Unexpected body format")
        if row["format"]=="html" and b"<html" not in payload.lower():
            raise ValueError("Unexpected body format")
        path = directory / (row["id"]+"."+row["format"])
        path.write_bytes(payload)
        record.update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), status="downloaded")
        return record, path
    except (OSError, ValueError) as exc:
        if isinstance(exc, HTTPError):
            record.update(http_status=exc.code, final_url=exc.geturl())
        record["error"] = str(exc)
        return record, None


def original_pdfs(early, later, restore, bundle, license_verified):
    rows = []
    for name, folder in (("early",early),("weekly",later)):
        filename = "acquisition_manifest.csv" if name=="early" else "definition_pdf_manifest.csv"
        for row in csv_rows(PREVIOUS / filename):
            ident = row["url"].rsplit("/",1)[-1]
            local = folder / ident
            status, error = "verified", ""
            if not local.exists() and restore:
                try:
                    payload, _, _, _ = request(row["url"])
                    if hashlib.sha256(payload).hexdigest()!=row["sha256"]:
                        raise ValueError("Official bytes differ from the recorded edition")
                    local.parent.mkdir(parents=True,exist_ok=True)
                    local.write_bytes(payload)
                except (OSError, ValueError) as exc:
                    error=str(exc)
            if not local.exists() or sha(local)!=row["sha256"]:
                status="missing_or_changed"
            signals, images, embedded = [], 0, 0
            if status=="verified":
                with fitz.open(local) as pdf:
                    for index, page in enumerate(pdf,1):
                        text=compact(page.get_text())
                        for match in re.finditer(r"著作権|転載禁止|無断転載|利用規約|AllRightsReserved|Copyright|©|提供[:：]|出典[:：]", text, re.I):
                            signals.append(f"{index}:{text[max(0,match.start()-7):match.end()+28]}")
                        images += len(page.get_image_info())
                    embedded=pdf.embfile_count()
                    if not pdf.metadata:
                        signals.append("metadata_unavailable")
                if bundle:
                    target=bundle/name/ident
                    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    if not target.exists():
                        shutil.copyfile(local,target)
                    if sha(target)!=row["sha256"]:
                        raise ValueError(f"Private copy differs: {target}")
            eligible = license_verified and status=="verified" and not (signals or images or embedded)
            rows.append(dict(series=name,url=row["url"],filename=ident,expected_bytes=row["bytes"],sha256=row["sha256"],
                integrity=status,checked_at_jst=now(),license_url=PDL,
                document_rights_signals=" | ".join(dict.fromkeys(signals)),raster_objects=images,embedded_files=embedded,
                decision="PDL1.0条件付き可・出典表示" if eligible else "公開保留・個別権利要確認",
                publication="本体未掲載",private_copy="hash_verified" if bundle and status=="verified" else "not_copied",error=error))
    return rows


def pdf_pages(path):
    with fitz.open(path) as doc:
        return [(i,compact(page.get_text(sort=True))) for i,page in enumerate(doc,1)]


def revise_crosswalk(sources):
    pages={key:pdf_pages(sources[key]) for key,_,_ in NOTICE.values() if sources.get(key)}
    if len(pages)!=len(NOTICE):
        raise ValueError("A reporting notice is unavailable. The active crosswalk was retained.")
    held={row["variable_id"]:row for row in csv_rows(PREVIOUS/"held_definition_followup.csv")}
    v2=csv_rows(V2)
    counts, reviews = [], []
    for row in v2:
        key=row["variable_id"]
        if key not in held:
            continue
        current=held[key]
        day=current["observation_date"]
        era="sep" if "2022-09-28"<=day<="2023-05-03" else current["era"]
        concept=row["concept"]
        spec=DEFINITIONS.get(concept)
        notice=NOTICE.get(era)
        page = ""
        source=""
        scope=""
        if spec and notice and concept in {
            "sep":{"total_inpatients","total_severe_patients","hotel_accommodation_patients","social_welfare_facility_patients"},
            "may":{"total_inpatients","total_severe_patients","hotel_accommodation_patients"},
            "oct":{"total_inpatients","total_severe_patients","total_moderate_II_patients"},
        }[era]:
            source,start,end=notice
            scope=f"{start}/{end}"
            page=next((i for i,text in pages.get(source,[]) if compact(spec[1]) in text),"")
        outcome="hold"
        if page:
            meaning, _, use=spec
            outcome="confirmed_reporting_rule"
            allowed=use=="記述分析"
            row.update(definition=meaning,definition_reason=f"{source} p.{page}。{use}",
                definition_status=outcome,status=outcome,
                adoption_status="期間内の原公表値のみ" if allowed else "地域基準確認まで保留",
                analysis_gate="available_prefectures" if allowed else "hold",
                definition_id=f"official_rule:{era}:{concept}",
                valid_from=start,valid_to=end)
            counts.append(concept)
        reviews.append(dict(variable_id=key,observation_date=day,concept=concept,prior_outcome="hold",
            outcome=outcome,reporting_notice=source,notice_page=page,period=scope,
            source_url=SOURCE_URLS.get(source,""),excel_url=current["excel_url"],sheet=current["sheet"],
            cells=current["header_cells"],followup=row["definition_reason"]))
    path = META/"variable_crosswalk_candidate_v3.csv"
    write_csv(path,v2)
    inputs=[path,V2,OUT/"source_catalog.tsv",OUT/"supplemental_source_manifest.csv",OUT/"definition_notice_review.csv"]
    write_csv(OUT/"definition_notice_review.csv",reviews)
    release=dict(release="weekly_candidate_v3",crosswalk=str(path.relative_to(ROOT)),
        status_precedence=["definition_notice_review","weekly_candidate_v2"],
        sha256={str(item.relative_to(ROOT)):sha(item) for item in inputs})
    ACTIVE.write_text(json.dumps(release,ensure_ascii=False,indent=2)+"\n")
    return reviews,counts


def validated_metrics(sources):
    # Values are anchored to published text/table, without combining source populations.
    rows = []
    values = [
        ("gmis_202308","icu_current_patients_7d_average","2023-07-17","2023-07-23",132,"人","7日間平均の在室患者数","入院中の患者数の7日間平均は132人"),
        ("gmis_202308","ecmo_or_ventilator_current_7d_average","2023-07-17","2023-07-23",70,"人","ECMO管理中とECMOなし人工呼吸器管理中の7日間平均","患者数の7日間平均は70人"),
        ("ecmo_cumulative","ecmo_cumulative_treated_patients","2020-02-09","2022-06-12",1287,"人","CRISISに登録された期間累積装着患者","総ECMO装着患者1287名"),
        ("mv_cumulative_2020","ventilator_without_ecmo_cumulative_patients","不明","2020-12-23",2030,"例","日本ECMOnet公表の人工呼吸治療累積、ECMO除外","成績累計は2,030例"),
        ("mv_cumulative_2020","ventilator_without_ecmo_current_patients","2020-12-23","2020-12-23",367,"例","同集計日に人工呼吸を実施中、ECMO除外","人工呼吸実施中367例"),
        ("mv_cumulative_2020","ecmo_current_patients","2020-12-23","2020-12-23",59,"例","同集計日にECMOを実施中","ECMO実施中59例"),
        ("icu_beds","icu_management_fee_1_registered_beds","不明","不明",1487,"床","特定集中治療室管理料1の届出。引用資料日2022-09-14","1,487床"),
    ]
    for key,metric,start,end,value,unit,definition,anchor in values:
        path=sources.get(key)
        if not path:
            continue
        text=subprocess.run(["pdftotext","-layout",str(path),"-"],check=True,capture_output=True).stdout.decode()
        page=next((i for i,line in enumerate(text.split("\f"),1) if compact(anchor) in compact(line)),None)
        if page:
            rows.append(dict(source_id=key,url=SOURCE_URLS[key],sha256=sha(path),page=page,metric=metric,
                             start=start,end=end,value=value,unit=unit,definition=definition,
                             geography="全国の報告施設" if key!="icu_beds" else "全国の届出病床"))
    return rows


SOURCE_URLS={}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("early-dir","later-dir","sources-dir","private-bundle"):
        parser.add_argument("--"+name,type=Path,required=name!="private-bundle")
    parser.add_argument("--restore-missing",action="store_true")
    args=parser.parse_args()
    started=now()
    for directory in (args.early_dir,args.later_dir,args.sources_dir,args.private_bundle):
        if directory and directory.resolve().is_relative_to(ROOT):
            parser.error("Originals and private copies must be outside Git")
    args.sources_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    if args.private_bundle:
        args.private_bundle.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (OUT/"source_catalog.tsv").open() as stream:
        catalog=list(csv.DictReader(stream,delimiter="\t"))
    SOURCE_URLS.update((x["id"],x["url"]) for x in catalog)
    with ThreadPoolExecutor(max_workers=8) as pool:
        downloaded=list(pool.map(lambda row:acquire(row,args.sources_dir),catalog))
    manifest=[row for row,_ in downloaded]
    sources={row["id"]:path for row,path in downloaded}
    if any(sources.get(key) is None for key, _, _ in NOTICE.values()):
        write_csv(OUT/"supplemental_source_failed_attempt.csv",manifest)
        raise SystemExit("A reporting notice is unavailable. The active crosswalk and manifest were retained.")
    write_csv(OUT/"supplemental_source_manifest.csv",manifest)
    license_verified = (sources.get("mhlw_license") is not None and sources.get("pdl") is not None
        and "PDL1.0" in sources["mhlw_license"].read_text(encoding="utf-8"))
    rights=original_pdfs(args.early_dir,args.later_dir,args.restore_missing,args.private_bundle,license_verified)
    write_csv(OUT/"pdf_preservation_and_rights.csv",rights)
    if args.private_bundle:
        shutil.copyfile(OUT/"pdf_preservation_and_rights.csv",args.private_bundle/"SHA256_manifest.csv")
    reviews,new=revise_crosswalk(sources)
    metrics=validated_metrics(sources)
    if metrics:
        write_csv(OUT/"critical_care_values.csv",metrics)
    active=load_active_crosswalk()
    tests=dict(all_207_originals_hash_verified=len(rights)==207 and all(r["integrity"]=="verified" for r in rights),
       no_original_pdf_listed_as_public=all(r["publication"]=="本体未掲載" for r in rights),
       every_held_occurrence_reassessed=len(reviews)==778,
       allowed_changes_have_notice_page=bool(new) and all(r["source_url"] and r["notice_page"] for r in reviews if r["outcome"]!="hold"),
       early_occupancy_still_held=active["2020-12-23:1:H"]["analysis_gate"]=="hold",
       severe_regional_use_still_held=active["2023-10-04:1:O"]["analysis_gate"]=="hold",
       crosswalk_has_5008_entries=len(active)==5008,
       license_policy_retrieved=license_verified,
       critical_care_metric_types_separate=len(metrics)==7 and len({r["metric"] for r in metrics})==7)
    result=dict(start_jst=started,end_jst=now(),source_success=sum(r["status"]=="downloaded" for r in manifest),
        source_total=len(manifest),new_definition_count=len(new),remaining_held=len(reviews)-len(new),
        original_rights_eligible=sum(r["decision"].startswith("PDL") for r in rights),
        private_copy_count=sum(r["private_copy"]=="hash_verified" for r in rights),
        metric_count=len(metrics),tests=tests)
    (OUT/"final_validation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return all(tests.values())


if __name__=="__main__":
    raise SystemExit(0 if main() else 1)

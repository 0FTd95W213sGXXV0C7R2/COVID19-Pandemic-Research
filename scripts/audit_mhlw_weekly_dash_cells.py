#!/usr/bin/env python3
"""Extract every dash-like cell with workbook/sheet/row/column context; never infer missing-value meaning."""
import json, re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import Counter
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
OUT=ROOT/"data/audits/mhlw/weekly_inpatient_survey_dash_cells.json"
DASH={"－","ー","―","—","–","-","ｰ","−"}
def norm(v): return re.sub(r"\\s+"," ",str(v)).strip()
def main():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    records=[]; statuses=Counter(); symbols=Counter(); books=0
    for item in manifest.get("results",[]):
        if item.get("status")!="downloaded": continue
        path=ROOT/item["local_path"]
        if not path.exists():
            statuses["file_missing"]+=1; continue
        books+=1
        try:
            wb=load_workbook(path,data_only=True,read_only=False)
            for ws in wb.worksheets:
                # Collect note-like text from the same workbook sheet.
                notes=[]
                for row in ws.iter_rows():
                    for c in row:
                        if isinstance(c.value,str):
                            t=norm(c.value)
                            if t and (re.search(r"注\\s*\\d*|※|備考|「－」|未報告|調整中|対象外|含まない|含む|定義|割合|修正",t)):
                                notes.append({"cell":c.coordinate,"text":t})
                for row in ws.iter_rows():
                    for c in row:
                        if not isinstance(c.value,str) or norm(c.value) not in DASH: continue
                        # Header context: collect non-empty labels in preceding 1-5 rows.
                        headers=[]
                        for rr in range(max(1,c.row-5),c.row):
                            vals=[norm(ws.cell(rr,cc).value) for cc in range(1,min(ws.max_column,c.column+2)+1) if ws.cell(rr,cc).value is not None and norm(ws.cell(rr,cc).value)]
                            if vals: headers.append({"row":rr,"labels":vals})
                        # Row context excluding the dash cell.
                        rowvals=[{"column":ws.cell(c.row,cc).column_letter,"value":norm(ws.cell(c.row,cc).value)} for cc in range(1,ws.max_column+1) if cc!=c.column and ws.cell(c.row,cc).value is not None and norm(ws.cell(c.row,cc).value)]
                        symbol=norm(c.value); symbols[symbol]+=1
                        records.append({"snapshot_date":item.get("snapshot_date"),"source_url":item.get("source_url"),
                          "local_path":item.get("local_path"),"sheet":ws.title,"cell":c.coordinate,
                          "row_context":rowvals,"preceding_header_context":headers,"same_sheet_note_candidates":notes})
            wb.close(); statuses["audited"]+=1
        except Exception as e:
            statuses["workbook_error"]+=1
    now=datetime.now(timezone.utc)
    out={"created_at_utc":now.isoformat(),"created_at_jst":now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
      "scope":"Cell-level extraction of dash-like strings from all downloaded weekly MHLW workbooks. No dash is converted to zero or interpreted.",
      "summary":{"workbooks_processed":books,"workbook_status_counts":dict(statuses),"dash_cell_count":len(records),"symbol_counts":dict(symbols)},
      "records":records,
      "classification":{"numeric_zero":0,"not_applicable":0,"not_reported":0,"other":0,"unresolved":len(records)},
      "limitations":["This is a context extraction, not a semantic classification. Same-sheet note candidates are not automatically assumed to apply to a dash cell.",
        "No values were imputed, converted to zero, aggregated nationally, or used to calculate occupancy."]}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["summary"],ensure_ascii=False))
if __name__=="__main__": main()

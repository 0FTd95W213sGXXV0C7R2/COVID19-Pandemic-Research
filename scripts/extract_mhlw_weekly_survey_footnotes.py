#!/usr/bin/env python3
"""Extract all non-empty cells, comments, and merged ranges from selected MHLW weekly survey workbooks."""
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
OUT=ROOT/"data/audits/mhlw/weekly_inpatient_survey_footnotes.json"
DATES=["2020-12-23","2021-06-02","2021-12-22","2023-05-10","2023-10-04","2024-03-27"]

def val(v):
    if v is None: return None
    if hasattr(v,"isoformat"): return v.isoformat()
    return str(v)

def main():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    items={x["snapshot_date"]:x for x in manifest["results"] if x.get("status")=="downloaded"}
    result=[]
    for date in DATES:
        item=items.get(date)
        if not item: result.append({"snapshot_date":date,"status":"missing_manifest_entry"}); continue
        path=ROOT/item["local_path"]
        raw=path.read_bytes()
        wb=load_workbook(path, data_only=False)
        sheets=[]
        for ws in wb.worksheets:
            cells=[]
            for row in ws.iter_rows():
                for c in row:
                    if c.value is not None or c.comment is not None:
                        cells.append({"cell":c.coordinate,"value":val(c.value),
                                      "comment":c.comment.text if c.comment else None,
                                      "data_type":c.data_type})
            sheets.append({"sheet":ws.title,"max_row":ws.max_row,"max_column":ws.max_column,
                           "merged_ranges":[str(x) for x in ws.merged_cells.ranges],
                           "nonempty_cells":cells})
        wb.close()
        result.append({"snapshot_date":date,"status":"extracted","source_url":item["source_url"],
                       "local_path":item["local_path"],"manifest_sha256":item["sha256"],
                       "actual_sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"sheets":sheets})
    now=datetime.now(timezone.utc)
    out={"created_at_utc":now.isoformat(),"created_at_jst":now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
         "scope":"Representative workbooks; all non-empty cells and comments extracted without modifying originals.",
         "dates":DATES,"results":result}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"created_at_jst":out["created_at_jst"],
      "results":[{"date":x["snapshot_date"],"status":x["status"],
      "sheets":[{"name":s["sheet"],"nonempty_cells":len(s["nonempty_cells"])} for s in x.get("sheets",[])]}
      for x in result]},ensure_ascii=False,indent=2))
if __name__=="__main__": main()

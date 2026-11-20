#!/usr/bin/env python3
"""Audit footnote/definition text across all acquired MHLW weekly survey workbooks."""
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
OUT = ROOT / "data/audits/mhlw/weekly_inpatient_survey_footnotes_all.json"
# Match Japanese footnote markers, dash-related explanations, and definition terms.
PATTERN = re.compile(r"注\s*\d*|※|備考|「－」|\b－\b|未報告|調整中|対象外|含まない|含む|割合|定義|修正")

def norm(value):
    return re.sub(r"\s+", " ", str(value)).strip()

def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    for item in manifest.get("results", []):
        if item.get("status") != "downloaded":
            continue
        rel = item.get("local_path")
        path = ROOT / rel
        row = {"snapshot_date": item.get("snapshot_date"), "source_url": item.get("source_url"),
               "local_path": rel, "manifest_sha256": item.get("sha256"), "status": "pending"}
        if not path.exists():
            row["status"] = "file_missing"
            results.append(row)
            continue
        raw = path.read_bytes()
        row["actual_sha256"] = hashlib.sha256(raw).hexdigest()
        row["sha256_match"] = row["actual_sha256"] == row["manifest_sha256"]
        try:
            wb = load_workbook(path, data_only=False, read_only=False)
            sheets = []
            for ws in wb.worksheets:
                notes = []
                for cells in ws.iter_rows():
                    for c in cells:
                        if c.comment is not None:
                            notes.append({"cell": c.coordinate, "kind": "comment", "text": norm(c.comment.text)})
                        if isinstance(c.value, str):
                            txt = norm(c.value)
                            if txt and (PATTERN.search(txt) or c.row >= max(1, ws.max_row - 18)):
                                notes.append({"cell": c.coordinate, "kind": "cell_text", "text": txt})
                seen = set()
                unique = []
                for note in notes:
                    key = (note["kind"], note["text"])
                    if key not in seen:
                        seen.add(key)
                        unique.append(note)
                sheets.append({"sheet": ws.title, "max_row": ws.max_row, "max_column": ws.max_column,
                               "merged_ranges": [str(x) for x in ws.merged_cells.ranges], "notes": unique,
                               "note_occurrences": len(notes), "unique_note_texts": len(unique)})
            wb.close()
            row["sheets"] = sheets
            row["status"] = "audited" if row["sha256_match"] else "sha256_mismatch"
        except Exception as exc:
            row["status"] = "workbook_error"
            row["error"] = repr(exc)
        results.append(row)
    dates = [r.get("snapshot_date") for r in results]
    summary = {"expected_downloaded": manifest.get("downloaded_count"), "processed": len(results),
               "audited": sum(r.get("status") == "audited" for r in results),
               "sha256_mismatch": sum(r.get("status") == "sha256_mismatch" for r in results),
               "missing": sum(r.get("status") == "file_missing" for r in results),
               "errors": sum(r.get("status") == "workbook_error" for r in results),
               "unique_note_texts": len({n["text"] for r in results for s in r.get("sheets", []) for n in s["notes"]})}
    now = datetime.now(timezone.utc)
    out = {"created_at_utc": now.isoformat(), "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
           "official_page": manifest.get("official_page"),
           "scope": "All downloaded weekly survey workbooks; note-like text, comments and trailing text extracted. No values normalized or imputed.",
           "summary": summary, "results": results,
           "limitations": ["Text extraction identifies candidate notes; it does not prove that a note applies to every earlier/later snapshot.",
                          "The dash symbol is retained verbatim; meanings are not inferred unless explicitly stated in that snapshot's notes.",
                          "No national aggregation, occupancy calculation, imputation, schema concatenation, or analytical dataset update was performed."]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created_at_jst": out["created_at_jst"], "summary": summary,
                      "date_range": [min(dates), max(dates)] if dates else None,
                      "statuses": {k: sum(r.get("status") == k for r in results) for k in sorted({r.get("status") for r in results})}},
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

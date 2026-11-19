#!/usr/bin/env python3
"""Bounded acquisition probe for official MHLW G-MIS public CSV links.

Downloads only two CSV URLs linked from official MHLW pages. Records response
metadata and leading rows for source/schema identification. No normalization,
joining, inference, or modification of MASTER/analysis datasets is performed.
"""
from __future__ import annotations
import csv, hashlib, io, json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "mhlw" / "gmis_publication_probe"
MANIFEST = ROOT / "data" / "metadata" / "mhlw" / "gmis_publication_probe_manifest.json"
SOURCES = [
    {
        "id": "mhlw_gmis_historical_link_000893241",
        "page": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00335.html",
        "url": "https://www.mhlw.go.jp/content/10900000/000893241.csv",
    },
    {
        "id": "mhlw_gmis_snapshot_link_001234488",
        "page": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html",
        "url": "https://www.mhlw.go.jp/content/001234488.csv",
    },
]
UA = "COVID19-Pandemic-Research/1.0 (public government data reproducibility audit)"

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def inspect_csv(data: bytes):
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            rows = list(csv.reader(io.StringIO(data.decode(enc))))
            nonempty = [(i + 1, row) for i, row in enumerate(rows) if any(str(x).strip() for x in row)]
            if rows and max((len(r) for r in rows), default=0) > 1:
                likely_headers = []
                for line_no, row in nonempty[:100]:
                    joined = " ".join(str(x) for x in row)
                    if any(k in joined for k in ("医療機関名", "病院名", "確保病床", "即応病床", "実績日", "都道府県")):
                        likely_headers.append({"line": line_no, "row": row})
                return {
                    "encoding_candidate": enc,
                    "row_count_including_blank_rows": len(rows),
                    "nonempty_row_count": len(nonempty),
                    "max_column_count": max((len(r) for r in rows), default=0),
                    "first_30_nonempty_rows": [{"line": n, "row": r} for n, r in nonempty[:30]],
                    "candidate_header_rows_within_first_100_nonempty": likely_headers[:12],
                    "csv_parse_status": "parsed",
                }
        except (UnicodeDecodeError, csv.Error):
            continue
    return {"csv_parse_status": "not_parsed_as_multicolumn_csv"}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    results = []
    for src in SOURCES:
        item = {"source_id": src["id"], "source_page": src["page"], "source_url": src["url"]}
        try:
            response = session.get(src["url"], timeout=(20, 90), allow_redirects=True)
            item.update({
                "http_status": response.status_code,
                "final_url": response.url,
                "content_type": response.headers.get("Content-Type"),
                "content_length_header": response.headers.get("Content-Length"),
            })
            if response.status_code != 200:
                item["status"] = "http_error"
                item["response_preview"] = response.content[:300].decode("utf-8", errors="replace")
            else:
                data = response.content
                content_type = (response.headers.get("Content-Type") or "").lower()
                preview = data[:500].lstrip().lower()
                is_html = b"<html" in preview or b"<!doctype html" in preview
                if is_html or "text/html" in content_type or not data:
                    item["status"] = "not_csv_or_html_response"
                    item["response_preview"] = data[:300].decode("utf-8", errors="replace")
                else:
                    path = OUT / f"{src['id']}.csv"
                    path.write_bytes(data)
                    item.update({
                        "status": "downloaded_for_schema_probe",
                        "filename": path.name,
                        "bytes": len(data),
                        "sha256": sha256(data),
                        **inspect_csv(data),
                    })
        except Exception as exc:
            item["status"] = "request_exception"
            item["error"] = f"{type(exc).__name__}: {exc}"
        results.append(item)

    now = datetime.now(timezone.utc)
    manifest = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "purpose": "source discovery and preliminary schema inspection only",
        "no_normalization_performed": True,
        "no_existing_data_modified": True,
        "results": results,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if not any(x["status"] == "downloaded_for_schema_probe" for x in results):
        raise SystemExit("No official MHLW CSV was successfully acquired; manifest retained.")

if __name__ == "__main__":
    main()

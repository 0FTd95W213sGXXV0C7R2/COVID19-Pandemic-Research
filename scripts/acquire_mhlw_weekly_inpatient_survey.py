#!/usr/bin/env python3
"""Acquire official MHLW weekly hospitalization survey Excel files."""
from __future__ import annotations
import hashlib, io, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import requests
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/mhlw/weekly_inpatient_survey"
MANIFEST = ROOT / "data/metadata/mhlw/weekly_inpatient_survey_manifest.json"
PAGE = "https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html"
UA = "COVID19-Pandemic-Research/1.0 (public government data reproducibility audit)"
DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []
        self.preceding_text = ""
        self.anchor_context = ""
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []
            self.anchor_context = self.preceding_text[-6000:]
    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)
        else:
            self.preceding_text = (self.preceding_text + " " + data)[-6000:]
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, "".join(self.text).strip(), self.anchor_context))
            self.preceding_text = (self.preceding_text + " " + "".join(self.text))[-6000:]
            self.href, self.text, self.anchor_context = None, [], ""

def parse_date(context):
    s = context.translate(DIGITS).replace(" ", "").replace("　", "")
    matches = re.findall(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", s)
    if not matches:
        return None
    y, mo, d = matches[-1]
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"

def discover():
    r = requests.get(PAGE, headers={"User-Agent": UA}, timeout=(20, 60))
    r.raise_for_status()
    parser = LinkParser()
    parser.feed(r.content.decode('utf-8', errors='replace'))
    # Parse the source page with stdlib HTMLParser and preserve the full anchor list.
    # Date labels are extracted from the immediately preceding title text in page source.
    items = {}
    for href, label, preceding_context in parser.links:
        url = urljoin(PAGE, href)
        path = urlparse(url).path.lower()
        if urlparse(url).netloc.lower() != "www.mhlw.go.jp" or not path.endswith((".xlsx", ".xls")):
            continue
        # The parser retains text immediately preceding the link; the report title/date appears there.
        plain = re.sub(r"\s+", " ", preceding_context).strip()
        date = parse_date(plain)
        if not date:
            # Fallback: use the nearest report-title text preceding this link.
            title_match = re.findall(r"20[０-９0-9]{2}年.{0,40}?日０?時?点?", plain.translate(DIGITS))
            if title_match:
                date = parse_date(title_match[-1])
        if not date:
            date = "unknown"
        if url not in items:
            filename = "unknown_unknown_" + Path(path).name
            items[url] = {
                "source_url": url,
                "source_page": PAGE,
                "snapshot_date": date,
                "link_label": label,
                "filename": f"{date}_{filename}",
                "context_excerpt": plain[-500:],
            }
    return list(items.values()), {"url": PAGE, "http_status": r.status_code, "page_bytes": len(r.content)}

def inspect_xlsx(data):
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets = []
        for ws in wb.worksheets:
            preview = []
            for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row or 1, 5), values_only=True):
                preview.append([None if v is None else str(v)[:120] for v in row[:20]])
            sheets.append({
                "sheet_name": ws.title,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "first_5_rows": preview,
            })
        wb.close()
        return {"workbook_status": "xlsx_opened", "sheet_count": len(sheets), "sheets": sheets}
    except Exception as exc:
        return {"workbook_status": "xlsx_parse_error", "parse_error": f"{type(exc).__name__}: {exc}"}

def download_one(item):
    out = dict(item)
    try:
        r = requests.get(item["source_url"], headers={"User-Agent": UA}, timeout=(20, 90))
        out.update({"http_status": r.status_code, "final_url": r.url,
                    "content_type": r.headers.get("Content-Type"),
                    "content_length_header": r.headers.get("Content-Length")})
        if r.status_code != 200:
            out["status"] = "http_error"
            out["response_preview"] = r.content[:200].decode("utf-8", errors="replace")
            return out
        data = r.content
        if not data or data[:2] != b"PK":
            out["status"] = "not_xlsx_binary"
            out["response_preview"] = data[:200].decode("utf-8", errors="replace")
            return out
        path = OUT / item["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        out.update({"status": "downloaded", "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "local_path": str(path.relative_to(ROOT)),
                    **inspect_xlsx(data)})
        return out
    except Exception as exc:
        out["status"] = "request_exception"
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    items, page_info = discover()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(download_one, x) for x in items]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda x: (x.get("snapshot_date", ""), x.get("source_url", "")))
    now = datetime.now(timezone.utc)
    manifest = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "official_page": page_info,
        "discovered_unique_excel_count": len(items),
        "downloaded_count": sum(x.get("status") == "downloaded" for x in results),
        "failed_count": sum(x.get("status") != "downloaded" for x in results),
        "date_range": [results[0]["snapshot_date"], results[-1]["snapshot_date"]] if results else None,
        "results": results,
        "limitations": [
            "Only Excel links currently exposed on the specified MHLW publication page were acquired.",
            "No crosswalk to G-MIS, no aggregation, no imputation, and no analytical dataset update was performed.",
            "This is a separate weekly survey series; comparability with G-MIS snapshots must be assessed from definitions and source notes."
        ]
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "created_at_jst": manifest["created_at_jst"], "page": page_info,
        "discovered": len(items), "downloaded": manifest["downloaded_count"],
        "failed": manifest["failed_count"], "date_range": manifest["date_range"],
        "results": [{"date": x.get("snapshot_date"), "url": x.get("source_url"),
                     "status": x.get("status"), "bytes": x.get("bytes"),
                     "sha256": x.get("sha256"), "workbook": x.get("workbook_status"),
                     "sheets": x.get("sheet_count"), "error": x.get("error")} for x in results]
    }, ensure_ascii=False, indent=2))
    if not manifest["downloaded_count"]:
        raise SystemExit("No weekly survey Excel files acquired.")

if __name__ == "__main__":
    main()

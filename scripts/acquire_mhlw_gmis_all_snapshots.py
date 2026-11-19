#!/usr/bin/env python3
"""Enumerate and acquire every G-MIS hospital-bed CSV linked by MHLW archive pages."""
from __future__ import annotations
import csv, hashlib, io, json, re, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/mhlw/gmis_all_snapshots"
MANIFEST = ROOT / "data/metadata/mhlw/gmis_all_snapshots_manifest.json"
PAGES = [
    "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00335.html",
    "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html",
]
UA = "COVID19-Pandemic-Research/1.0 (public government data reproducibility audit)"
DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []
    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append((self.href, "".join(self.text).strip()))
            self.href = None
            self.text = []

def parse_japanese_date(label):
    s = label.translate(DIGITS).replace(" ", "").replace("　", "")
    m = re.search(r"(令和|平成)(\d+)年(\d+)月(\d+)日", s)
    if not m:
        return None
    era, year, month, day = m.groups()
    year = int(year) + (2018 if era == "令和" else 1988)
    return f"{year:04d}-{int(month):02d}-{int(day):02d}"

def discover():
    found = {}
    page_results = []
    for page in PAGES:
        r = requests.get(page, headers={"User-Agent": UA}, timeout=(20, 60))
        page_item = {"url": page, "http_status": r.status_code, "bytes": len(r.content)}
        r.raise_for_status()
        parser = AnchorParser()
        parser.feed(r.text)
        matched = 0
        for href, label in parser.links:
            absolute = urljoin(page, href)
            parsed = urlparse(absolute)
            if parsed.netloc.lower() != "www.mhlw.go.jp" or not parsed.path.lower().endswith(".csv"):
                continue
            matched += 1
            date = parse_japanese_date(label)
            key = absolute
            if key not in found:
                found[key] = {
                    "source_url": absolute,
                    "source_pages": [page],
                    "published_label": label,
                    "snapshot_date": date,
                }
            else:
                if page not in found[key]["source_pages"]:
                    found[key]["source_pages"].append(page)
                if not found[key].get("snapshot_date") and date:
                    found[key]["snapshot_date"] = date
                if not found[key].get("published_label") and label:
                    found[key]["published_label"] = label
        page_item["csv_links_found"] = matched
        page_results.append(page_item)
    items = list(found.values())
    for item in items:
        if not item["snapshot_date"]:
            item["snapshot_date"] = "unknown"
        name = Path(urlparse(item["source_url"]).path).name
        item["filename"] = f'{item["snapshot_date"]}_{name}'
    return items, page_results

def inspect_csv(data):
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            rows = list(csv.reader(io.StringIO(data.decode(enc))))
        except (UnicodeDecodeError, csv.Error):
            continue
        header_idx = None
        header = None
        for i, row in enumerate(rows[:100]):
            cells = {str(x).strip() for x in row}
            if {"医療機関コード", "実績日", "確保病床数", "即応病床数"}.issubset(cells):
                header_idx, header = i, [str(x).strip() for x in row]
                break
        if header_idx is None:
            continue
        records = []
        for row in rows[header_idx + 1:]:
            if not any(str(x).strip() for x in row):
                continue
            row = row + [""] * max(0, len(header) - len(row))
            records.append(dict(zip(header, row[:len(header)])))
        status = "報告状況" if "報告状況" in header else None
        date_col = "実績日" if "実績日" in header else None
        return {
            "encoding": enc,
            "row_count_including_blanks": len(rows),
            "header_line_1based": header_idx + 1,
            "header": header,
            "data_record_count": len(records),
            "report_status_counts": ({k: sum((r.get(status, "").strip() or "(blank)") == k for r in records)
                                      for k in sorted({r.get(status, "").strip() or "(blank)" for r in records})}
                                     if status else {}),
            "raw_observation_date_counts": ({k: sum(r.get(date_col, "").strip() == k for r in records)
                                             for k in sorted({r.get(date_col, "").strip() for r in records})}
                                            if date_col else {}),
            "schema_status": "recognized_gmis_bed_csv",
        }
    return {"schema_status": "unrecognized_or_non_csv"}

def download_one(item):
    result = dict(item)
    try:
        r = requests.get(item["source_url"], headers={"User-Agent": UA}, timeout=(20, 90))
        result.update({
            "http_status": r.status_code,
            "final_url": r.url,
            "content_type": r.headers.get("Content-Type"),
            "content_length_header": r.headers.get("Content-Length"),
        })
        if r.status_code != 200:
            result["status"] = "http_error"
            result["response_preview"] = r.content[:200].decode("utf-8", errors="replace")
            return result
        data = r.content
        if not data or b"<html" in data[:1000].lower() or b"<!doctype html" in data[:1000].lower():
            result["status"] = "html_or_empty_response"
            result["response_preview"] = data[:200].decode("utf-8", errors="replace")
            return result
        path = OUT / item["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        result.update({
            "status": "downloaded",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "local_path": str(path.relative_to(ROOT)),
            **inspect_csv(data),
        })
        return result
    except Exception as exc:
        result["status"] = "request_exception"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    items, page_results = discover()
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(download_one, item): item for item in items}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda x: (x.get("snapshot_date", ""), x.get("source_url", "")))
    now = datetime.now(timezone.utc)
    manifest = {
        "created_at_utc": now.isoformat(),
        "created_at_jst": now.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "purpose": "complete acquisition of CSV links discoverable from the two official MHLW publication pages",
        "official_pages": page_results,
        "discovered_unique_csv_url_count": len(items),
        "downloaded_count": sum(x.get("status") == "downloaded" for x in results),
        "failed_count": sum(x.get("status") != "downloaded" for x in results),
        "results": results,
        "limitations": [
            "This is the set of CSV links discoverable on the two specified MHLW pages at acquisition time; it does not prove no other archived or removed publications exist.",
            "No longitudinal merge, imputation, occupancy calculation, or analytical dataset update was performed.",
            "Published snapshot date labels and raw CSV observation dates are both retained for later comparison."
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "created_at_jst": manifest["created_at_jst"],
        "page_results": page_results,
        "discovered": len(items),
        "downloaded": manifest["downloaded_count"],
        "failed": manifest["failed_count"],
        "results": [{k: x.get(k) for k in ("snapshot_date","published_label","source_url","status","bytes","sha256","encoding","data_record_count","schema_status","error")} for x in results]
    }, ensure_ascii=False, indent=2))
    if not manifest["downloaded_count"]:
        raise SystemExit("No CSV snapshot acquired.")

if __name__ == "__main__":
    main()

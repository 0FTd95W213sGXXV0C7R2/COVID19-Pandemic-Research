#!/usr/bin/env python3
"""Acquire and inventory the FDMA source workbook from the official website.

This first-stage rebuild preserves the downloaded workbook byte-for-byte and
exports sheet cell matrices for inspection. It does not infer dates, fill
missing values, or create an analytical time series.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "fdma" / "emergency_transport"
DUMP_DIR = ROOT / "data" / "interim" / "fdma" / "emergency_transport" / "sheet_cell_dumps"
AUDIT_DIR = ROOT / "data" / "audits" / "fdma" / "emergency_transport"
SOURCE_PAGE = "https://www.fdma.go.jp/disaster/coronavirus/post-1.html"
EXPECTED_FILENAME = "coronavirus_data.xlsx"
USER_AGENT = "COVID19-Pandemic-Research/1.0 (public data reproducibility audit)"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        if href:
            self.links.append(href)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def acquire_source() -> tuple[Path, dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    page_response = session.get(SOURCE_PAGE, timeout=(20, 90))
    page_response.raise_for_status()
    page_response.encoding = page_response.apparent_encoding or "utf-8"

    parser = LinkParser()
    parser.feed(page_response.text)
    candidates = [
        urljoin(SOURCE_PAGE, href)
        for href in parser.links
        if EXPECTED_FILENAME in href.lower()
    ]
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        raise RuntimeError(
            "Official source page no longer exposes a link containing "
            f"{EXPECTED_FILENAME}; stop and manually audit the page."
        )

    source_url = candidates[0]
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.fdma.go.jp", "fdma.go.jp"}:
        raise RuntimeError(f"Unexpected official-source host: {source_url}")

    response = session.get(source_url, timeout=(30, 180))
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"PK\x03\x04"):
        preview = content[:160].decode("utf-8", errors="replace")
        raise RuntimeError(
            "Official download did not return an XLSX ZIP signature. "
            f"Content-Type={response.headers.get('Content-Type')!r}; "
            f"preview={preview!r}"
        )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / EXPECTED_FILENAME
    out.write_bytes(content)
    acquired_utc = datetime.now(timezone.utc)
    acquired_jst = acquired_utc.astimezone(ZoneInfo("Asia/Tokyo"))
    meta = {
        "source_page": SOURCE_PAGE,
        "source_file_url": response.url,
        "source_host": urlparse(response.url).hostname,
        "http_status": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "content_length_header": response.headers.get("Content-Length"),
        "downloaded_bytes": len(content),
        "sha256": sha256(out),
        "acquired_at_utc": acquired_utc.isoformat(),
        "acquired_at_jst": acquired_jst.isoformat(),
        "filename": out.name,
        "acquisition_method": "Direct HTTPS download from link discovered on the official FDMA page",
    }
    return out, meta


def inventory_workbook(path: Path, meta: dict) -> dict:
    wb = load_workbook(path, read_only=False, data_only=False)
    wb_values = load_workbook(path, read_only=False, data_only=True)

    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    sheets = []
    previews = {}
    for ws in wb.worksheets:
        values_ws = wb_values[ws.title]
        max_row = ws.max_row
        max_col = ws.max_column
        nonempty_rows = 0
        nonempty_cells = 0
        formula_cells = 0
        first_nonempty_row = None
        last_nonempty_row = None

        dump_path = DUMP_DIR / f"{len(sheets)+1:02d}_{re.sub(r'[^A-Za-z0-9_-]+', '_', ws.title).strip('_') or 'sheet'}.csv"
        with dump_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for row in ws.iter_rows():
                row_values = [cell.value for cell in row]
                if any(v is not None for v in row_values):
                    nonempty_rows += 1
                    row_number = row[0].row
                    first_nonempty_row = first_nonempty_row or row_number
                    last_nonempty_row = row_number
                nonempty_cells += sum(v is not None for v in row_values)
                formula_cells += sum(
                    isinstance(v, str) and v.startswith("=") for v in row_values
                )
                writer.writerow(row_values)

        preview_rows = []
        for row in ws.iter_rows(min_row=1, max_row=min(max_row, 25), values_only=True):
            preview_rows.append(list(row[:min(max_col, 30)]))
        previews[ws.title] = {
            "first_25_rows_max_30_columns": preview_rows,
            "merged_ranges": [str(r) for r in ws.merged_cells.ranges],
        }

        sheets.append({
            "sheet_name": ws.title,
            "state": ws.sheet_state,
            "max_row": max_row,
            "max_column": max_col,
            "nonempty_rows": nonempty_rows,
            "nonempty_cells": nonempty_cells,
            "formula_cells": formula_cells,
            "first_nonempty_row": first_nonempty_row,
            "last_nonempty_row": last_nonempty_row,
            "merged_range_count": len(ws.merged_cells.ranges),
            "raw_cell_dump": str(dump_path.relative_to(ROOT)),
        })

    audit = {
        "status": "SOURCE_ACQUIRED_AND_WORKBOOK_INVENTORIED",
        "manifest": meta,
        "workbook": {
            "sheet_count": len(wb.sheetnames),
            "sheet_names_in_order": wb.sheetnames,
            "sheets": sheets,
            "calculation_mode": getattr(wb.calculation, "calcMode", None),
        },
        "important_limitations": [
            "This is a structural inventory, not a validated analytical dataset.",
            "Cell dumps preserve worksheet cell values but not all Excel formatting, formulas' cached values, or workbook behavior; the original XLSX is preserved separately.",
            "No date interpretation, zero/missing classification, annual-block joining, or time-series concatenation is performed at this stage.",
            "The meaning of blank cells, explicit zeros, repeated headers, subtotals, and reporting revisions must be determined in a separate audit.",
            "Do not use historical derived CSVs as inputs to this rebuild.",
        ],
    }

    (AUDIT_DIR / "source_manifest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (AUDIT_DIR / "workbook_inventory.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    with (AUDIT_DIR / "sheet_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = list(sheets[0].keys()) if sheets else ["sheet_name"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sheets)

    return audit


def main():
    path, meta = acquire_source()
    audit = inventory_workbook(path, meta)
    print(json.dumps({
        "status": audit["status"],
        "file": str(path),
        "sha256": meta["sha256"],
        "bytes": meta["downloaded_bytes"],
        "acquired_at_jst": meta["acquired_at_jst"],
        "sheet_names": audit["workbook"]["sheet_names_in_order"],
        "sheet_count": audit["workbook"]["sheet_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

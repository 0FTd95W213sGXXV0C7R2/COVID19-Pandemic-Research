#!/usr/bin/env python3
"""Acquire and audit the four MHLW M1 daily CSVs; never commit raw data."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCES = {
    "newly_confirmed_cases_daily.csv": "https://covid19.mhlw.go.jp/public/opendata/newly_confirmed_cases_daily.csv",
    "severe_cases_daily.csv": "https://covid19.mhlw.go.jp/public/opendata/severe_cases_daily.csv",
    "deaths_cumulative_daily.csv": "https://covid19.mhlw.go.jp/public/opendata/deaths_cumulative_daily.csv",
    "requiring_inpatient_care_etc_daily.csv": "https://covid19.mhlw.go.jp/public/opendata/requiring_inpatient_care_etc_daily.csv",
}
MAX_BYTES = 100 * 1024 * 1024
RETRIES = 3
TIMEOUT_SECONDS = 45
NULL_TOKENS = {"", "na", "n/a", "null", "none", "-"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch(url: str, destination: Path) -> dict:
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "COVID19-Pandemic-Research/1.0 (data acquisition audit)",
                    "Accept": "text/csv,application/octet-stream,*/*",
                },
            )
            digest = hashlib.sha256()
            total = 0
            temp = destination.with_suffix(destination.suffix + ".part")
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response, temp.open("wb") as out:
                status = getattr(response, "status", None)
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError(f"file exceeds safety limit ({MAX_BYTES} bytes)")
                    digest.update(chunk)
                    out.write(chunk)
            if total == 0:
                raise ValueError("empty response")
            temp.replace(destination)
            return {
                "status": "downloaded",
                "attempts": attempt,
                "http_status": status,
                "content_type": content_type,
                "requested_url": url,
                "final_url": final_url,
                "filename": destination.name,
                "size_bytes": total,
                "sha256": digest.hexdigest(),
            }
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            try:
                temp.unlink(missing_ok=True)
            except UnboundLocalError:
                pass
            if attempt < RETRIES:
                time.sleep(2 ** (attempt - 1))
    return {
        "status": "download_failed",
        "attempts": RETRIES,
        "requested_url": url,
        "error": last_error or "unknown error",
    }


def inspect_csv(path: Path) -> dict:
    raw = path.read_bytes()
    text = None
    encoding_used = None
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(encoding)
            encoding_used = encoding
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise UnicodeError("CSV is neither valid UTF-8 nor CP932")

    # Reject an HTML error page even when the server labels it as octet-stream.
    if re.search(r"^\s*<!doctype\s+html|^\s*<html", text[:1000], re.I):
        raise ValueError("response appears to be HTML, not CSV")

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        raise ValueError("CSV header row is missing")
    rows = 0
    missing = {name: 0 for name in headers}
    date_candidates = [
        name for name in headers
        if re.search(r"date|日付|年月日|報告日|公表日", name, re.I)
    ]
    date_column = date_candidates[0] if len(date_candidates) == 1 else None
    dates = []
    duplicate_dates = 0
    seen_dates = set()
    for row in reader:
        rows += 1
        for name in headers:
            value = (row.get(name) or "").strip()
            if value.lower() in NULL_TOKENS:
                missing[name] += 1
        if date_column:
            value = (row.get(date_column) or "").strip()
            if value:
                if value in seen_dates:
                    duplicate_dates += 1
                seen_dates.add(value)
                dates.append(value)

    return {
        "encoding": encoding_used,
        "row_count": rows,
        "column_count": len(headers),
        "columns": headers,
        "missing_values_by_column": missing,
        "date_column_candidates": date_candidates,
        "date_column_used_for_audit": date_column,
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
        "duplicate_date_values": duplicate_dates if date_column else None,
        "date_audit_note": (
            "Heuristic only; confirm the official date definition before analysis."
            if date_column else
            "No unique date column was inferred; inspect the columns manually."
        ),
    }


def main() -> int:
    root = Path(".")
    raw_dir = root / "data" / "raw" / "mhlw"
    audit_dir = root / "audit" / "mhlw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "project": "COVID19-Pandemic-Research",
        "created_at_utc": utc_now(),
        "purpose": "Phase 1 M1 acquisition and structural audit; no analytical integration",
        "source_registry_basis": "User-approved Notion source database; four registered MHLW daily CSV URLs",
        "files": {},
        "limitations": [
            "A successful HTTP download does not establish scientific validity or comparability.",
            "Date-column detection is heuristic and requires manual definition review.",
            "The inpatient-care CSV is audit-only and must not enter the main analysis until the known discrepancy is resolved.",
            "Raw files are retained only in the workflow artifact; they are not committed to Git.",
        ],
    }

    failures = 0
    for filename, url in SOURCES.items():
        destination = raw_dir / filename
        item = fetch(url, destination)
        if item["status"] == "downloaded":
            try:
                item["audit"] = inspect_csv(destination)
            except Exception as exc:
                item["audit_error"] = f"{type(exc).__name__}: {exc}"
                item["status"] = "downloaded_but_audit_failed"
                failures += 1
        else:
            failures += 1
        report["files"][filename] = item

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = audit_dir / f"mhlw_m1_acquisition_audit_{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# MHLW M1 acquisition audit",
        "",
        f"- Created (UTC): {report['created_at_utc']}",
        "- Scope: four registered MHLW daily CSVs",
        "- Raw data policy: workflow artifact only; never commit raw files",
        "",
        "| File | Status | Size (bytes) | SHA-256 | Rows | Date range |",
        "|---|---|---:|---|---:|---|",
    ]
    for filename, item in report["files"].items():
        audit = item.get("audit", {})
        date_range = ""
        if audit.get("date_min") or audit.get("date_max"):
            date_range = f"{audit.get('date_min') or '?'} – {audit.get('date_max') or '?'}"
        lines.append(
            f"| {filename} | {item['status']} | {item.get('size_bytes', '')} | "
            f"{item.get('sha256', '')} | {audit.get('row_count', '')} | {date_range} |"
        )
        if item.get("error"):
            lines.append(f"\nDownload error for {filename}: {item['error']}\n")
        if item.get("audit_error"):
            lines.append(f"\nAudit error for {filename}: {item['audit_error']}\n")
    lines += [
        "",
        "## Interpretation constraints",
        "",
        "- Structural checks do not certify definitions, coverage, revisions, or analytical suitability.",
        "- The inpatient-care CSV remains audit-only until the previously identified discrepancy is resolved.",
        "- No values are corrected, imputed, scaled, or merged by this script.",
        "",
    ]
    (audit_dir / f"mhlw_m1_acquisition_audit_{stamp}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

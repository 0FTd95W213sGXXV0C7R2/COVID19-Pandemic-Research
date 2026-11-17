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
from datetime import date, datetime, timezone, timedelta
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
        temp = destination.with_suffix(destination.suffix + ".part")
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
            temp.unlink(missing_ok=True)
            if attempt < RETRIES:
                time.sleep(2 ** (attempt - 1))
    return {
        "status": "download_failed",
        "attempts": RETRIES,
        "requested_url": url,
        "error": last_error or "unknown error",
    }


def decode_csv(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError("CSV is neither valid UTF-8 nor CP932")


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def parse_number(value: str) -> int | None:
    value = (value or "").strip()
    if value.lower() in NULL_TOKENS:
        return None
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    if not number.is_integer():
        return None
    return int(number)


def inspect_csv(path: Path) -> dict:
    text, encoding_used = decode_csv(path)
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
    dates: list[date] = []
    duplicate_dates = 0
    seen_dates: set[date] = set()
    unparsed_dates = []
    for row in reader:
        rows += 1
        for name in headers:
            value = (row.get(name) or "").strip()
            if value.lower() in NULL_TOKENS:
                missing[name] += 1
        if date_column:
            value = (row.get(date_column) or "").strip()
            if value:
                parsed_date = parse_date(value)
                if parsed_date is None:
                    unparsed_dates.append(value)
                else:
                    if parsed_date in seen_dates:
                        duplicate_dates += 1
                    seen_dates.add(parsed_date)
                    dates.append(parsed_date)

    result = {
        "encoding": encoding_used,
        "row_count": rows,
        "column_count": len(headers),
        "columns": headers,
        "missing_values_by_column": missing,
        "date_column_candidates": date_candidates,
        "date_column_used_for_audit": date_column,
        "date_min": min(dates).isoformat() if dates else None,
        "date_max": max(dates).isoformat() if dates else None,
        "duplicate_date_values": duplicate_dates if date_column else None,
        "unparsed_date_values": unparsed_dates[:20],
        "date_audit_note": (
            "Parsed supported date formats chronologically; confirm the official date definition before analysis."
            if date_column else
            "No unique date column was inferred; inspect the columns manually."
        ),
    }
    if path.name == "deaths_cumulative_daily.csv":
        result["cumulative_death_series_audit"] = audit_cumulative_deaths(text, headers)
    return result


def audit_cumulative_deaths(text: str, headers: list[str]) -> dict:
    """Check completeness and arithmetic consistency without imputing or correcting values."""
    reader = csv.DictReader(io.StringIO(text))
    date_column = "Date" if "Date" in headers else None
    national_column = "ALL" if "ALL" in headers else None
    prefecture_columns = [name for name in headers if name not in {date_column, national_column}]
    expected_prefecture_count = 47
    errors = []
    if date_column is None:
        errors.append("Required Date column was not found.")
    if national_column is None:
        errors.append("Required ALL column was not found.")
    if len(prefecture_columns) != expected_prefecture_count:
        errors.append(
            f"Expected 47 prefecture columns, found {len(prefecture_columns)}."
        )

    records = []
    seen_dates: set[date] = set()
    invalid_date_rows = []
    for row_number, row in enumerate(reader, start=2):
        parsed_date = parse_date(row.get(date_column, "")) if date_column else None
        if parsed_date is None:
            invalid_date_rows.append(row_number)
            continue
        if parsed_date in seen_dates:
            errors.append(f"Duplicate Date value: {parsed_date.isoformat()}")
        seen_dates.add(parsed_date)
        prefecture_values = {name: parse_number(row.get(name, "")) for name in prefecture_columns}
        missing_prefectures = [name for name, value in prefecture_values.items() if value is None]
        prefecture_sum = (
            sum(prefecture_values.values())
            if not missing_prefectures and len(prefecture_columns) == expected_prefecture_count
            else None
        )
        all_value = parse_number(row.get(national_column, "")) if national_column else None
        all_matches = (
            all_value == prefecture_sum
            if all_value is not None and prefecture_sum is not None
            else None
        )
        records.append({
            "date": parsed_date,
            "all": all_value,
            "missing_prefectures": missing_prefectures,
            "prefecture_sum": prefecture_sum,
            "all_matches_prefecture_sum": all_matches,
            "national_value_usable": (
                all_value is not None and prefecture_sum is not None and all_matches is True
            ),
            "prefecture_values": prefecture_values,
        })

    records.sort(key=lambda item: item["date"])
    date_gaps = []
    for previous, current in zip(records, records[1:]):
        expected = previous["date"] + timedelta(days=1)
        if current["date"] != expected:
            date_gaps.append({
                "after": previous["date"].isoformat(),
                "before": current["date"].isoformat(),
                "missing_calendar_days": max((current["date"] - expected).days + 1, 0),
            })

    mismatch_dates = [
        item["date"].isoformat()
        for item in records
        if item["all_matches_prefecture_sum"] is False
    ]
    incomplete_dates = [
        {
            "date": item["date"].isoformat(),
            "missing_prefectures": item["missing_prefectures"],
            "all": item["all"],
            "prefecture_sum": item["prefecture_sum"],
            "national_value_usable": item["national_value_usable"],
        }
        for item in records
        if not item["national_value_usable"]
    ]

    all_decreases = []
    prefecture_decreases = []
    for previous, current in zip(records, records[1:]):
        if previous["all"] is not None and current["all"] is not None:
            if current["all"] < previous["all"]:
                all_decreases.append({
                    "from": previous["date"].isoformat(),
                    "to": current["date"].isoformat(),
                    "previous": previous["all"],
                    "current": current["all"],
                })
        for name in prefecture_columns:
            old = previous["prefecture_values"].get(name)
            new = current["prefecture_values"].get(name)
            if old is not None and new is not None and new < old:
                prefecture_decreases.append({
                    "prefecture": name,
                    "from": previous["date"].isoformat(),
                    "to": current["date"].isoformat(),
                    "previous": old,
                    "current": new,
                })

    complete_records = [item for item in records if item["national_value_usable"]]
    return {
        "scope": "deaths_cumulative_daily.csv only",
        "date_column": date_column,
        "national_column": national_column,
        "prefecture_column_count": len(prefecture_columns),
        "expected_prefecture_column_count": expected_prefecture_count,
        "row_count_with_valid_dates": len(records),
        "invalid_date_row_numbers": invalid_date_rows[:50],
        "duplicate_date_count": len(records) - len(seen_dates),
        "date_min": records[0]["date"].isoformat() if records else None,
        "date_max": records[-1]["date"].isoformat() if records else None,
        "calendar_gaps": date_gaps,
        "all_vs_prefecture_sum_mismatch_dates": mismatch_dates,
        "incomplete_or_unusable_national_dates": incomplete_dates,
        "complete_national_day_count": len(complete_records),
        "last_complete_national_date": (
            complete_records[-1]["date"].isoformat() if complete_records else None
        ),
        "all_cumulative_decreases": all_decreases,
        "prefecture_cumulative_decreases": prefecture_decreases,
        "structural_errors": errors,
        "rules": [
            "A national ALL value is marked usable only when all 47 prefecture values are present and their sum equals ALL.",
            "Missing values are never imputed or replaced with zero.",
            "A cumulative decrease is flagged, not corrected.",
            "These structural checks do not establish the date basis, revision history, cause of death, or analytical suitability.",
            "No daily death counts are derived from cumulative differences.",
        ],
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
            "Cumulative-death structural checks do not resolve the official date basis or retrospective revision history.",
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
    death_audit = report["files"].get("deaths_cumulative_daily.csv", {}).get("audit", {}).get("cumulative_death_series_audit")
    if death_audit:
        lines += [
            "",
            "## Cumulative deaths structural audit",
            "",
            f"- Complete national days: {death_audit['complete_national_day_count']}",
            f"- Last complete national date: {death_audit['last_complete_national_date']}",
            f"- ALL vs 47-prefecture sum mismatches: {len(death_audit['all_vs_prefecture_sum_mismatch_dates'])}",
            f"- Dates with incomplete/unusable national values: {len(death_audit['incomplete_or_unusable_national_dates'])}",
            f"- ALL cumulative decreases: {len(death_audit['all_cumulative_decreases'])}",
            f"- Prefecture cumulative decreases: {len(death_audit['prefecture_cumulative_decreases'])}",
            f"- Calendar gaps: {len(death_audit['calendar_gaps'])}",
            "",
            "### Incomplete or unusable national dates",
            "",
        ]
        if death_audit["incomplete_or_unusable_national_dates"]:
            lines.append("| Date | Missing prefectures | ALL | Prefecture sum |")
            lines.append("|---|---|---:|---:|")
            for item in death_audit["incomplete_or_unusable_national_dates"]:
                lines.append(
                    f"| {item['date']} | {', '.join(item['missing_prefectures']) or '—'} | "
                    f"{item['all'] if item['all'] is not None else '—'} | "
                    f"{item['prefecture_sum'] if item['prefecture_sum'] is not None else '—'} |"
                )
        else:
            lines.append("No incomplete national dates were detected.")
        if death_audit["all_cumulative_decreases"]:
            lines += ["", "### ALL cumulative decreases", ""]
            for item in death_audit["all_cumulative_decreases"]:
                lines.append(
                    f"- {item['from']} → {item['to']}: {item['previous']} → {item['current']}"
                )
        if death_audit["prefecture_cumulative_decreases"]:
            lines += ["", "### Prefecture cumulative decreases", ""]
            for item in death_audit["prefecture_cumulative_decreases"]:
                lines.append(
                    f"- {item['prefecture']}: {item['from']} → {item['to']} "
                    f"({item['previous']} → {item['current']})"
                )
    lines += [
        "",
        "## Interpretation constraints",
        "",
        "- Structural checks do not certify definitions, coverage, revisions, or analytical suitability.",
        "- The inpatient-care CSV remains audit-only until the previously identified discrepancy is resolved.",
        "- No values are corrected, imputed, scaled, or merged by this script.",
        "- Cumulative deaths are not converted to daily deaths by differencing.",
        "",
    ]
    (audit_dir / f"mhlw_m1_acquisition_audit_{stamp}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

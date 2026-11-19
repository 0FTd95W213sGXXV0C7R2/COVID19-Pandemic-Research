#!/usr/bin/env python3
"""Audit FDMA workbook weekly headers, reporting units, blanks/zeros and partitions.

This is a source-first audit. It reads only the preserved official XLSX.
No values are imputed, no annual blocks are joined by guesswork, and no
canonical analytical series is emitted.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/fdma/emergency_transport/coronavirus_data.xlsx"
MANIFEST = ROOT / "data/audits/fdma/emergency_transport/source_manifest.json"
OUT = ROOT / "data/audits/fdma/emergency_transport"
WEEKDAY_JA = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
DATE_RE = re.compile(
    r"(?P<sm>\d{1,2})\s*/\s*(?P<sd>\d{1,2})\s*[\(（]\s*(?P<sw>[月火水木金土日])\s*[\)）]"
    r"\s*[～〜~]\s*"
    r"(?P<em>\\d{1,2})\\s*/\\s*(?P<ed>\\d{1,2})\\s*[\\(（]\\s*(?P<ew>[月火水木金土日])\\s*[\\)）]"
)
SHEET_NAMES = [
    "搬送困難事案（今回）",
    "搬送困難事案（前年同期）",
    "うちコロナ疑い事案（今回）",
    "うち非コロナ疑い事案（今回）",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reiwa_year(value) -> int:
    m = re.search(r"R\s*(\d+)", str(value or ""))
    if not m:
        raise ValueError(f"Cannot infer calendar-year anchor from first era label: {value!r}")
    return 2018 + int(m.group(1))


def parse_header(raw: str):
    m = DATE_RE.search(str(raw or "").replace("\u3000", " "))
    if not m:
        return None
    return {
        "start_month": int(m.group("sm")),
        "start_day": int(m.group("sd")),
        "start_weekday": m.group("sw"),
        "end_month": int(m.group("em")),
        "end_day": int(m.group("ed")),
        "end_weekday": m.group("ew"),
    }


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not SOURCE.exists() or not MANIFEST.exists():
        raise FileNotFoundError("Official workbook or acquisition manifest is missing.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    actual_hash = sha256(SOURCE)
    if actual_hash != manifest.get("sha256"):
        raise RuntimeError("Source workbook SHA-256 does not match its acquisition manifest.")

    wb = load_workbook(SOURCE, data_only=False, read_only=False)
    wb_cached = load_workbook(SOURCE, data_only=True, read_only=False)
    if wb.sheetnames != SHEET_NAMES:
        raise RuntimeError(f"Unexpected sheet names/order: {wb.sheetnames!r}")

    header_rows = []
    header_maps = {}
    sheet_summaries = []
    facility_maps = {}
    quality_summaries = {}

    for sheet_name in SHEET_NAMES:
        ws = wb[sheet_name]
        wsv = wb_cached[sheet_name]
        anchor_year = reiwa_year(ws.cell(3, 4).value)
        header_cols = [
            col for col in range(4, ws.max_column + 1)
            if ws.cell(4, col).value not in (None, "")
        ]
        parsed_weeks = []
        unparsed = 0
        start_mismatches = 0
        end_mismatches = 0
        previous_expected = None

        for idx, col in enumerate(header_cols, start=1):
            raw = ws.cell(4, col).value
            parts = parse_header(raw)
            if idx == 1:
                if parts is None:
                    raise RuntimeError(f"First week header cannot be parsed: {sheet_name} {raw!r}")
                anchor = date(anchor_year, parts["start_month"], parts["start_day"])
                if anchor.weekday() != WEEKDAY_JA[parts["start_weekday"]]:
                    raise RuntimeError(
                        f"Era-year anchor and weekday disagree: {sheet_name} {raw!r} / {anchor}"
                    )
            expected_start = anchor + timedelta(days=7 * (idx - 1))
            expected_end = expected_start + timedelta(days=6)

            if parts is None:
                unparsed += 1
                start_match = end_match = False
                label_start = label_end = ""
                issue = "UNPARSED_HEADER"
            else:
                label_start = f"{expected_start.year:04d}-{parts['start_month']:02d}-{parts['start_day']:02d}"
                end_year = expected_start.year + (1 if parts["end_month"] < parts["start_month"] else 0)
                try:
                    label_end_date = date(end_year, parts["end_month"], parts["end_day"])
                    label_end = label_end_date.isoformat()
                except ValueError:
                    label_end_date = None
                    label_end = ""
                start_match = (
                    parts["start_month"] == expected_start.month
                    and parts["start_day"] == expected_start.day
                    and WEEKDAY_JA[parts["start_weekday"]] == expected_start.weekday()
                )
                end_match = (
                    label_end_date == expected_end
                    and WEEKDAY_JA[parts["end_weekday"]] == expected_end.weekday()
                )
                if not start_match:
                    start_mismatches += 1
                if not end_match:
                    end_mismatches += 1
                issues = []
                if not start_match:
                    issues.append("START_LABEL_MISMATCH")
                if not end_match:
                    issues.append("END_LABEL_MISMATCH")
                issue = ";".join(issues) if issues else ""

            record = {
                "sheet_name": sheet_name,
                "week_index": idx,
                "excel_column": col,
                "era_label_anchor": str(ws.cell(3, 4).value),
                "raw_header": str(raw),
                "expected_start_date": expected_start.isoformat(),
                "expected_end_date": expected_end.isoformat(),
                "label_start_date_interpreted": label_start,
                "label_end_date_interpreted": label_end,
                "start_label_match": start_match,
                "end_label_match": end_match,
                "issue": issue,
            }
            header_rows.append(record)
            parsed_weeks.append(record)
            if parts is not None and start_match:
                header_maps.setdefault(sheet_name, {})[expected_start.isoformat()] = col
            previous_expected = expected_start

        header_maps.setdefault(sheet_name, {})
        sheet_summaries.append({
            "sheet_name": sheet_name,
            "era_label_anchor": str(ws.cell(3, 4).value),
            "anchor_calendar_year": anchor_year,
            "week_header_count": len(header_cols),
            "first_expected_week": parsed_weeks[0]["expected_start_date"] if parsed_weeks else None,
            "last_expected_week": parsed_weeks[-1]["expected_start_date"] if parsed_weeks else None,
            "last_expected_week_end": parsed_weeks[-1]["expected_end_date"] if parsed_weeks else None,
            "unparsed_headers": unparsed,
            "start_label_mismatches": start_mismatches,
            "end_label_mismatches": end_mismatches,
            "year_label_cells": [
                {"column": c, "value": str(ws.cell(3, c).value)}
                for c in range(4, ws.max_column + 1)
                if ws.cell(3, c).value not in (None, "")
            ],
            "merged_ranges_in_year_row": [
                str(rng) for rng in ws.merged_cells.ranges
                if rng.min_row <= 3 <= rng.max_row
            ],
        })

        facility_rows = []
        for row in range(6, 58):
            pref = ws.cell(row, 2).value
            hq = ws.cell(row, 3).value
            if pref not in (None, "") or hq not in (None, ""):
                facility_rows.append((str(pref or ""), str(hq or "")))
        facility_maps[sheet_name] = facility_rows

        counts = Counter()
        formula_total = 0
        for row in range(6, 58):
            for col in header_cols:
                value = ws.cell(row, col).value
                if value is None:
                    counts["blank"] += 1
                elif is_number(value):
                    counts["numeric"] += 1
                    if value == 0:
                        counts["explicit_zero"] += 1
                    if value < 0:
                        counts["negative"] += 1
                elif isinstance(value, str) and value.startswith("="):
                    counts["formula"] += 1
                else:
                    counts["other_nonempty"] += 1

        total_row = 58
        cached_total_count = 0
        cached_total_mismatches = 0
        cached_total_unavailable = 0
        total_formula_count = 0
        for col in header_cols:
            formula = ws.cell(total_row, col).value
            cached_total = wsv.cell(total_row, col).value
            if isinstance(formula, str) and formula.startswith("="):
                total_formula_count += 1
            if is_number(cached_total):
                cached_total_count += 1
                detail_values = [ws.cell(row, col).value for row in range(6, 58)]
                if all(is_number(v) for v in detail_values):
                    if sum(detail_values) != cached_total:
                        cached_total_mismatches += 1
            else:
                cached_total_unavailable += 1

        quality_summaries[sheet_name] = {
            **dict(counts),
            "data_cells_expected": len(header_cols) * 52,
            "total_row_formula_cells": total_formula_count,
            "cached_total_numeric_cells": cached_total_count,
            "cached_total_non_numeric_or_missing": cached_total_unavailable,
            "cached_total_mismatches_vs_52_facility_sum": cached_total_mismatches,
        }

    # Compare reporting-unit identity across all four sheets.
    reference_facilities = facility_maps[SHEET_NAMES[0]]
    facility_consistency = {
        "reference_sheet": SHEET_NAMES[0],
        "reference_facility_rows": len(reference_facilities),
        "reference_unique_hq_names": len({x[1] for x in reference_facilities}),
        "all_sheets_same_ordered_prefecture_hq_pairs": all(
            facility_maps[name] == reference_facilities for name in SHEET_NAMES[1:]
        ),
        "per_sheet_facility_rows": {
            name: len(facility_maps[name]) for name in SHEET_NAMES
        },
        "per_sheet_unique_hq_names": {
            name: len({x[1] for x in facility_maps[name]}) for name in SHEET_NAMES
        },
    }

    # Compare COVID-suspected + non-COVID-suspected against overall counts.
    overall, covid, noncovid = SHEET_NAMES[0], SHEET_NAMES[2], SHEET_NAMES[3]
    common_dates = sorted(
        set(header_maps.get(overall, {}))
        & set(header_maps.get(covid, {}))
        & set(header_maps.get(noncovid, {}))
    )
    mismatch_rows = []
    reconciliation = Counter()
    ws_all, ws_c, ws_n = wb[overall], wb[covid], wb[noncovid]
    for row in range(6, 58):
        for week_date in common_dates:
            vals = [
                ws_all.cell(row, header_maps[overall][week_date]).value,
                ws_c.cell(row, header_maps[covid][week_date]).value,
                ws_n.cell(row, header_maps[noncovid][week_date]).value,
            ]
            if all(is_number(v) for v in vals):
                reconciliation["numeric_triplets"] += 1
                if vals[0] == vals[1] + vals[2]:
                    reconciliation["exact_partition_matches"] += 1
                else:
                    reconciliation["partition_mismatches"] += 1
                    mismatch_rows.append({
                        "prefecture": str(ws_all.cell(row, 2).value or ""),
                        "fire_department": str(ws_all.cell(row, 3).value or ""),
                        "week_start": week_date,
                        "overall": vals[0],
                        "covid_suspected": vals[1],
                        "non_covid_suspected": vals[2],
                        "subgroup_sum": vals[1] + vals[2],
                        "difference_overall_minus_subgroups": vals[0] - vals[1] - vals[2],
                    })
            else:
                reconciliation["incomplete_triplets"] += 1
                mismatch_rows.append({
                    "prefecture": str(ws_all.cell(row, 2).value or ""),
                    "fire_department": str(ws_all.cell(row, 3).value or ""),
                    "week_start": week_date,
                    "overall": vals[0],
                    "covid_suspected": vals[1],
                    "non_covid_suspected": vals[2],
                    "subgroup_sum": "",
                    "difference_overall_minus_subgroups": "",
                })

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUT / "week_header_inventory.csv",
        header_rows,
        list(header_rows[0].keys()) if header_rows else ["sheet_name"],
    )
    write_csv(
        OUT / "partition_reconciliation.csv",
        mismatch_rows,
        ["prefecture", "fire_department", "week_start", "overall", "covid_suspected",
         "non_covid_suspected", "subgroup_sum", "difference_overall_minus_subgroups"],
    )
    report = {
        "status": "SOURCE_HEADER_AND_CELL_QUALITY_AUDIT",
        "audit_timestamp_jst": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        "source_sha256": actual_hash,
        "source_bytes": SOURCE.stat().st_size,
        "sheet_summaries": sheet_summaries,
        "facility_consistency": facility_consistency,
        "cell_quality_by_sheet": quality_summaries,
        "subgroup_partition_reconciliation": {
            "common_week_count": len(common_dates),
            "common_week_first": common_dates[0] if common_dates else None,
            "common_week_last": common_dates[-1] if common_dates else None,
            **dict(reconciliation),
            "mismatch_or_incomplete_rows": len(mismatch_rows),
        },
        "limitations": [
            "Calendar dates are anchored to the first header's Japanese era-year label and then checked against every printed month/day and weekday.",
            "A mismatch is flagged; it is not silently corrected in the source workbook.",
            "Formula cached values may be absent or stale; formula cells are separately counted and not recalculated.",
            "Blank cells and explicit numeric zeroes are counted separately.",
            "No daily interpolation, imputation, or canonical time-series construction is performed.",
        ],
    }
    (OUT / "weekly_header_and_values_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "source_sha256": actual_hash,
        "sheet_summaries": [
            {k: s[k] for k in ("sheet_name", "week_header_count", "first_expected_week",
                                "last_expected_week", "last_expected_week_end",
                                "unparsed_headers", "start_label_mismatches",
                                "end_label_mismatches")}
            for s in sheet_summaries
        ],
        "facility_consistency": facility_consistency,
        "cell_quality_by_sheet": quality_summaries,
        "subgroup_partition_reconciliation": report["subgroup_partition_reconciliation"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

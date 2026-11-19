#!/usr/bin/env python3
"""Build a transparent long-format FDMA dataset from the official workbook only."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/fdma/emergency_transport/coronavirus_data.xlsx"
SOURCE_MANIFEST = ROOT / "data/audits/fdma/emergency_transport/source_manifest.json"
OUT_CSV = ROOT / "data/processed/fdma/emergency_transport/weekly_long.csv"
OUT_MANIFEST = ROOT / "data/metadata/fdma/emergency_transport/manifest.json"
OUT_AUDIT = ROOT / "data/audits/fdma/emergency_transport/normalized_dataset_build_audit.json"
OUT_DICTIONARY = ROOT / "docs/data_dictionary/FDMA_EMERGENCY_TRANSPORT_WEEKLY.md"

WEEKDAY_JA = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
DATE_RE = re.compile(
    r"(?P<sm>\d{1,2})\s*/\s*(?P<sd>\d{1,2})\s*[\(（]?\s*(?P<sw>[月火水木金土日])\s*[\)）]"
    r"\s*[～〜~]\s*"
    r"(?P<em>\d{1,2})\s*/\s*(?P<ed>\d{1,2})\s*[\(（]\s*(?P<ew>[月火水木金土日])\s*[\)）]"
)

SHEETS = [
    {"sheet": "搬送困難事案（今回）", "metric_code": "transport_difficulty_overall_current",
     "metric_label": "救急搬送困難事案数（今回・全体）", "series_role": "current_overall",
     "comparison_basis": "current_period"},
    {"sheet": "搬送困難事案（前年同期）", "metric_code": "transport_difficulty_overall_previous_year",
     "metric_label": "救急搬送困難事案数（前年同期・全体）", "series_role": "previous_year_comparator",
     "comparison_basis": "previous_year_same_week_index"},
    {"sheet": "うちコロナ疑い事案（今回）", "metric_code": "transport_difficulty_covid_suspected_current",
     "metric_label": "救急搬送困難事案のうちコロナ疑い事案（今回）", "series_role": "current_subgroup",
     "comparison_basis": "current_period_subgroup"},
    {"sheet": "うち非コロナ疑い事案（今回）", "metric_code": "transport_difficulty_non_covid_suspected_current",
     "metric_label": "救急搬送困難事案のうち非コロナ疑い事案（今回）", "series_role": "current_subgroup",
     "comparison_basis": "current_period_subgroup"},
]

FIELDS = [
    "dataset_id", "metric_code", "metric_label", "series_role", "comparison_basis",
    "week_index", "period_start_date", "period_end_date", "period_end_date_expected",
    "period_end_date_printed", "date_header_status", "raw_week_header", "prefecture", "prefecture_value_source",
    "fire_department", "aggregation_level", "value", "unit", "observation_status",
    "paired_current_week_start_date", "source_sheet", "source_cell", "source_formula",
    "source_file_sha256",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def era_year(value) -> int:
    m = re.search(r"R\s*(\d+)", str(value or ""))
    if not m:
        raise ValueError(f"Missing Reiwa-year anchor: {value!r}")
    return 2018 + int(m.group(1))


def parse_header(raw):
    m = DATE_RE.search(str(raw or "").replace("\u3000", " "))
    if not m:
        return None
    return {
        "sm": int(m.group("sm")), "sd": int(m.group("sd")), "sw": m.group("sw"),
        "em": int(m.group("em")), "ed": int(m.group("ed")), "ew": m.group("ew"),
    }


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def get_weeks(ws):
    cols = [c for c in range(4, ws.max_column + 1) if ws.cell(4, c).value not in (None, "")]
    if not cols:
        raise RuntimeError(f"No week headers found in {ws.title}")
    first = parse_header(ws.cell(4, cols[0]).value)
    if first is None:
        raise RuntimeError(f"Unparseable first week header in {ws.title}")
    anchor = date(era_year(ws.cell(3, 4).value), first["sm"], first["sd"])
    if anchor.weekday() != WEEKDAY_JA[first["sw"]]:
        raise RuntimeError(f"Era year and weekday disagree in {ws.title}: {anchor}")

    weeks = []
    for index, col in enumerate(cols, start=1):
        raw = str(ws.cell(4, col).value)
        p = parse_header(raw)
        if p is None:
            raise RuntimeError(f"Unparseable week header: {ws.title} {col} {raw!r}")
        start = anchor + timedelta(days=7 * (index - 1))
        expected_end = start + timedelta(days=6)
        start_match = (
            p["sm"] == start.month and p["sd"] == start.day
            and WEEKDAY_JA[p["sw"]] == start.weekday()
        )
        if not start_match:
            raise RuntimeError(
                f"Week start mismatch; do not auto-correct: {ws.title} col {col} {raw!r} expected {start}"
            )
        end_year = start.year + (1 if p["em"] < p["sm"] else 0)
        printed_end = date(end_year, p["em"], p["ed"])
        end_match = printed_end == expected_end and WEEKDAY_JA[p["ew"]] == expected_end.weekday()
        weeks.append({
            "index": index, "column": col, "start": start, "expected_end": expected_end,
            "printed_end": printed_end, "raw_header": raw, "end_match": end_match,
            "date_header_status": "matched" if end_match else "printed_end_date_or_weekday_mismatch",
        })
    return weeks


def main():
    if not SOURCE.exists() or not SOURCE_MANIFEST.exists():
        raise FileNotFoundError("Official source workbook or source manifest missing.")
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source_hash = sha256(SOURCE)
    if source_hash != source_manifest.get("sha256"):
        raise RuntimeError("Official workbook hash differs from acquisition manifest.")

    wb = load_workbook(SOURCE, data_only=False, read_only=False)
    wb_values = load_workbook(SOURCE, data_only=True, read_only=False)
    expected_sheets = [x["sheet"] for x in SHEETS]
    if wb.sheetnames != expected_sheets:
        raise RuntimeError(f"Unexpected worksheet names/order: {wb.sheetnames!r}")

    weeks_by_sheet = {}
    facilities_by_sheet = {}
    for cfg in SHEETS:
        ws = wb[cfg["sheet"]]
        weeks = get_weeks(ws)
        if len(weeks) not in (157, 261):
            raise RuntimeError(f"Unexpected week count in {cfg['sheet']}: {len(weeks)}")
        facilities = []
        for row in range(6, 58):
            pref = ws.cell(row, 2).value
            hq = ws.cell(row, 3).value
            pref_source = "explicit_cell"
            if pref in (None, ""):
                # The source workbook merges prefecture cells vertically for
                # multiple fire departments in the same prefecture. Resolve
                # only when the row is explicitly inside a merged B-column range.
                merged_pref = next((
                    rng for rng in ws.merged_cells.ranges
                    if rng.min_col == 2 and rng.max_col == 2
                    and rng.min_row <= row <= rng.max_row
                ), None)
                if merged_pref is not None:
                    pref = ws.cell(merged_pref.min_row, 2).value
                    pref_source = f"merged_range:{merged_pref}"
            if pref in (None, "") or hq in (None, ""):
                raise RuntimeError(f"Facility identifier missing outside an explicit merged range: {cfg['sheet']} row {row}")
            facilities.append((str(pref), str(hq), row, pref_source))
        if len(facilities) != 52 or len({x[1] for x in facilities}) != 52:
            raise RuntimeError(f"Expected 52 unique fire departments in {cfg['sheet']}")
        if ws.cell(58, 3).value != "52本部合計":
            raise RuntimeError(f"Unexpected total row label in {cfg['sheet']}")
        weeks_by_sheet[cfg["sheet"]] = weeks
        facilities_by_sheet[cfg["sheet"]] = facilities

    reference_facilities = [(x[0], x[1]) for x in facilities_by_sheet[SHEETS[0]["sheet"]]]
    if any(
        [(x[0], x[1]) for x in facilities_by_sheet[cfg["sheet"]]] != reference_facilities
        for cfg in SHEETS[1:]
    ):
        raise RuntimeError("Facility names/order differ between source sheets.")
    prefecture_source_counts = Counter(
        x[3] == "explicit_cell"
        for sheet in facilities_by_sheet.values() for x in sheet
    )

    current_weeks = weeks_by_sheet[SHEETS[0]["sheet"]]
    prior_weeks = weeks_by_sheet[SHEETS[1]["sheet"]]
    if len(current_weeks) != len(prior_weeks):
        raise RuntimeError("Current and previous-year tabs have different week counts.")
    prior_pair_dates = {}
    prior_pair_deltas = []
    for cur, prev in zip(current_weeks, prior_weeks):
        delta = (cur["start"] - prev["start"]).days
        prior_pair_deltas.append(delta)
        if delta != 364:
            raise RuntimeError(f"Previous-year week pairing is not 364 days: index {cur['index']} delta {delta}")
        prior_pair_dates[prev["index"]] = cur["start"].isoformat()

    covid_weeks = weeks_by_sheet[SHEETS[2]["sheet"]]
    noncovid_weeks = weeks_by_sheet[SHEETS[3]["sheet"]]
    current_map = {x["start"]: x for x in current_weeks}
    covid_map = {x["start"]: x for x in covid_weeks}
    noncovid_map = {x["start"]: x for x in noncovid_weeks}
    common_dates = sorted(set(current_map) & set(covid_map) & set(noncovid_map))
    if len(common_dates) != 157:
        raise RuntimeError(f"Expected 157 aligned subgroup weeks, found {len(common_dates)}")

    rows = []
    total_checks = Counter()
    partition_checks = Counter()
    incomplete_locations = []
    end_date_mismatch_weeks = []

    for cfg in SHEETS:
        ws, wsv = wb[cfg["sheet"]], wb_values[cfg["sheet"]]
        weeks = weeks_by_sheet[cfg["sheet"]]
        facilities = facilities_by_sheet[cfg["sheet"]]

        for week in weeks:
            col = week["column"]
            if not week["end_match"]:
                end_date_mismatch_weeks.append({
                    "sheet": cfg["sheet"], "week_index": week["index"],
                    "start": week["start"].isoformat(),
                    "printed_end": week["printed_end"].isoformat(),
                    "expected_end": week["expected_end"].isoformat(),
                    "raw_header": week["raw_header"],
                })

            detail_values = []
            for pref, hq, row_number, pref_source in facilities:
                value = ws.cell(row_number, col).value
                source_cell = f"{get_column_letter(col)}{row_number}"
                if value is None:
                    clean_value, observation_status = "", "blank_in_source"
                elif is_number(value):
                    if value < 0 or int(value) != value:
                        raise RuntimeError(f"Unexpected non-integer/negative count: {cfg['sheet']} {source_cell} {value}")
                    clean_value = int(value)
                    observation_status = "reported_zero" if value == 0 else "reported_numeric_value"
                else:
                    raise RuntimeError(f"Unexpected non-numeric detail value: {cfg['sheet']} {source_cell} {value!r}")
                detail_values.append(value)
                rows.append({
                    "dataset_id": "FDMA_EMERGENCY_TRANSPORT_WEEKLY_2026",
                    "metric_code": cfg["metric_code"], "metric_label": cfg["metric_label"],
                    "series_role": cfg["series_role"], "comparison_basis": cfg["comparison_basis"],
                    "week_index": week["index"], "period_start_date": week["start"].isoformat(),
                    "period_end_date": week["expected_end"].isoformat() if week["end_match"] else "",
                    "period_end_date_expected": week["expected_end"].isoformat(),
                    "period_end_date_printed": week["printed_end"].isoformat(),
                    "date_header_status": week["date_header_status"], "raw_week_header": week["raw_header"],
                    "prefecture": pref, "prefecture_value_source": pref_source,
                    "fire_department": hq, "aggregation_level": "fire_department",
                    "value": clean_value, "unit": "件", "observation_status": observation_status,
                    "paired_current_week_start_date": (
                        prior_pair_dates[week["index"]] if cfg["series_role"] == "previous_year_comparator" else ""
                    ),
                    "source_sheet": cfg["sheet"], "source_cell": source_cell,
                    "source_formula": "", "source_file_sha256": source_hash,
                })

            total_formula = ws.cell(58, col).value
            cached_total = wsv.cell(58, col).value
            if not is_number(cached_total):
                raise RuntimeError(f"Missing cached 52-HQ total: {cfg['sheet']} col {col}")
            if not all(v is None or is_number(v) for v in detail_values):
                raise RuntimeError(f"Non-numeric detail value blocks total check: {cfg['sheet']} col {col}")
            numeric_sum = sum(v for v in detail_values if is_number(v))
            total_checks["columns_checked"] += 1
            if any(v is None for v in detail_values):
                total_checks["columns_with_blank_detail"] += 1
            if numeric_sum != cached_total:
                total_checks["mismatches"] += 1
                raise RuntimeError(f"52-HQ total differs from detail sum: {cfg['sheet']} col {col}")

            total_cell = f"{get_column_letter(col)}58"
            rows.append({
                "dataset_id": "FDMA_EMERGENCY_TRANSPORT_WEEKLY_2026",
                "metric_code": cfg["metric_code"], "metric_label": cfg["metric_label"],
                "series_role": cfg["series_role"], "comparison_basis": cfg["comparison_basis"],
                "week_index": week["index"], "period_start_date": week["start"].isoformat(),
                "period_end_date": week["expected_end"].isoformat() if week["end_match"] else "",
                "period_end_date_expected": week["expected_end"].isoformat(),
                "period_end_date_printed": week["printed_end"].isoformat(),
                "date_header_status": week["date_header_status"], "raw_week_header": week["raw_header"],
                "prefecture": "", "prefecture_value_source": "not_applicable",
                "fire_department": "52本部合計",
                "aggregation_level": "52_fire_department_total", "value": int(cached_total), "unit": "件",
                "observation_status": (
                    "cached_excel_total_formula"
                    if isinstance(total_formula, str) and total_formula.startswith("=")
                    else "source_total_value"
                ),
                "paired_current_week_start_date": (
                    prior_pair_dates[week["index"]] if cfg["series_role"] == "previous_year_comparator" else ""
                ),
                "source_sheet": cfg["sheet"], "source_cell": total_cell,
                "source_formula": (
                    total_formula if isinstance(total_formula, str) and total_formula.startswith("=") else ""
                ),
                "source_file_sha256": source_hash,
            })

    ws_all, ws_c, ws_n = wb[SHEETS[0]["sheet"]], wb[SHEETS[2]["sheet"]], wb[SHEETS[3]["sheet"]]
    map_all = {x["start"]: x["column"] for x in current_weeks}
    map_c = {x["start"]: x["column"] for x in covid_weeks}
    map_n = {x["start"]: x["column"] for x in noncovid_weeks}
    for row in range(6, 58):
        for dt in common_dates:
            vals = [ws_all.cell(row, map_all[dt]).value, ws_c.cell(row, map_c[dt]).value, ws_n.cell(row, map_n[dt]).value]
            if all(is_number(v) for v in vals):
                partition_checks["numeric_triplets"] += 1
                if vals[0] == vals[1] + vals[2]:
                    partition_checks["exact_matches"] += 1
                else:
                    partition_checks["mismatches"] += 1
                    raise RuntimeError(f"Subgroup partition mismatch: row {row}, week {dt}, values {vals!r}")
            else:
                partition_checks["incomplete_triplets"] += 1
                incomplete_locations.append({
                    "prefecture": str(ws_all.cell(row, 2).value),
                    "fire_department": str(ws_all.cell(row, 3).value),
                    "week_start": dt.isoformat(),
                    "overall": vals[0], "covid_suspected": vals[1], "non_covid_suspected": vals[2],
                })

    expected_rows = sum(len(weeks_by_sheet[x["sheet"]]) * 53 for x in SHEETS)
    if len(rows) != expected_rows:
        raise RuntimeError(f"Unexpected normalized row count: {len(rows)} != {expected_rows}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    now_jst = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()
    manifest = {
        "dataset_id": "FDMA_EMERGENCY_TRANSPORT_WEEKLY_2026",
        "status": "NORMALIZED_SOURCE_DATASET_BUILT_WITH_AUDIT_FLAGS",
        "created_at_jst": now_jst,
        "source": {
            "publisher": "総務省消防庁",
            "source_page": "https://www.fdma.go.jp/disaster/coronavirus/post-1.html",
            "source_file_url": source_manifest["source_file_url"],
            "filename": SOURCE.name, "sha256": source_hash, "bytes": SOURCE.stat().st_size,
            "acquired_at_jst": source_manifest["acquired_at_jst"],
        },
        "transformation": {
            "script": "scripts/build_fdma_weekly_long.py",
            "workflow": ".github/workflows/fdma_source_rebuild.yml",
            "github_sha": os.environ.get("GITHUB_SHA", ""),
            "method": "Long-format extraction from the official workbook's four original sheets; no historical derived CSV input.",
            "time_granularity": "weekly",
            "missing_value_policy": "Blank source cells remain blank; explicit numeric zero remains 0; no imputation.",
            "date_policy": "Week start is anchored to the first Reiwa-year header and validated against every printed start date/weekday. End-date discrepancies are preserved; period_end_date is blank for discrepant headers.",
            "total_policy": "52本部合計 is read from cached Excel values and checked against numeric detail cells using Excel SUM blank-ignored semantics. Blank detail cells remain blank.",
            "subgroup_policy": "COVID-suspected and non-COVID-suspected remain separate source series; their sum is checked against overall values where all three values are numeric.",
        },
        "output": {
            "path": str(OUT_CSV.relative_to(ROOT)), "rows": len(rows),
            "detail_rows": sum(1 for x in rows if x["aggregation_level"] == "fire_department"),
            "aggregate_rows": sum(1 for x in rows if x["aggregation_level"] == "52_fire_department_total"),
            "sha256": sha256(OUT_CSV), "columns": FIELDS,
        },
        "audits": {
            "week_counts_by_sheet": {x["sheet"]: len(weeks_by_sheet[x["sheet"]]) for x in SHEETS},
            "current_vs_previous_year_week_start_delta_days": {
                "min": min(prior_pair_deltas), "max": max(prior_pair_deltas), "unique": sorted(set(prior_pair_deltas)),
            },
            "aligned_subgroup_week_count": len(common_dates),
            "prefecture_cell_provenance": {
                "explicit_cell_rows": sum(1 for x in prefecture_source_counts.elements() if x),
                "merged_range_rows": sum(1 for x in prefecture_source_counts.elements() if not x),
            },
            "52_hq_total_checks": dict(total_checks),
            "subgroup_reconciliation": dict(partition_checks),
            "incomplete_subgroup_triplets": incomplete_locations,
            "week_end_header_discrepancies": end_date_mismatch_weeks,
        },
        "limitations": [
            "The dataset describes the 52 fire departments included in the FDMA survey, not every fire department in Japan.",
            "救急搬送困難事案 is not equivalent to ambulance refusal, non-transport, or inability to receive treatment.",
            "The previous-year tab is paired by week index 364 days apart and retained as a separate comparator series.",
            "The overall sheet has one blank facility-week observation; this is not converted to zero.",
            "One overall-sheet header prints 2024-04-01 through 2024-04-08 although the validated seven-day interval is 2024-04-01 through 2024-04-07. Its raw header is preserved and period_end_date is blank for that interval.",
            "This is a descriptive weekly dataset and does not establish causal effects of COVID-19 on transport difficulty.",
        ],
    }
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    audit = {
        "status": "PASS_WITH_EXPLICIT_SOURCE_ISSUES",
        "created_at_jst": now_jst, "source_sha256": source_hash,
        "normalized_rows": len(rows),
        "week_counts_by_sheet": manifest["audits"]["week_counts_by_sheet"],
        "facility_rows_per_sheet": 52, "facility_identity_and_order_consistent": True,
        "prefecture_cell_provenance": {
            "explicit_cell_rows": sum(1 for x in prefecture_source_counts.elements() if x),
            "merged_range_rows": sum(1 for x in prefecture_source_counts.elements() if not x),
        },
        "previous_year_pairing_days": sorted(set(prior_pair_deltas)),
        "total_checks": dict(total_checks), "subgroup_reconciliation": dict(partition_checks),
        "incomplete_subgroup_triplets": incomplete_locations,
        "week_end_header_discrepancies": end_date_mismatch_weeks,
        "zero_imputation": False, "daily_interpolation": False,
        "historical_derived_csv_used_as_input": False,
    }
    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dictionary = """# FDMA 救急搬送困難事案・週次データ辞書

## 出典・構築
- 発行主体：総務省消防庁
- 公式ページ：https://www.fdma.go.jp/disaster/coronavirus/post-1.html
- 公式Excel：https://www.fdma.go.jp/disaster/coronavirus/items/coronavirus_data.xlsx
- 原本SHA-256：""" + source_hash + """
- 粒度：週次
- 単位：件
- 収録単位：調査対象52消防本部および52本部合計
- 構築：公式Excelの4シートから直接抽出。過去のミラーCSV・加工CSVは入力に不使用。

## 系列
| metric_code | 公式シート | 意味 |
|---|---|---|
| transport_difficulty_overall_current | 搬送困難事案（今回） | 今回の全体系列 |
| transport_difficulty_overall_previous_year | 搬送困難事案（前年同期） | 前年同期比較用の別系列。今回系列と週番号で対応し、開始日は364日差 |
| transport_difficulty_covid_suspected_current | うちコロナ疑い事案（今回） | 今回のうちコロナ疑い事案 |
| transport_difficulty_non_covid_suspected_current | うち非コロナ疑い事案（今回） | 今回のうち非コロナ疑い事案 |

## 主な列
| 列 | 定義 |
|---|---|
| week_index | シート内の週番号。シートごとに1から付番 |
| period_start_date | 見出し開始日。初週の令和年表示を基準にし、全見出しの月日・曜日と照合 |
| period_end_date | 終了日見出しが7日間の期待期間と一致した場合のみ設定。不一致の場合は空欄 |
| period_end_date_expected | 開始日から6日後の期待終了日。検証用であり、印刷見出しの置換ではない |
| period_end_date_printed | Excel見出しに印字された終了日 |
| date_header_status | matched または printed_end_date_or_weekday_mismatch |
| raw_week_header | Excelの週見出し原文 |
| prefecture | 消防本部所在地の都道府県。縦方向に結合されたExcelセルは、結合範囲の先頭セルから値を取得 |
| prefecture_value_source | 都道府県値が明示セルか、原本の縦結合セルから取得されたか |
| fire_department | 消防本部名。合計行は「52本部合計」 |
| aggregation_level | fire_department または 52_fire_department_total |
| value | 件数。原本空欄は空欄のまま、明示的な0は0 |
| observation_status | reported_numeric_value、reported_zero、blank_in_source、cached_excel_total_formula 等 |
| paired_current_week_start_date | 前年同期シートの週番号に対応する今回シートの開始日 |
| source_cell | 原本Excelのセル番地 |
| source_formula | 合計行の原本数式（数式がある場合） |
| source_file_sha256 | 原本ファイルのSHA-256 |

## 解釈上の制約
- 調査対象は52消防本部であり、日本全国の全消防本部の悉皆集計ではない。
- 救急搬送困難事案は受入照会・現場滞在に関する指標であり、搬送拒否・未搬送・治療不能と同義ではない。
- 空欄と0を区別する。補間・ゼロ埋めはしない。
- 全体シートの2022-03-07開始週、秋田市消防本部の値は原本空欄。コロナ疑い・非コロナ疑いシートは両方0。
- 全体シートの2024-04-01開始週の印刷見出しは終了日が2024-04-08と記載されるが、7日間の連続週として期待される終了日は2024-04-07。原文を保持し、period_end_dateは空欄としている。
- COVID疑い・非COVID疑いの分類は消防庁原本の分類であり、患者の確定診断区分と同一と断定しない。
- 週次データを日次に補間しない。時系列上の関連は因果関係を意味しない。
"""
    OUT_DICTIONARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_DICTIONARY.write_text(dictionary, encoding="utf-8")

    print(json.dumps({
        "status": audit["status"], "normalized_rows": len(rows),
        "detail_rows": sum(1 for x in rows if x["aggregation_level"] == "fire_department"),
        "aggregate_rows": sum(1 for x in rows if x["aggregation_level"] == "52_fire_department_total"),
        "week_counts_by_sheet": audit["week_counts_by_sheet"],
        "previous_year_pairing_days": audit["previous_year_pairing_days"],
        "total_checks": audit["total_checks"],
        "subgroup_reconciliation": audit["subgroup_reconciliation"],
        "incomplete_subgroup_triplets": incomplete_locations,
        "week_end_header_discrepancies": end_date_mismatch_weeks,
        "csv_sha256": manifest["output"]["sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

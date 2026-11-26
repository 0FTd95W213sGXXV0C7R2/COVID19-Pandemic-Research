#!/usr/bin/env python3
"""Rebuild the MHLW resource audit from the checked-in original files."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from contextlib import ExitStack, redirect_stdout
from datetime import date, datetime
from io import StringIO, TextIOWrapper
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

import audit_mhlw_gmis_all_snapshots as gmis
import audit_mhlw_weekly_inpatient_survey as weekly
import audit_mhlw_weekly_survey_footnotes_all as old_notes
import build_mhlw_weekly_survey_crosswalk as old_crosswalk

ROOT = weekly.ROOT
AUDIT = ROOT / "data/audits/mhlw"
OUT = AUDIT / "resource_quality_20261126"
META = ROOT / "data/metadata/rebuild_2026/scarce_resource/mhlw_resource_quality"
SERIES = ROOT / "data/processed/rebuild_2026/scarce_resource/mhlw_weekly_prefecture_long.csv"
JST = ZoneInfo("Asia/Tokyo")
UNKNOWN = "不明"
DASHES = {"－", "ー", "-", "―", "–", "—", "−", "‐"}
PREFECTURES = dict(zip(old_crosswalk.PREF_NAMES, range(1, 48)))
NAMES = "|".join(PREFECTURES)
AREA = re.compile(rf"^(?:\d{{1,2}}\s*)?({NAMES}|全国|合計)$")
DATE_TOKEN = r"(?:(?:令和\s*(?P<era>\d+|元)|(?P<year>20\d\d))\s*年\s*)?(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日"
OBS = re.compile(DATE_TOKEN + r"\s*0時(?:時点|現在)?")
PUB = re.compile(DATE_TOKEN + r"\s*公表")
REV = re.compile(DATE_TOKEN + r"\s*(?:[）)]\s*)?(?:付け?\s*)?修正|修正[。\s]*[(（]?\s*" + DATE_TOKEN.replace("?P<", "?P<after_"))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def csv_writer(stack, path, fields):
    handle = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.DictWriter(handle, fields.split(), lineterminator="\n")
    writer.writeheader()
    return writer


def compact(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def row_identity(row):
    for cell in row[:4]:
        match = AREA.fullmatch(unicodedata.normalize("NFKC", str(cell.value or "")).strip())
        if match:
            name = match[1]
            return (name if name in PREFECTURES else "全国"), cell.column
    return None


def date_from(match, anchor, prefix="", forward=False):
    fields = match.groupdict()
    era, year, month, day = (fields.get(prefix + field) for field in ("era", "year", "month", "day"))
    if not month:
        return None
    candidate_year = int(year) if year else (2018 + (1 if era == "元" else int(era))) if era else anchor.year
    try:
        candidate = date(candidate_year, int(month), int(day))
        if not era and not year:
            if forward and candidate < anchor:
                candidate = candidate.replace(year=candidate_year + 1)
            elif not forward and abs((candidate - anchor).days) > 180:
                candidate = candidate.replace(year=candidate_year + (1 if candidate < anchor else -1))
        return candidate
    except ValueError:
        return None


def value_status(cell, formula):
    value = cell.value
    if cell.data_type == "e":
        return "excel_error"
    if value is None or isinstance(value, str) and not value.strip():
        return "formula_cache_missing" if formula else "blank"
    if isinstance(value, str) and value.strip() in DASHES:
        return "dash"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "reported_zero" if value == 0 else "numeric"
    if isinstance(value, str) and re.match(r"注\s*\d+", compact(value)):
        return "annotated_value"
    return "text"


def inventory():
    manifests = {"weekly": read_json(weekly.MANIFEST), "gmis": read_json(gmis.MANIFEST)}
    groups, all_files = defaultdict(list), {}
    metadata = {}
    for series, manifest in manifests.items():
        entries = {x["local_path"]: x for x in manifest["results"] if x["status"] == "downloaded"}
        metadata.update(entries)
        folder = ROOT / "data/raw/mhlw" / ("weekly_inpatient_survey" if series == "weekly" else "gmis_all_snapshots")
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            groups[series, digest].append(rel)
            all_files[rel] = {"series": series, "path": rel, "bytes": len(content), "sha256": digest}
    representatives, duplicates = [], []
    for (series, digest), paths in groups.items():
        canonical = min(paths, key=lambda path: (path not in metadata, path))
        representatives.append((series, canonical))
        for path in paths:
            all_files[path]["canonical_path"] = canonical
            if path != canonical:
                # Confirm literal equality in addition to the hash grouping.
                if (ROOT / path).read_bytes() != (ROOT / canonical).read_bytes():
                    raise ValueError(f"SHA-256 collision: {path}")
                duplicates.append({"series": series, "sha256": digest, "path": path, "canonical_path": canonical})
    return all_files, metadata, sorted(representatives), duplicates


def reproduce_headers():
    # Execute the original extractor without overwriting its historical results.
    saved = old_crosswalk.OUT
    try:
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            old_crosswalk.OUT = Path(directory) / "crosswalk.json"
            old_crosswalk.main()
            return read_json(old_crosswalk.OUT)
    finally:
        old_crosswalk.OUT = saved


def header_parts(sheet, first, col):
    merged = [region for region in sheet.merged_cells.ranges if region.min_row < first]
    result = []
    for row in range(1, first):
        cell = sheet.cell(row, col)
        if cell.value is None:
            region = next((region for region in merged if region.min_row <= row <= region.max_row
                           and region.min_col <= col <= region.max_col), None)
            if region:
                cell = sheet.cell(region.min_row, region.min_col)
        if cell.value is not None and (not result or result[-1][0] != cell.coordinate):
            result.append((cell.coordinate, str(cell.value)))
    return result


def semantic(label, col, modern):
    """Use the leaf for the metric and separately preserve the severity grouping."""
    text = compact(label)
    if modern:
        if col in (9, 10, 11, 12, 13, 14):
            severity = "moderate_II"
        elif col in (15, 16, 17, 18, 19, 20):
            severity = "severe"
        elif col in (3, 4, 5, 6, 7, 8):
            severity = "general"
        else:
            severity = "all_or_not_applicable"
    elif "重症" in text:
        severity = "severe"
    elif "中等症II" in text:
        severity = "moderate_II"
    else:
        severity = "unconfirmed"
    leaf = text.rsplit("/", 1)[-1] if " / " in label else text
    if "フェーズ" in text or "現段階" in text:
        if "計画" in text:
            return ("planned_rooms" if "居室" in text else "planned_immediate_beds", severity)
        return "stage", severity
    if "臨時の医療施設" in text or "入院待機施設" in text:
        return "temporary_facility_" + ("beds" if "施設の病床数" in text else
               "rooms" if "施設の居室数" in text else "patients"), severity
    if "使用率" in leaf:
        if "居室" in leaf:
            return "secured_room_occupancy_rate", severity
        if "定員" in leaf:
            return "secured_capacity_occupancy_rate", severity
        return "secured_bed_occupancy_rate", severity
    for token, concept in (
        ("確保病床外に入院", "outside_secured_inpatients"),
        ("確保病床に入院", "secured_inpatients"),
        ("即応病床数", "immediate_beds"), ("確保病床数", "secured_beds"),
        ("即応居室数", "immediate_rooms"), ("確保居室数", "secured_rooms"),
        ("即応定員数", "immediate_capacity"), ("確保定員数", "secured_capacity"),
        ("入院率", "admission_rate"), ("確認中の人数", "pending_confirmation_patients"),
        ("在院者数", "total_inpatients"), ("入院者数", "total_inpatients"),
        ("重症者数", "total_severe_patients"), ("中等症II患者数", "total_moderate_II_patients"),
    ):
        if token in leaf:
            return concept, severity
    return old_crosswalk.classify(label), severity


def metric_unit(concept):
    if concept.endswith("_rate"):
        return "%"
    if concept.endswith("_beds"):
        return "床"
    if concept.endswith("_rooms"):
        return "室"
    if concept.endswith("_capacity") or "patient" in concept or concept == "positive_cases_excluding_recovered":
        return "人"
    return UNKNOWN


def run():
    started = datetime.now(JST)
    for directory in (OUT, META, SERIES.parent):
        directory.mkdir(parents=True, exist_ok=True)
    files, metadata, representatives, duplicates = inventory()
    previous = read_json(weekly.OUT)
    previous_book = {x["local_path"]: x for x in previous["snapshots"]}
    previous_notes = {x["local_path"]: x for x in read_json(old_notes.OUT)["results"]}
    previous_gmis = {x["local_path"]: x for x in read_json(gmis.OUT)["snapshots"]}
    previous_headers = read_json(old_crosswalk.OUT)
    previous_dash = read_json(AUDIT / "weekly_inpatient_survey_dash_cells.json")
    errors, differences, notes_missing, dates_seen = [], [], [], []
    counts = Counter()
    gmis_crosswalk = {}
    source_details = {}
    signatures = Counter()
    past_signature = {}
    sums = Counter()
    with ExitStack() as stack:
        notes = csv_writer(stack, OUT / "footnotes.csv", "source_path sheet cell kind text flags")
        revisions = csv_writer(stack, OUT / "revisions.csv", "source_path sheet cell observation_date publication_date revision_date text")
        changes = csv_writer(stack, OUT / "definition_changes.csv", "observation_date source_path sheet change_type previous_signature signature evidence")
        quality = csv_writer(stack, OUT / "quality_flags.csv", "source_path sheet cell flag detail")
        totals = csv_writer(stack, OUT / "national_totals.csv", "source_path sheet cell variable_id national numeric_prefectures prefecture_sum result")
        columns_out = csv_writer(stack, META / "column_headers.csv", "variable_id source_path sheet observation_date schema_id column header_path header_cells")
        crosswalk = csv_writer(stack, META / "variable_crosswalk.csv", "variable_id source_system valid_from valid_to concept severity unit population definition evidence numerator denominator status")
        series = csv_writer(stack, SERIES, "observation_date prefecture_code prefecture variable_id cell raw_value numeric_value value_status number_format")
        binary = stack.enter_context((OUT / "excel_cells.jsonl.gz").open("wb"))
        compressed = stack.enter_context(gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0))
        cells = stack.enter_context(TextIOWrapper(compressed, encoding="utf-8"))
        for system, path in sorted(representatives, key=lambda x: (x[0], metadata.get(x[1], {}).get("snapshot_date") or "", x[1])):
            item = metadata.get(path)
            try:
                if not item:
                    raise ValueError("取得台帳に対応する行がありません")
                if system == "gmis":
                    current = gmis.inspect(item)
                    old = previous_gmis.get(path, {})
                    compare(current, old, path, differences)
                    if current["status"] != "audited":
                        raise ValueError(current["status"])
                    counts["gmis_audited"] += 1
                    if current["blank_facility_codes"]:
                        quality.writerow(flag(path, "", "", "gmis_facility_code_missing", str(current["blank_facility_codes"])))
                    if current["observation_date_mismatches"]:
                        quality.writerow(flag(path, "", "", "facility_observation_date_differs", json.dumps(current["observation_date_mismatches"], ensure_ascii=False)))
                    for status, amount in current["report_status_counts"].items():
                        if status != "報告済み":
                            quality.writerow(flag(path, "", "", "gmis_reporting_status", f"{status}: {amount}"))
                    enc, rows = gmis.decode_csv((ROOT / path).read_bytes())
                    start = current["header_line_1based"] - 1
                    glossary = [" ".join(cell for cell in row if cell.strip()) for row in rows[:start]]
                    for line, text in enumerate(glossary, 1):
                        if text:
                            notes.writerow(dict(source_path=path, sheet="", cell=line, kind="csv_preamble", text=text, flags=""))
                    gmis_crosswalk[path] = dict(header=current["header"], glossary=glossary, date=item["snapshot_date"])
                    source_details[path] = dict(observation_date=item["snapshot_date"], date_evidence="取得台帳の実績日。個票差は品質フラグ参照")
                    continue
                current = weekly.inspect(item)
                old = previous_book.get(path, {})
                sid = hashlib.sha256(current.get("schema_signature", "UNRECOGNIZED").encode()).hexdigest()[:10]
                signatures[sid] += 1
                compare(current, old, path, differences, exclude={"schema_signature", "header_labels_by_column", "sheet_names"})
                if sid != old.get("schema_id"):
                    differences.append([path, "schema_id"])
                with ExitStack() as workbooks:
                    raw = load_workbook(ROOT / path, data_only=False)
                    workbooks.callback(raw.close)
                    values = load_workbook(ROOT / path, data_only=True)
                    workbooks.callback(values.close)
                    process_workbook(path, item, raw, values, sid, cells, notes, revisions, changes,
                                     quality, totals, columns_out, crosswalk, series, counts, sums,
                                     past_signature, source_details, previous_notes.get(path, {}),
                                     notes_missing, dates_seen)
                counts["excel_audited"] += 1
            except Exception as exc:
                errors.append({"path": path, "error": repr(exc)})
                quality.writerow(flag(path, "", "", "processing_error", repr(exc)))
        for path, record in gmis_crosswalk.items():
            for col, label in enumerate(record["header"], 1):
                identifier = f"{files[path]['sha256']}:CSV:{col}"
                columns_out.writerow(dict(variable_id=identifier, source_path=path, sheet="CSV",
                    observation_date=record["date"], schema_id="gmis", column=col,
                    header_path=label, header_cells=""))
                evidence = [line for line in record["glossary"] if re.search(r"^\s*[・･]?" + re.escape(label) + r"\s*[：:]", line)]
                concept = {"確保病床数": "secured_beds", "即応病床数": "immediate_beds", "即応病床": "immediate_beds",
                           "入院中患者数": "total_inpatients", "入院中": "total_inpatients"}.get(label, "unconfirmed")
                crosswalk.writerow(dict(variable_id=identifier, source_system="gmis", valid_from=record["date"],
                    valid_to=record["date"], concept=concept, severity=UNKNOWN, unit=metric_unit(concept),
                    population="病床確保計画に位置づけられた医療機関の公表対象施設",
                    definition=" ".join(evidence) or UNKNOWN, evidence="CSV前文" if evidence else UNKNOWN,
                    numerator="対象外", denominator="対象外", status="施設別・週次調査への接続保留"))
    write_inventory(files, metadata, source_details, duplicates)
    fresh = reproduce_headers()
    tests = validate(files, metadata, counts, signatures, sums, errors, differences, notes_missing,
                     dates_seen, previous, previous_headers, previous_dash, fresh)
    result = dict(started_at_jst=started.isoformat(timespec="seconds"),
                  finished_at_jst=datetime.now(JST).isoformat(timespec="seconds"),
                  counts=dict(counts), schemas=dict(signatures), national_checks=dict(sums),
                  header_signatures=fresh["summary"]["candidate_header_signatures"],
                  errors=errors, historical_differences=differences, historical_notes_missing=notes_missing, tests=tests)
    write_json(OUT / "validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return all(tests.values())


def flag(path, sheet, cell, kind, detail):
    return dict(source_path=path, sheet=sheet, cell=cell, flag=kind, detail=detail)


def compare(current, old, path, differences, exclude=()):
    for key in sorted((current.keys() & old.keys()) - set(exclude)):
        if current[key] != old[key]:
            differences.append([path, key])


def note_flags(text):
    patterns = {
        "regional_definition": r"国基準|都[の独自]*基準|独自基準|定義が異|北海道について",
        "incompatible_occupancy": r"単純に比較できない|使用率は空欄",
        "reporting_zero": r"把握が困難.{0,12}0|把握が困難.{0,12}ゼロ",
        "possible_estimate": r"推計|推定|直近1週間の新規陽性者数",
        "dash_note": r"「-」|「ー」|「―」|ハイフン",
        "nonreporting": r"未報告|未回答|未把握",
        "transition_policy": r"経過措置|移行期間|柔軟な運用",
    }
    normalized = unicodedata.normalize("NFKC", text)
    return [key for key, pattern in patterns.items() if re.search(pattern, normalized)]


def process_workbook(path, item, raw, values, schema, cells, notes, revisions, changes,
                     quality, totals, columns_out, crosswalk, series, counts, sums,
                     past_signature, source_details, previous_notes, notes_missing, dates_seen):
    anchor = date.fromisoformat(item["snapshot_date"])
    title_dates, publication_dates = {}, {}
    for sheet in raw.worksheets:
        for row in sheet.iter_rows(min_row=1, max_row=min(3, sheet.max_row)):
            for cell in row:
                text = unicodedata.normalize("NFKC", str(cell.value or ""))
                for pattern, found in ((OBS, title_dates), (PUB, publication_dates)):
                    match = pattern.search(text)
                    if match:
                        parsed = date_from(match, anchor)
                        if parsed:
                            found[parsed] = f"{sheet.title}!{cell.coordinate}"
    observation = next(iter(title_dates)) if len(title_dates) == 1 else None
    publication = next(iter(publication_dates)) if len(publication_dates) == 1 else None
    source_details[path] = dict(observation_date=observation or UNKNOWN, publication_date=publication or UNKNOWN,
        date_evidence=title_dates.get(observation, UNKNOWN),
        publication_evidence=publication_dates.get(publication, UNKNOWN), revision_dates=set())
    if observation != anchor:
        quality.writerow(flag(path, "", title_dates.get(observation, ""), "observation_date_differs_or_unknown",
                              f"台帳={anchor}; Excel={observation or UNKNOWN}"))
        counts["date_discrepancies"] += 1

    for index, sheet in enumerate(raw.worksheets, 1):
        counts["sheets"] += 1
        cached = values[sheet.title]
        rows = {}
        for row in sheet.iter_rows():
            identity = row_identity(row)
            if identity:
                rows.setdefault(identity[0], []).append((row[0].row, identity[1]))
        prefecture_rows = {name: positions[0][0] for name, positions in rows.items()
                           if name in PREFECTURES and len(positions) == 1}
        has_table = set(prefecture_rows) == set(PREFECTURES)
        if index == 1 and not has_table:
            quality.writerow(flag(path, sheet.title, "", "prefecture_coverage_incomplete", str(len(prefecture_rows))))
        first = min(prefecture_rows.values(), default=sheet.max_row + 1)
        last = max((r for positions in rows.values() for r, _ in positions), default=0)
        national_rows = rows.get("全国", [])
        national_row = national_rows[0][0] if len(national_rows) == 1 else None
        archive = dict(source_path=path, sheet=sheet.title, sheet_state=sheet.sheet_state, dimensions=sheet.calculate_dimension(),
                       merges=sorted(str(region) for region in sheet.merged_cells.ranges), cells=[])
        definitions, historical, labels = {}, set(), {}
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None and cell.comment is None:
                    continue
                cache = cached[cell.coordinate]
                entry = dict(cell=cell.coordinate, value=cell.value, data_type=cell.data_type, number_format=cell.number_format)
                if cell.data_type == "f":
                    entry["cached"] = cache.value
                if cell.comment:
                    entry["comment"] = cell.comment.text
                archive["cells"].append(entry)
                candidates = []
                if cell.comment:
                    candidates.append(("comment", cell.comment.text))
                    historical.add(("comment", old_notes.norm(cell.comment.text)))
                if isinstance(cell.value, str) and cell.data_type != "f":
                    historical_text = old_notes.norm(cell.value)
                    if old_notes.PATTERN.search(historical_text) or cell.row >= max(1, sheet.max_row - 18):
                        historical.add(("cell_text", historical_text))
                    if cell.row > last or old_notes.PATTERN.search(historical_text):
                        candidates.append(("cell_text", cell.value))
                    normalized = unicodedata.normalize("NFKC", cell.value)
                    match = re.match(r"\s*注\s*(\d+)\s*:", normalized)
                    if match:
                        definitions[int(match[1])] = (cell.coordinate, cell.value)
                for kind, text in candidates:
                    tags = note_flags(text)
                    notes.writerow(dict(source_path=path, sheet=sheet.title, cell=cell.coordinate,
                                        kind=kind, text=text, flags="|".join(tags)))
                    counts["footnote_occurrences"] += 1
                    for tag in tags:
                        quality.writerow(flag(path, sheet.title, cell.coordinate, tag, text))
                    if "修正" in text:
                        matches = list(REV.finditer(unicodedata.normalize("NFKC", text)))
                        revision_days = {date_from(m, publication or observation or anchor,
                                                    "" if m["month"] else "after_", True) for m in matches}
                        revision_days.discard(None)
                        source_details[path]["revision_dates"].update(revision_days)
                        for day in sorted(revision_days) or [UNKNOWN]:
                            revisions.writerow(dict(source_path=path, sheet=sheet.title, cell=cell.coordinate,
                                observation_date=observation or UNKNOWN, publication_date=publication or UNKNOWN,
                                revision_date=day, text=text))
                            counts["revision_records"] += 1
        cells.write(json.dumps(archive, ensure_ascii=False, default=str, separators=(",", ":")) + "\n")
        for previous_sheet in previous_notes.get("sheets", []):
            if previous_sheet["sheet"] == sheet.title:
                prior = {(n["kind"], n["text"]) for n in previous_sheet["notes"]}
                notes_missing.extend((path, sheet.title, kind, text) for kind, text in sorted(prior - historical))
        if not has_table:
            continue
        dates_seen.append((str(observation or ""), sheet.title))
        for col in range(1, sheet.max_column + 1):
            parts = [(coord, text) for coord, text in header_parts(cached, first, col)
                     if not OBS.search(unicodedata.normalize("NFKC", text))
                     and not PUB.search(unicodedata.normalize("NFKC", text))
                     and not re.search(r"調査結果|新型コロナウイルス感染症患者", text)]
            if not parts and not any(cached.cell(row, col).value is not None for row in prefecture_rows.values()):
                continue
            if any(col == positions[0][1] for name, positions in rows.items() if name in PREFECTURES):
                continue
            if col <= 2 and not parts and all(cached.cell(row, col).value in (None, PREFECTURES[name])
                                             for name, row in prefecture_rows.items()):
                continue
            label = " / ".join(text for _, text in parts)
            # The late layout has repeated capacity leaf labels without a severity token.
            modern = ("中等症II" in compact(cached["I4"].value) and "重症者" in compact(cached["O4"].value)
                      and all("即応病床数" in compact(cached.cell(7, index).value) for index in (6, 12, 18)))
            concept, severity = semantic(label, col, modern)
            if (col in (11, 12, 13, 14) and "重症者数" in compact(cached["J5"].value)
                    and "病床数" == compact(cached["K5"].value)
                    and "入院確定者数を含む" in compact(cached["E3"].value)):
                severity = "severe"
            leaf = parts[-1][1] if parts else ""
            references = set()
            for refs in re.findall(r"注\s*(\d+(?:\s*[,、､]\s*\d+)*)", unicodedata.normalize("NFKC", leaf)):
                references.update(int(number) for number in re.findall(r"\d+", refs))
            evidence = [definitions[n] for n in sorted(references & definitions.keys())]
            # Early admission scope is explicit in the header itself.
            explicit = "入院確定者数を含む" in compact(leaf)
            definition = "\n".join(text for _, text in evidence) or (leaf if explicit else UNKNOWN)
            identifier = f"{item['snapshot_date']}:{index}:{get_column_letter(col)}"
            labels[col] = dict(identifier=identifier, concept=concept, severity=severity, definition=definition,
                               evidence=evidence, parts=parts, leaf=leaf, explicit=explicit)
        definition_signature = hashlib.sha256(json.dumps(
            [(col, compact(spec["leaf"]), compact(spec["definition"])) for col, spec in labels.items()],
            ensure_ascii=False).encode()).hexdigest()[:12]
        prior = past_signature.get(index)
        if prior != (schema, definition_signature):
            changes.writerow(dict(observation_date=observation or UNKNOWN, source_path=path, sheet=sheet.title,
                change_type="initial" if prior is None else ("schema_change" if prior[0] != schema else "header_or_referenced_note_change"),
                previous_signature=prior[1] if prior else "", signature=definition_signature,
                evidence="列見出しと参照注記の変更候補。意味の同一性は個別確認"))
            counts["change_events"] += 1
        past_signature[index] = (schema, definition_signature)

        for col, spec in labels.items():
            identifier, concept, severity = (spec[key] for key in ("identifier", "concept", "severity"))
            definition = spec["definition"]
            headers = " / ".join(text for _, text in spec["parts"])
            unit = metric_unit(concept)
            numerator = denominator = UNKNOWN if concept.endswith("_rate") else "対象外"
            populations = {"general": "一般区分", "moderate_II": "中等症Ⅱ区分", "severe": "重症区分"}
            population = populations.get(severity, UNKNOWN)
            if spec["explicit"]:
                population = "入院中及び入院確定者"
            if concept == "secured_bed_occupancy_rate" and "当該病床に入院している者" in compact(definition):
                denominator = select_variable(labels, "secured_beds", severity, col)
                numerator = select_variable(labels, "secured_inpatients", severity, col)
            if concept == "admission_rate" and "療養者数に対する入院者数" in compact(definition):
                numerator = select_variable(labels, "total_inpatients", None, col)
                denominator = select_variable(labels, "total_patients_in_care", None, col)
            if concept == "secured_room_occupancy_rate" and "確保居室数に対する宿泊療養者数" in compact(definition):
                numerator = select_variable(labels, "hotel_accommodation_patients", None, col)
                denominator = select_variable(labels, "secured_rooms", None, col)
            if concept == "secured_capacity_occupancy_rate" and "確保定員数に対する" in compact(definition):
                numerator = select_variable(labels, "temporary_facility_patients", None, col)
                denominator = select_variable(labels, "secured_capacity", None, col)
            columns_out.writerow(dict(variable_id=identifier, source_path=path, sheet=sheet.title,
                observation_date=observation or UNKNOWN, schema_id=schema, column=col, header_path=headers,
                header_cells="|".join(coord for coord, _ in spec["parts"])))
            crosswalk.writerow(dict(variable_id=identifier, source_system="weekly",
                valid_from=observation or UNKNOWN, valid_to=observation or UNKNOWN, concept=concept,
                severity=severity, unit=unit, population=population, definition=definition,
                evidence="|".join(coord for coord, _ in spec["evidence"]) or (spec["parts"][-1][0] if spec["explicit"] else UNKNOWN),
                numerator=numerator, denominator=denominator,
                status="未確定・時点間接続保留" if definition == UNKNOWN else "原表記録済・時点間接続保留"))
            if definition == UNKNOWN:
                counts["undefined_weekly_columns"] += 1
            definition_tags = note_flags(definition)
            reported = []
            for name, row in prefecture_rows.items():
                cell = cached.cell(row, col)
                status = value_status(cell, sheet.cell(row, col).data_type == "f")
                reported.append(cell.value if status in ("numeric", "reported_zero") else None)
                counts[status] += 1
                counts["time_series_rows"] += 1
                series.writerow(dict(observation_date=observation or UNKNOWN, prefecture_code=f"{PREFECTURES[name]:02d}",
                    prefecture=name, variable_id=identifier, cell=cell.coordinate, raw_value=cell.value,
                    numeric_value=reported[-1], value_status=status, number_format=cell.number_format))
                if status not in ("numeric", "text"):
                    quality.writerow(flag(path, sheet.title, cell.coordinate, status, identifier))
                if status == "annotated_value":
                    reference = re.match(r"\s*注\s*(\d+)", unicodedata.normalize("NFKC", cell.value))
                    linked = definitions.get(int(reference[1])) if reference else None
                    if linked:
                        for tag in note_flags(linked[1]):
                            quality.writerow(flag(path, sheet.title, cell.coordinate, tag, f"参照注記 {linked[0]}"))
                for note_tag in definition_tags:
                    if note_tag == "possible_estimate" or note_tag == "reporting_zero" and status == "reported_zero":
                        tag = "estimate_possible" if note_tag == "possible_estimate" else "reporting_zero_possible"
                        quality.writerow(flag(path, sheet.title, cell.coordinate, tag, identifier))
            if national_row and unit in ("床", "人", "室") and concept != "unclassified":
                national = cached.cell(national_row, col)
                numbers = [v for v in reported if v is not None]
                if len(numbers) != 47 or value_status(national, False) not in ("numeric", "reported_zero"):
                    result = "national_zero_incomplete" if national.value == 0 and len(numbers) < 47 else "incomplete"
                else:
                    result = "match" if sum(numbers) == national.value else "mismatch"
                sums[result] += 1
                totals.writerow(dict(source_path=path, sheet=sheet.title, cell=national.coordinate,
                    variable_id=identifier, national=national.value, numeric_prefectures=len(numbers),
                    prefecture_sum=sum(numbers) if len(numbers) == 47 else None, result=result))
                if result != "match":
                    quality.writerow(flag(path, sheet.title, national.coordinate, result, identifier))


def select_variable(labels, concept, severity, rate_col):
    matches = [spec["identifier"] for col, spec in labels.items()
               if col != rate_col and spec["concept"] == concept and (severity is None or severity == spec["severity"])]
    return matches[0] if len(matches) == 1 else UNKNOWN


def write_inventory(files, metadata, details, duplicates):
    with ExitStack() as stack:
        manifest = csv_writer(stack, META / "raw_manifest.csv",
            "series path bytes sha256 canonical_path title publisher source_url observation_date listed_date "
            "publication_date revision_dates acquired_from date_evidence publication_evidence provenance")
        dup = csv_writer(stack, META / "duplicate_files.csv", "series sha256 path canonical_path")
        dup.writerows(duplicates)
        for path, record in sorted(files.items()):
            canonical = record["canonical_path"]
            item = metadata.get(path) or metadata.get(canonical, {})
            detail = details.get(canonical, {})
            revision_dates = "|".join(str(value) for value in sorted(detail.get("revision_dates", ())))
            series = record["series"]
            manifest.writerow(dict(**record, title=("新型コロナウイルス感染症患者の療養状況等及び入院患者受入病床数等に関する調査結果"
                if series == "weekly" else "G-MIS 医療機関別病床使用状況"), publisher="厚生労働省",
                source_url=item.get("source_url", UNKNOWN), observation_date=detail.get("observation_date", UNKNOWN),
                listed_date=item.get("snapshot_date", UNKNOWN), publication_date=detail.get("publication_date", UNKNOWN),
                revision_dates=revision_dates or UNKNOWN,
                acquired_from=item.get("source_page") or "|".join(item.get("source_pages", ())) or UNKNOWN,
                date_evidence=detail.get("date_evidence", UNKNOWN), publication_evidence=detail.get("publication_evidence", UNKNOWN),
                provenance="取得台帳" if path in metadata else "同一バイトの取得台帳行を参照"))


def validate(files, metadata, counts, schemas, sums, errors, differences, notes_missing, dates_seen,
             previous, previous_headers, previous_dash, fresh):
    statuses_valid = True
    source_values_valid, pdf_valid = validate_source_values()
    seen = set()
    row_count = 0
    with (META / "variable_crosswalk.csv").open(encoding="utf-8", newline="") as handle:
        ids = {row["variable_id"] for row in csv.DictReader(handle)}
    with SERIES.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row_count += 1
            key = (row["prefecture_code"], row["variable_id"])
            status, raw, numeric = (row[x] for x in ("value_status", "raw_value", "numeric_value"))
            statuses_valid &= key not in seen and row["variable_id"] in ids
            if status in ("numeric", "reported_zero"):
                statuses_valid &= raw == numeric and (float(numeric) == 0) == (status == "reported_zero")
            else:
                statuses_valid &= numeric == "" and (status != "dash" or raw.strip() in DASHES)
            seen.add(key)
    revisions = csv_rows(OUT / "revisions.csv")
    revisions_valid = {"2021-01-07", "2021-01-19", "2023-09-06"} <= {r["revision_date"] for r in revisions}
    return {
        "reproduces_known_revision_dates": revisions_valid,
        "title_date_used_for_february_2024": ("2024-02-07", "公表資料") in dates_seen
            and ("2024-02-02", "公表資料") not in dates_seen,
        "raw_counts": Counter(x["series"] for x in files.values()) == {"weekly": 513, "gmis": 43},
        "canonical_counts": Counter(x["series"] for path, x in files.items() if path == x["canonical_path"]) == {"weekly": 171, "gmis": 43},
        "acquisition_hash_and_size": set(metadata) <= files.keys() and all(
            files[path]["sha256"] == item["sha256"] and files[path]["bytes"] == item["bytes"] for path, item in metadata.items()),
        "no_processing_errors": not errors and counts["excel_audited"] == 171 and counts["gmis_audited"] == 43,
        "historical_structure_and_gmis": not differences and len(schemas) == previous["schema_variant_count"] == 9,
        "historical_header_signatures_and_profiles": fresh["candidate_variables"] == previous_headers["candidate_variables"]
            and fresh["summary"]["candidate_header_signatures"] == 100,
        "historical_dash_cells": fresh["dash_cells"] == previous_headers["dash_cells"]
            and len(fresh["dash_cells"]) == previous_dash["summary"]["dash_cell_count"] == 15098,
        "historical_note_texts": not notes_missing,
        "complete_dated_prefecture_tables": len(dates_seen) == len(set(dates_seen)) == 171
            and all(day for day, _ in dates_seen),
        "csv_integrity_and_no_imputation": statuses_valid and row_count == counts["time_series_rows"] and row_count > 0,
        "csv_cells_match_original_cached_values": source_values_valid,
        "final_snapshot_matches_pdf_transcription": pdf_valid,
        "raw_files_unchanged": all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == item["sha256"]
                                   for path, item in files.items()),
        "additive_checks_executed": sums["match"] > 0 and sums["national_zero_incomplete"] > 0,
    }


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_source_values():
    # Independently reopen original sheets in streaming mode and compare every exported cell.
    variables = {row["variable_id"]: row for row in csv_rows(META / "column_headers.csv")}
    records = defaultdict(list)
    pdf_values = defaultdict(dict)
    for row in csv_rows(SERIES):
        variable = variables[row["variable_id"]]
        records[variable["source_path"], variable["sheet"]].append(row)
        if row["observation_date"] == "2024-03-27":
            value = row["raw_value"]
            if row["number_format"] == '0"%"' and row["value_status"] in ("reported_zero", "numeric"):
                value += "%"
            pdf_values[row["prefecture_code"]][int(variable["column"])] = value
    source_matches = bool(records)
    for (path, sheet), rows in records.items():
        workbook = load_workbook(ROOT / path, read_only=True, data_only=True)
        try:
            cached = {cell.coordinate: (str(cell.value), cell.number_format)
                      for line in workbook[sheet].iter_rows() for cell in line if cell.value is not None}
            for row in rows:
                if row["cell"] not in cached:
                    source_matches &= row["raw_value"] == ""
                else:
                    source_matches &= cached[row["cell"]] == (row["raw_value"], row["number_format"])
        finally:
            workbook.close()
    pdf = csv_rows(SERIES.parent / "mhlw_hospital_status_20240327_pdf_transcription.csv")
    pdf_matches = len(pdf) == len(pdf_values) == 47 and all(
        all(pdf_values[row["prefecture_code"]].get(col) == value for col, value in enumerate(list(row.values())[2:], 2))
        for row in pdf)
    return source_matches, pdf_matches


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)

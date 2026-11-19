#!/usr/bin/env python3
"""Create a compact review file from the full weekly survey crosswalk candidate output."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/audits/mhlw/weekly_inpatient_survey_variable_crosswalk_candidates.json"
OUT = ROOT / "data/audits/mhlw/weekly_inpatient_survey_crosswalk_review_summary.json"
RATE_CONCEPTS = {"secured_bed_occupancy_rate", "severe_specific_secured_bed_occupancy_rate", "room_occupancy_rate", "inpatient_rate"}

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    variables = data.get("candidate_variables", [])
    selected = []
    for item in variables:
        concept = item.get("candidate_concept")
        record = {
            "candidate_concept": concept,
            "exact_header_label": item.get("exact_header_label"),
            "date_count": item.get("date_count"),
            "first_date": item.get("first_date"),
            "last_date": item.get("last_date"),
            "schema_ids": item.get("schema_ids"),
            "numeric_min": item.get("numeric_min"),
            "numeric_max": item.get("numeric_max"),
            "dash_count": item.get("dash_count"),
            "blank_count": item.get("blank_count")
        }
        if concept in RATE_CONCEPTS:
            record["date_profiles"] = item.get("date_profiles", [])
        selected.append(record)
    snapshots = data.get("snapshots", [])
    transitions = []
    previous = None
    for item in snapshots:
        if item.get("schema_id") != previous:
            transitions.append({"date": item.get("snapshot_date"), "schema_id": item.get("schema_id")})
            previous = item.get("schema_id")
    out = {
        "created_at_jst": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        "source": str(SOURCE.relative_to(ROOT)),
        "summary": data.get("summary"),
        "schema_groups": data.get("schema_groups"),
        "contiguous_schema_periods": transitions,
        "candidate_concepts": sorted({x.get("candidate_concept") for x in variables}),
        "variables": selected,
        "unclassified": [
            {"exact_header_label": x.get("exact_header_label"), "date_count": x.get("date_count"),
             "first_date": x.get("first_date"), "last_date": x.get("last_date")}
            for x in variables if x.get("candidate_concept") == "unclassified"
        ],
        "limitations": [
            "This is a compact review aid, not an approved analytical crosswalk.",
            "Candidate concepts are rule-based and require definition/footnote confirmation.",
            "No missing-value conversion, rate recalculation, aggregation, or analytical dataset update was performed."
        ]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created_at_jst": out["created_at_jst"], "summary": out["summary"],
                      "contiguous_schema_periods": out["contiguous_schema_periods"],
                      "candidate_concept_count": len(out["candidate_concepts"]),
                      "unclassified_label_count": len(out["unclassified"])}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

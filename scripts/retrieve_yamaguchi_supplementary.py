#!/usr/bin/env python3
"""Retrieve one article's supplementary archive from the official Europe PMC REST API.

This first bounded run targets Yamaguchi et al. (2022), PMCID PMC9058318.
No author/provider contact is performed. The script never infers values from figures.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

PMCID = "PMC9058318"
ENDPOINT = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/supplementaryFiles"
ROOT = Path("data/raw/non_covid_access/supplementary/yamaguchi_2022")
MANIFEST = Path("data/metadata/non_covid_access/yamaguchi_supplementary_retrieval.json")
EXPECTED = {f"bmjopen-2021-060390supp{i:03d}.pdf" for i in range(1, 11)}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_manifest(payload: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().isoformat()
    record = {
        "study_id": "YAMAGUCHI_2022",
        "pmcid": PMCID,
        "endpoint": ENDPOINT,
        "retrieval_method": "Europe PMC official REST supplementaryFiles endpoint",
        "retrieved_at": now,
        "status": "started",
        "policy": "Public-source retrieval only; no researcher/provider contact; no figure digitization.",
    }
    try:
        response = requests.get(
            ENDPOINT,
            headers={"User-Agent": "COVID19-Pandemic-Research supplementary audit/1.0"},
            timeout=(15, 90),
        )
        record["http_status"] = response.status_code
        record["final_url"] = response.url
        record["content_type"] = response.headers.get("Content-Type")
        response.raise_for_status()
        body = response.content
        if not body:
            raise ValueError("Europe PMC returned an empty response")
        if not zipfile.is_zipfile(__import__("io").BytesIO(body)):
            preview = body[:500].decode("utf-8", errors="replace")
            raise ValueError(f"Response is not a ZIP archive; first 500 chars: {preview}")
        archive_path = ROOT / f"{PMCID}_supplementary.zip"
        archive_path.write_bytes(body)
        record["archive"] = {
            "path": str(archive_path),
            "bytes": len(body),
            "sha256": sha256(body),
        }
        extracted = []
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Reject absolute paths, parent traversal, and unexpected nested paths.
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"Unsafe archive member path: {info.filename}")
                base = Path(name).name
                if not base:
                    continue
                data = zf.read(info)
                target = ROOT / base
                target.write_bytes(data)
                extracted.append({
                    "archive_member": info.filename,
                    "filename": base,
                    "path": str(target),
                    "bytes": len(data),
                    "sha256": sha256(data),
                    "is_expected_filename": base in EXPECTED,
                })
        found = {item["filename"] for item in extracted}
        record["files"] = extracted
        record["expected_filenames"] = sorted(EXPECTED)
        record["missing_expected_filenames"] = sorted(EXPECTED - found)
        record["unexpected_filenames"] = sorted(found - EXPECTED)
        record["status"] = "retrieved_archive_and_extracted_files"
        record["content_audit_status"] = "not_started"
        record["note"] = (
            "Archive and member hashes are recorded. PDF contents have not yet been interpreted; "
            "no values have been added to the 47-row evidence table."
        )
        write_manifest(record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        record["status"] = "retrieval_failed"
        record["error_type"] = type(exc).__name__
        record["error"] = str(exc)
        record["content_audit_status"] = "not_started"
        record["note"] = "No supplementary content was accepted or transcribed."
        write_manifest(record)
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0  # A documented retrieval failure is an auditable result, not a workflow crash.


if __name__ == "__main__":
    sys.exit(main())

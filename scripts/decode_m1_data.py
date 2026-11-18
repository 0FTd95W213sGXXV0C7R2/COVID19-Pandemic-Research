#!/usr/bin/env python3
"""Decode the base64-wrapped gzip CSV datasets in data/derived/."""
from pathlib import Path
import base64
import gzip

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"

FILES = {
    "national_severe_cases_daily_20200509_20230508.csv.gz.b64":
        "national_severe_cases_daily_20200509_20230508.csv",
    "national_deaths_daily_20200509_20230508.csv.gz.b64":
        "national_deaths_daily_20200509_20230508.csv",
}

def main():
    for encoded_name, output_name in FILES.items():
        encoded_path = DATA / encoded_name
        output_path = DATA / output_name
        compressed = base64.b64decode(encoded_path.read_text(encoding="ascii"))
        output_path.write_bytes(gzip.decompress(compressed))
        print(f"Decoded: {output_path.relative_to(ROOT)}")

if __name__ == "__main__":
    main()

# National cancer QA stage 1

Date JST: 2026-11-27 (exact time not captured).

Reaggregated existing verified comparison CSVs using pandas, not independent extraction from original workbooks.

| Measure | MATCH | DIFFERENT | NONNUMERIC_HELD |
|---|---:|---:|---:|
| incidence_count | 17400 | 0 | 0 |
| incidence_rate | 7603 | 5298 | 931 |
| incidence_asr | 193 | 1158 | 98 |

Rate recalculation: 585140 MATCH, 40817 HELD. All held rows have missing published_rate and nonmissing numerator and denominator. No imputation. Cause of rate differences unresolved.

Annual candidates: 5891 rows; numeric 5324, unresolved dash 567. Counts by measure (numeric/held): incidence_count 1372/0; incidence_rate 1183/189; incidence_asr 2625/378; mortality_count 16/0; mortality_rate 16/0; mortality_asr75 112/0. Keep PENDING_QA.

Source: https://drive.google.com/drive/folders/1HKGAXwAfD-JaXMtRy2FG7eMqYyP94YZo ; national_prefecture_comparison.csv.gz, rate_recalculation_audit.csv.gz, national_annual_candidates.csv, summary.json, schema.json, known_limitations.json. Integrity record: data/audits/non_covid_access/cancer/ncc_manifest_verification.json.

Incidence coverage 2017–2023, mortality 2017–2024. Two national mortality workbooks reading held. No new acquisition or public dataset upload. Next: examine rate denominators and standard populations; verify source cell coordinates independently; HBCR original comparison.

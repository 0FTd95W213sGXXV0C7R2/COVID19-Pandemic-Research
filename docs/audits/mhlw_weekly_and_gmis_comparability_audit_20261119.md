# MHLW G-MIS and weekly inpatient survey acquisition audit — 2026-11-19

Audit timestamp: 2026-11-19T15:13:55 JST

## Scope and decision

Two separate official Ministry of Health, Labour and Welfare (MHLW) datasets were acquired and structurally audited. They must not be merged or treated as one continuous series without a documented variable/definition crosswalk.

**Preliminary source priority:** use the prefecture-level weekly hospitalization survey as the primary candidate for nationwide temporal analysis of hospital burden; use G-MIS facility-level snapshots as a supplementary source for facility-level capacity/reporting checks. Neither source has been added to the final analysis dataset or MASTER.

## 1. MHLW weekly hospitalization survey

Official page:
- https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html

Acquisition:
- 171 Excel workbooks discovered and downloaded successfully (171/171; each workbook opened with openpyxl).
- Snapshot range: 2020-12-23 through 2024-03-27.
- 47 prefecture rows were identified in every workbook; no prefecture was missing in the structural audit.
- The workbooks do not contain a national-total row; a national series would require a separately documented aggregation of prefecture values.
- Snapshot intervals: 168 intervals of 7 days, one 2-day interval (2024-01-31 to 2024-02-02), and one 12-day interval (2024-02-02 to 2024-02-14).
- Nine header/schema variants were detected. Some variants are minor formatting/header differences, while others represent substantive changes in measured categories.

Important schema eras:
- Early files (2020-12-23 onward): PCR-positive people excluding discharged cases, inpatients, secured beds/bed use, severe patients, accommodation, home care, etc.
- 2021-06-02: schema changed to fields including total people receiving care, inpatients, inpatients in secured beds, severe patients, accommodation/home care, and people awaiting placement.
- 2021-12-22: additional categories for temporary medical facilities/waiting facilities and care-placement adjustment.
- 2023-05-10: schema changed around the transition to the Class 5 framework; inpatients are distinguished from those in secured beds and those outside secured beds.
- 2023-10-04: schema changed again, with moderate II and severe patient categories and corresponding secured-bed/outside-secured-bed distinctions.

Data handling cautions:
- Do not equate fields with similar names across schema eras until the footnotes and survey definitions have been crosswalked.
- Values shown as "－" in later workbooks are nonnumeric source marks. They have not been recoded as zero; their exact meaning must be checked against the workbook notes.
- No imputation, occupancy-rate calculation, national aggregation, or longitudinal concatenation has been performed.

Files:
- Original workbooks: `data/raw/mhlw/weekly_inpatient_survey/`
- Acquisition manifest (URLs, dates, hashes, workbook dimensions/previews): `data/metadata/mhlw/weekly_inpatient_survey_manifest.json`
- Structural/schema audit: `data/audits/mhlw/weekly_inpatient_survey_audit.json`
- Acquisition script: `scripts/acquire_mhlw_weekly_inpatient_survey.py`
- Audit script: `scripts/audit_mhlw_weekly_inpatient_survey.py`
- Acquisition workflow: `.github/workflows/mhlw-weekly-inpatient-survey.yml`
- Audit workflow: `.github/workflows/mhlw-weekly-inpatient-survey-audit.yml`
- Latest successful acquisition run: https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research/actions/runs/44469939342
- Latest successful audit run: https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research/actions/runs/44470515705

## 2. MHLW G-MIS facility-level bed snapshots

Official publication pages:
- https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00335.html
- https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html

Acquisition and audit:
- 43 CSV links discovered; all 43 downloaded successfully and passed structural audit.
- Snapshot range: 2021-12-01 through 2024-03-06.
- Snapshot interval distribution: 27 intervals of 14 days, five of 21 days, four of 28 days, five of 35 days, and one of 56 days. This is not a daily/weekly series.
- Three header variants were identified. The earliest uses shorter labels for immediate beds and inpatients; the later files use "即応病床数" and either "入院中患者数" or "入院中".
- Facility records range from 2,214 to 3,516 per snapshot. From 2022-05-18 through 2023-05-03, two or three rows per snapshot lack a facility code; these rows cannot be joined by facility code and have been preserved.
- No duplicate nonblank facility codes were found in the audited snapshots.
- "未報告" records are present (up to 140 in the inspected snapshots). They must not be treated as zero or assumed to represent a current-date submission.
- The 2022-01-05 file contains 14 raw observation-date cells represented as Excel serial "44566"; the audit normalized this only for date-consistency checking and retained the raw CSV unchanged.

Comparability break:
- From 2023-10, MHLW changed the focus of secured-bed arrangements toward severe and moderate II patients. This changes the interpretation of secured-bed counts and means the pre- and post-change bed counts must not be compared as if they had an unchanged denominator/target population.
- The G-MIS snapshots are facility-level cross-sections, not a fixed facility panel. Facility-list/reporting coverage changes materially over time.

Files:
- Original CSVs: `data/raw/mhlw/gmis_all_snapshots/`
- Acquisition manifest: `data/metadata/mhlw/gmis_all_snapshots_manifest.json`
- Structural audit: `data/audits/mhlw/gmis_all_snapshots_audit.json`
- Acquisition script: `scripts/acquire_mhlw_gmis_all_snapshots.py`
- Audit script: `scripts/audit_mhlw_gmis_all_snapshots.py`
- Workflow: `.github/workflows/mhlw-gmis-all-snapshots.yml`
- Latest successful acquisition/audit run: https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research/actions/runs/44469420602

## 3. Preliminary research decision

1. The weekly survey is the stronger candidate for the primary nationwide temporal indicator because it provides 171 prefecture-level snapshots with 47 prefectures represented in every workbook.
2. G-MIS is supplementary: it provides facility-level detail but has irregular snapshot intervals, changing facility coverage, nonreporting, and a post-2023-10 change in the secured-bed target population.
3. The weekly survey's schema changes (especially 2023-05-10 and 2023-10-04) must be audited against source footnotes before deciding which variables can be joined.
4. The "－" marks, unreported values, missing facility codes, and any blank cells must remain distinct from numeric zero.
5. No files were inserted into the evidence table, MASTER, or final analysis dataset. No occupancy rates or causal estimates were calculated.

## 4. Next audit tasks

- Extract and compare footnotes/definitions from representative weekly workbooks across each schema era, with priority on 2023-05-10 and 2023-10-04.
- Establish the exact meaning of "－" in the 2023-10 onward workbooks.
- Build a versioned variable crosswalk for the nine weekly schema variants and the three G-MIS header variants.
- Only after crosswalk approval, create a separate derived prefecture-week dataset and document aggregation/missingness rules.
- If the study needs pre-2020-12 coverage, inventory the earlier PDF-only weekly survey reports and assess whether their tables can be extracted reproducibly.

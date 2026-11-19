# Administrative/public-source initial audit — 2026-11-19

Audit timestamp: 2026-11-19 14:56 JST  
Scope: MHLW G-MIS hospital-bed snapshots and FDMA ambulance-transport difficulty workbook.  
Policy: source files are acquired from official URLs; no historical MASTER, evidence table, or analysis dataset was modified. No normalization or longitudinal join was performed for the G-MIS probe.

## 1. MHLW G-MIS public CSV snapshots

Official publication pages:
- https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00335.html
- https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html

Direct official CSV files acquired successfully (HTTP 200, text/csv):
1. https://www.mhlw.go.jp/content/10900000/000893241.csv
   - Published snapshot date identified in source notes/data: 2022-01-05.
   - 227,552 bytes; CP932; SHA-256: 31aa4539f667487da377482a3008a31b982c73a357f98f3a3bc540b0a7012958.
   - 2,301 data records; 2,301 unique facility codes; no duplicate facility codes.
   - Report status: 2,285 reported, 16 unreported.
   - Raw observation-date values: 2,287 rows "2022/1/5"; 14 rows "44566" (all 14 are at the end of the sheet and correspond to Okinawa facilities). The raw value is preserved; no conversion was applied.
2. https://www.mhlw.go.jp/content/001234488.csv
   - Published snapshot date: 2024-03-06.
   - 255,866 bytes; UTF-8 with BOM; SHA-256: 25d66056467db06fbedc0eecfc8a443ac82e99ce6adcf2fc3109d1b07f985465.
   - 2,214 data records; 2,214 unique facility codes; no duplicate facility codes.
   - Report status: 2,171 reported, 43 unreported.
   - All 2,214 observation-date values are "2024/3/6".

Facility-code overlap between these two snapshots:
- Intersection: 1,623; union: 2,892; Jaccard: 0.5612.
- 678 codes occur only in the 2022-01-05 snapshot; 591 only in the 2024-03-06 snapshot.
- This indicates material change in the facility list/coverage; do not treat the snapshots as a fixed panel without investigating facility entry/exit and reporting coverage.

Header and definitions:
- Both files have 12 columns and the header is on line 21.
- Shared key fields: prefecture, secondary medical area, medical institution code/name, report status, observation date, secured beds, immediately available beds, inpatient count, and free-text remarks.
- The 2022 file labels the inpatient column "入院中患者数"; the 2024 file labels it "入院中". This is a schema-label difference requiring explicit crosswalk review.
- Source notes state the data covers medical institutions with beds positioned as secured beds in prefectural bed plans; it excludes institutions/beds receiving suspected COVID-19 patients and does not publish temporary medical facilities.
- "確保病床数" is basically the maximum bed count in the general phase. "即応病床数" is the number made available for the prefecture's current phase and includes beds with patients already admitted. "入院中患者数" is the number of COVID-positive patients admitted at the observation date.
- Source notes warn that facility-level totals may not match prefectural plan totals and that secondary medical-area allocation may not match prefectural plan area totals.
- "未報告" means the institution had not entered information for the observation date; the displayed figures may be from an earlier entry. It must not be treated as zero or as a current-date report.
- Main numeric fields contain no nonnumeric nonblank values in these two files. Blank immediate-bed/inpatient values match unreported counts (16 in 2022; 43 in 2024). The free-text remarks column contains both narrative text and numeric-looking values; do not parse it as a quantitative variable.
- The 2022 file contains 1 blank secured-bed value; the 2024 file contains no blank secured-bed values.
- No occupancy rate was calculated: denominators, unreported records, phase differences, and zero immediate-bed values require further validation.

Interpretation:
- These are two facility-level cross-sectional snapshots, not a continuous daily/weekly series by themselves.
- They are potentially useful for a point-in-time assessment of COVID-specific hospital capacity and inpatient load, but cannot yet be adopted as a longitudinal measure of nationwide bed occupancy.
- Next G-MIS task: crawl the official MHLW publication pages and enumerate every dated snapshot file, then acquire each original file with URL, date, content type, bytes, SHA-256, encoding, header, report status, and definition version. Only after that should we assess a longitudinal panel or national aggregate series.

Files:
- Raw files: data/raw/mhlw/gmis_publication_probe/
- Acquisition manifest: data/metadata/mhlw/gmis_publication_probe_manifest.json
- Structure audit: data/audits/mhlw/gmis_publication_probe_audit.json
- Scripts: scripts/acquire_mhlw_gmis_publication_probe.py; scripts/audit_mhlw_gmis_publication_probe.py
- Workflow: .github/workflows/mhlw-gmis-publication-probe.yml
- Workflow run: https://github.com/0FTd95W213sGXXV0C7R2/actions/runs/44468537552
- Output commit: ddc658a66358072c543864272dbee289fecc06f4

## 2. FDMA ambulance-transport difficulty workbook

Official source page and file:
- https://www.fdma.go.jp/disaster/coronavirus/post-1.html
- https://www.fdma.go.jp/disaster/coronavirus/items/coronavirus_data.xlsx

Fresh official download was recorded at 2026-11-19 14:16:36 JST:
- 286,999 bytes; SHA-256: bc586c494b32dd83c8d79c1ffd736e828ca208c93a7932667c5a606e1a6a4101.
- Four sheets, 52 fire departments.
- Current-period overall sheet: 261 weekly headers, 2020-03-30 to 2025-03-24.
- Previous-year comparison sheet: 261 weekly headers, 2019-04-01 to 2024-03-25.
- COVID-suspected and non-COVID-suspected subgroup sheets: 157 weeks each, 2021-03-29 to 2024-03-25.
- Normalized output has 44,308 rows. No zero imputation or daily interpolation.
- Subgroup reconciliation: 8,163 complete numeric triplets, all exact matches; one incomplete triplet (Akita City Fire Department, week starting 2022-03-07: overall blank, COVID-suspected 0, non-COVID-suspected 0).
- One printed week-end label discrepancy: week starting 2024-04-01 printed as ending 2024-04-08, while expected end is 2024-04-07.
- First four weeks (2020-03-30 through 2020-04-26) contain source values before the formal weekly survey period; provenance of these early values remains to be explained.
- COVID/non-COVID subgroup breakdown ends 2024-03-25; the overall series continues to 2025-03-24.

Interpretation and limits:
- FDMA defines the relevant difficulty case using at least 4 receiving-hospital inquiries and at least 30 minutes at the scene.
- The workbook is a weekly, fire-department-level count, not a patient-level dataset. It does not directly identify the patient outcomes, the reason for each failed acceptance, or the ethical decisions made.
- The COVID/non-COVID breakdown is not available for the final year of the overall series. Do not compare subgroup counts after the subgroup series ends.
- Use as a supplementary indicator of emergency-care access pressure, not as a direct measure of all non-COVID care access or proof that a patient was not transported.
- Existing raw workbook and audit outputs are retained; no changes were made to the existing MASTER or evidence table.

Audit files:
- data/raw/fdma/emergency_transport/coronavirus_data.xlsx
- data/metadata/fdma/emergency_transport/manifest.json
- data/audits/fdma/emergency_transport/weekly_header_and_values_audit.json
- data/audits/fdma/emergency_transport/normalized_dataset_build_audit.json

## 3. Overall decision

- G-MIS: source files acquired and preliminary schema/coverage audit completed; not yet eligible as a longitudinal series. Enumerate and acquire all dated snapshots next.
- FDMA: official workbook acquired and weekly structure/value audit completed; suitable only as a supplementary weekly indicator with explicit limitations.
- No values from either source have been inserted into the final analytical dataset or used for causal inference.

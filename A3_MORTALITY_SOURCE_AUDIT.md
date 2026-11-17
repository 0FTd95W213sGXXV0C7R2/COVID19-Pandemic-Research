# A3 Mortality Source Audit — First Pass

Recorded: 2026-11-17 16:07:12 JST

## Decision

**Adopt the e-Stat annual confirmed vital-statistics table as the primary source family for A3 (COVID-19 deaths by month of death), pending direct extraction and validation of the monthly cells.** Do not use the historical MHLW comparison PDF's preliminary monthly values as the canonical series.

## Primary table

- Provider: Ministry of Health, Labour and Welfare / e-Stat
- Table title: 人口動態調査・人口動態統計・確定数・死亡・下巻 第3表「死亡数，死因（死因簡単分類）・性・死亡月別」
- e-Stat table ID: `0003411700`
- URL: https://www.e-stat.go.jp/dbview?sid=0003411700
- Observation unit: number of deaths
- Time basis: month of death
- Dimensions: year, month, sex, simplified cause-of-death classification
- COVID-19 category: `22201_新型コロナウイルス感染症`
- Years exposed by the table: 2015–2024 (including the study period 2020–2023)
- Statistical basis: population dynamics survey, covering births, deaths, marriages, divorces and stillbirths notified under the relevant notification rules; monthly survey.

## Annual confirmed totals cross-check

Official MHLW annual confirmed statistics provide the following totals:

| Year | COVID-19 deaths (persons) | Official source |
|---|---:|---|
| 2020 | 3,466 | MHLW 2021 vital statistics annual report |
| 2021 | 16,766 | MHLW 2021 vital statistics annual report |
| 2022 | 47,638 | MHLW 2023 vital statistics annual report |
| 2023 | 38,086 | MHLW 2023 vital statistics annual report |

Sources:
- 2021 annual report, official PDF: https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei21/dl/15_all.pdf
- 2023 annual report, official PDF: https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/kakutei23/dl/15_all.pdf

The 2021 report gives 2021 total 16,766 and 2020 total 3,466, including sex breakdowns. The 2023 report gives 2023 total 38,086 and 2022 total 47,638. It notes that the 2023 cause-of-death ranking includes COVID-19 as a ranking category for the first time; the 2022 comparison is presented retrospectively. For 2022, the reported classification includes ICD-10 categories U07.1, U07.2 and U10.9. Therefore, classification metadata must be preserved rather than assuming the code's definition is identical in every year.

## Why preliminary monthly comparisons are not canonical

MHLW's comparison document for deaths by death-certificate information vs. vital statistics provides monthly comparison figures, but explicitly states that the COVID-19-related figures are estimates under a defined method for timeliness and can differ from later published vital-statistics results. It also distinguishes the underlying cause of death, selected using WHO underlying-cause rules, from a broader related-death count.

- MHLW comparison document: https://www.mhlw.go.jp/content/10900000/001214132.pdf
- The document's monthly underlying-cause figures sum to 2020: 3,466; 2021: 16,756; 2022: 47,635; 2023 Jan–Sep: 32,022. The annual confirmed totals above are 3,466; 16,766; 47,638; and 38,086 respectively.
- Differences for 2021 and 2022 (10 and 3 deaths respectively) and the incomplete 2023 monthly display show why this comparison PDF must not replace the current annual confirmed e-Stat table. These monthly values are retained only as a historical cross-check, not as the study's canonical data.
- The PDF's broader "COVID-19-related deaths (I or II column)" and "I-column" counts are not the same definition as COVID-19 selected as the underlying cause. Do not combine them with the e-Stat cause-specific series.

## Limitations and unresolved work

1. The e-Stat page exposes the full required dimensions and code, but the 48 monthly values for 2020–2023 have **not yet been extracted into a raw CSV** in this audit.
2. Confirm the exact values by selecting sex = total, cause = 22201, month = Jan–Dec, year = 2020–2023 in e-Stat and downloading the complete table/API response. Record the original download, retrieval timestamp, file hash and transformation log.
3. Sum the 12 monthly values for each year and compare against the annual confirmed totals above. Any difference must be investigated, not silently corrected.
4. Confirm whether annual totals and monthly table cells use the same final/confirmed revision and classification rules. Retain the source's original year/cause labels.
5. Do not derive daily deaths from cumulative report-date data or call monthly reporting-date figures deaths by month of death.

## Status

- Source family for A3: **adopted as primary source family**.
- Annual confirmed totals: **verified from official annual reports**.
- Monthly 2020–2023 raw data: **not yet acquired; validation incomplete**.
- Analysis: **not started**.
- No legacy MASTER values or derived data were used.


## Reproducible acquisition pipeline prepared — 2026-11-17 16:10 JST

- e-Stat API documentation confirms that data acquisition through the API requires an application ID (appId), obtained by registering an e-Stat user account: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0
- The official table page confirms that table 0003411700 exposes monthly, sex, cause and annual dimensions, including years 2020–2023 and cause code 22201.
- Added `scripts/acquire_estat_a3.py` to request the 48 monthly observations (total sex, COVID-19 cause, month-of-death basis), plus the four annual-total cells. It preserves raw metadata and raw API responses, produces a CSV and SHA-256 manifest, and fails closed on missing/duplicate/non-numeric observations or annual reconciliation differences.
- Added `.github/workflows/estat-a3-acquisition.yml`, manually triggered only. It expects the repository Actions secret `ESTAT_APP_ID`, uploads the raw source responses and audit outputs as a 14-day artifact, and does not commit raw data.
- Workflow expression interpolation was corrected and the saved workflow was re-fetched to verify the expressions.
- **Not yet executed:** the repository secret `ESTAT_APP_ID` has not been provided/configured through this workflow, and the current execution environment cannot directly download the e-Stat API response. No monthly values are claimed as acquired.
- Next action: configure the e-Stat application ID as a repository Actions secret named `ESTAT_APP_ID`, then run the workflow manually from GitHub Actions. Review the artifact and annual reconciliation before accepting the 48 monthly cells.
- No legacy MASTER or legacy derived data was read or used.

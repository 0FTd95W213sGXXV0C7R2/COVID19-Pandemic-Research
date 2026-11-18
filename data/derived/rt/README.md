# EpiForecasts Japan Rt (2020-08-30 to 2022-03-31)

## Dataset

- **File:** `EpiForecasts_Japan_Rt_20200830_20220331.csv`
- **Geographic coverage:** Japan (national)
- **Period:** 2020-08-30 through 2022-03-31
- **Temporal resolution:** Daily
- **Rows:** 579 daily observations
- **Columns:** `date`, `Rt_median`, `vintage_count`, `pooled_row_count`
- **Value:** `Rt_median` is the median of pooled Rt estimates for each date.

## Source and reconstruction

The source is the EpiForecasts `covid-rt-estimates` repository and its documented historical reconstruction approach. The repository documentation explains that the current `rt.csv` is a rolling recent window and that historical estimates can be reconstructed from the Git history by collecting historical snapshots and pooling overlapping estimates.

- Repository: https://github.com/epiforecasts/covid-rt-estimates
- Historical reconstruction example (official Gist): https://gist.github.com/sbfnk/d2900c745312219e3e48e08adde47cde
- Methods: https://epiforecasts.io/covid/methods.html
- Source CSV path in the upstream repository: `national/cases/summary/rt.csv`

For this reconstruction, 411 commits in the upstream file history were examined. The pooled Japan subset contained 45,999 rows. The resulting daily series contains 579 dates, with 18–117 contributing vintages per date. The daily `Rt_median` is the median across the pooled rows for that date.

## Important methodological limitation

This file is a Python reconstruction of the median time series based on the documented historical-snapshot pooling approach. It is **not yet verified as an exact, full reproduction of the upstream R function** (including all summary statistics and harmonization details). Do not describe it as exact R-output parity.

## Relationship to the project's existing MASTER

This file is stored as a separate derived Rt series. A read-only comparison against the project's existing MASTER Rt series found matching dates for all 579 days but non-identical numerical values (MAE 0.113528; RMSE 0.171333; Pearson correlation 0.743948). The two series' estimation definitions and provenance have not been established as equivalent. Therefore, this file does not replace or overwrite the MASTER Rt column. Treat the series separately unless a later methodological review establishes comparability.

The original source CSV previously listed in the MASTER inventory (`STEP_R5_R7_Japan_Infection_Status_Rt_20200104_20230508.csv`) was reported as unavailable. This EpiForecasts reconstruction is not a substitute for that missing file and does not establish the provenance of the MASTER Rt values.

## Data quality checks performed

- 579 rows; dates cover 2020-08-30 through 2022-03-31 without gaps.
- No duplicate dates.
- No missing or non-finite `Rt_median` values.
- `vintage_count` and `pooled_row_count` are positive on every date and equal on every row.
- The CSV is retained unchanged from the supplied file.

## File integrity

SHA-256 of the CSV as packaged: `fd1085ae7684bd67996fd7e13dbbe7ff9cd732138a413de89d261b0eb970f307`

## Suggested repository location

`data/derived/rt/EpiForecasts_Japan_Rt_20200830_20220331.csv`

Place this README alongside the CSV. Do not place the file under `data/raw/`: it is a derived reconstruction, not an untouched upstream source snapshot.

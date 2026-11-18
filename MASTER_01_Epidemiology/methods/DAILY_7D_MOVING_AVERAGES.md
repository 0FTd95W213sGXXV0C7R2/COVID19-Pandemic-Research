# Daily indicator series with trailing 7-day moving averages

Generated: 2026-11-18

This note documents companion CSVs that retain each daily source series and append a trailing 7-day arithmetic mean. Original source files are not overwritten.

## Method

For each daily series, the value on date t is the arithmetic mean of the current observation and the preceding six calendar-day observations:

MA7_t = (x_t + x_(t-1) + ... + x_(t-6)) / 7

A value is emitted only when all seven observations in that window are present and finite. Otherwise the MA field is blank. No missing values are imputed and no zero is substituted for missing data. The window is trailing (not centered) and includes the date shown in the row.

## Companion datasets

| Indicator | Source value column | Added column | Companion CSV |
|---|---|---|---|
| National new cases | New_cases | New_cases_7dMA | ../data/01_New_cases/national_new_cases_daily_20200116_20230508_with_7dMA.csv |
| National severe cases | Severe_cases | Severe_cases_7dMA | ../data/03_Severe_cases/national_severe_cases_daily_20200509_20230508_with_7dMA.csv |
| National reported daily deaths | Deaths_reported_increment | Deaths_reported_increment_7dMA | ../data/04_Deaths/national_deaths_daily_20200509_20230508_with_7dMA.csv |
| EpiForecasts Japan Rt reconstruction | Rt_median | Rt_median_7dMA | ../data/05_Rt/EpiForecasts_Japan_Rt_20200830_20220331_with_7dMA.csv |

The deaths moving average is calculated from Deaths_reported_increment, not from the cumulative-deaths column. The first date in that source has no reported daily increment, so the 7-day mean remains blank until seven consecutive daily increments are available.

## Non-daily indicator

The national bed-occupancy series ../data/02_Bed_occupancy/national_bed_occupancy_sapmed_202005_202305.csv is weekly (with a documented early observation and source/definition transitions). It is therefore not assigned a daily 7-day moving average in this operation.

## Scope and provenance

The EpiForecasts Rt file is the separately documented 2020-08-30–2022-03-31 reconstruction. It remains distinct from the project's prior MASTER Rt series and must not be treated as replacing or proving equivalence with that series. Its companion moving average is only a smoothed representation of the EpiForecasts series.

All original CSV and compressed source files remain unchanged. These companion files are derived analysis-ready data.

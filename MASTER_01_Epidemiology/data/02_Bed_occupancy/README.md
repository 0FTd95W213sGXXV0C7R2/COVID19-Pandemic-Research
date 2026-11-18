# Nationwide COVID-19 bed occupancy (Sapporo Medical University)

## File
`national_bed_occupancy_sapmed_202005_202305.csv`

## Scope
- Geography: Japan nationwide only.
- Indicator: overall bed occupancy rate (`病床使用率・全体`), not the severe-care-bed series.
- Period: 2020-05-07 through 2023-05-03.
- Observations: 157 dated observations.
- Unit: percent (%).
- Frequency: weekly as published by the source; dates are retained as published and are not interpolated.

## Source and extraction
- Dashboard: https://web.sapmed.ac.jp/canmol/coronavirus/japan_indicator.html
- The page identifies the series as bed occupancy, provides separate controls for `全体` and `重症者`, states that it is updated weekly, and names the Ministry of Health, Labour and Welfare (MHLW) as a data source.
- The page's embedded data file is `japan_bed.csv`. The source file has a first metadata/header row; the nationwide series is the `全国` column. This derived CSV retains only the date and nationwide value.
- Values are transcribed directly from the source CSV, not digitized from a chart image. The source's first available observation in May 2020 is 2020-05-07; the 2020-04-28 observation was excluded to honor the requested May 2020 start.

## Limitations
- This is the dashboard's published nationwide overall bed-occupancy series. Do not relabel it as the occupancy rate of immediately available beds or severe-care beds without a separate definition audit.
- The dashboard advises users to verify original data for accuracy and notes that recent values may be provisional/revised.
- The dashboard cites MHLW and the Statistics Bureau as data sources. For academic analysis, cross-check the underlying MHLW survey definitions and releases, especially when comparing across changes in survey methodology or bed phases.

## Citation
Idogawa M, Tange S, Nakase H, Tokino T. Interactive Web-based Graphs of Coronavirus Disease 2019 Cases and Deaths per Population by Country. *Clinical Infectious Diseases*. 2020;71:902–903. https://doi.org/10.1093/cid/ciaa500

Accessed: 2026-11-18 (JST).


## Early observation added from MHLW (2020-04-28)

A pre-May observation has been appended to the same nationwide overall bed-occupancy series, with its distinct source and denominator reference date explicitly recorded in the CSV metadata columns.

- 2020-04-28: 5,514 inpatients / 31,099 secured beds = **17.730474%** (calculated from the source counts; the source table displays 18% rounded).
- Numerator reference: 2020-04-28 00:00.
- Denominator reference: 2020-05-01 bed count.
- Source: MHLW official materials, including the table titled "入院者数、受入確保病床数に占める入院者数の割合" (2020-04-28 to 2020-07-29).
- The 2020-05-07 dashboard value is independently cross-checked against MHLW: 4,436 / 31,513 = 14.0767%; denominator reference date 2020-05-08. It exactly matches the dashboard value.
- Source table: https://www.mhlw.go.jp/content/10900000/000797218.pdf
- MHLW survey index: https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html

### Comparability and interpretation

The 2020-04-28 observation uses the MHLW snapshot definition: inpatients at 00:00 (including patients confirmed for admission within one or two days) divided by beds secured for the peak phase; the bed denominator is dated 2020-05-01. The subsequent dashboard observations are weekly published nationwide overall bed-occupancy values. The 2020-05-07 cross-check demonstrates a numerical match for that date, but it does not prove that every historical observation has identical collection mechanics.

Per the research decision dated 2026-11-18 (JST), observations from different definitions or source procedures may be retained in one longitudinal dataset when the differences, effective dates, and comparability limitations are explicitly documented. Do not silently treat all observations as perfectly homogeneous. Use the row-level `source_series` and `definition_note` fields to identify the source and definition. The original source CSV is not overwritten; this is an extended derived dataset.

### Extended CSV columns

- `date`: observation date.
- `national_bed_occupancy_percent`: percentage.
- `numerator_inpatients`, `denominator_secured_beds`: populated when source counts are available.
- `numerator_as_of`, `denominator_reference_date`: reference dates for numerator and denominator.
- `source_series`, `definition_note`: provenance and definition/caveat at row level.

Accessed: 2026-11-18 (JST).

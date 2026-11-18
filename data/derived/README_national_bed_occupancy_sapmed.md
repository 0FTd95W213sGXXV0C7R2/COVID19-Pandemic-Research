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

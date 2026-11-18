# MASTER01 figures — Epidemiology (Japan)

Generated: 2026-11-18 JST  
Source: the CSV files currently stored under `MASTER_01_Epidemiology/data/`. The source CSVs were not modified.

## Charts

| Indicator | Figure | Frequency / smoothing |
|---|---|---|
| New cases | [new_cases.svg](./new_cases.svg) | Daily original values + trailing 7-day moving average |
| Bed occupancy | [bed_occupancy.svg](./bed_occupancy.svg) | Weekly original values; no daily 7-day moving average |
| Severe cases | [severe_cases.svg](./severe_cases.svg) | Daily original values + trailing 7-day moving average |
| Reported-death increment | [deaths.svg](./deaths.svg) | Daily reported cumulative-count increment + trailing 7-day moving average |
| Rt | [rt.svg](./rt.svg) | EpiForecasts Japan reconstruction + trailing 7-day moving average |

## Reading notes

- Daily 7-day moving averages use the companion CSV columns already documented in [DAILY_7D_MOVING_AVERAGES.md](../methods/DAILY_7D_MOVING_AVERAGES.md). The source value is retained and shown as a separate line.
- A moving-average value is blank where the source method does not provide a complete seven-observation window. No interpolation, imputation, or zero-filling was added.
- Bed occupancy is weekly and is plotted at its published observation dates. It is not resampled to daily frequency and has no forced 7-day moving average.
- The deaths chart plots `Deaths_reported_increment`, which is the day-to-day change in cumulative reported deaths. It is not necessarily the number of deaths that occurred on that date.
- The Rt chart is limited to the EpiForecasts reconstruction from 2020-08-30 through 2022-03-31. It is not asserted to be identical or equivalent to the legacy MASTER Rt series.
- The bed-occupancy and severe-case charts retain the definition/source caveats recorded in their indicator README files.


# Non-COVID healthcare access: article-reported aggregate evidence

## Dataset identity

- File: `data/processed/non_covid_access/article_reported_aggregate_evidence.csv`
- Unit of observation: one published aggregate estimate or cohort count reported in a source article.
- Row count: 47.
- Source studies: Yoshida et al. (2022), Yamaguchi et al. (2022), Kurokawa et al. (2022).
- Observation granularity: mixed article-level / survey-outcome / month-comparison; **not a common time series**.
- Raw patient-level and claims-level records are not included.

## Columns

| Column | Meaning |
|---|---|
| study_id | Stable identifier for the source study |
| evidence_id | Unique row identifier within the extracted evidence table |
| study_design | Source study design |
| observation_period | Period represented by the reported outcome |
| collection_period | Survey collection or article publication period |
| population_scope | Analytic population described by the source |
| facility_scope | Facility or sampling scope |
| outcome_or_measure | Reported outcome, count, or association |
| numerator | Source-reported count when available; blank when not reported |
| denominator | Source-reported denominator when available; blank when not reported |
| value | Source-reported value, preserving sign for percentage changes |
| unit | Unit of value (percent, percent_change, persons, discharges, etc.) |
| estimate_basis | Unweighted count, weighted estimate, multivariable model, or observed cohort total |
| comparison_or_reference | Comparator and reference period |
| source_locator | Article section, table, figure or supplement locator |
| interpretation_limit | Row-specific limitation |
| source_url | Canonical source article URL |

## Source-specific rules

### Yoshida et al. (2022)
- 7,747 respondents with a disease currently under treatment.
- Survey collected 2020-08-25 to 2020-09-30; outcomes recalled for April-May 2020.
- Percentages and counts are self-reported, cross-sectional outcomes.
- Adjusted odds ratios are associations, not causal effects.
- Individual-level data are not publicly available due to ethics approval restrictions.

### Yamaguchi et al. (2022)
- 26 anonymised hospitals; 785,495 patients in the study cohort.
- Hospitalisation counts are based on discharge month.
- Percentage changes compare 2020 with the same month in 2019 unless otherwise stated.
- MDV claims data are proprietary and not publicly available.
- This table stores article-reported values, not a reconstructed claims dataset.

### Kurokawa et al. (2022)
- 3,678 respondents with a planned elective surgery.
- The unweighted count (223; 6.06%) and weighted estimate (431; 11.72%) are separate estimates and must remain separate.
- Self-reported planned surgery postponement/cancellation; not hospital procedure-volume statistics.
- Data are available upon reasonable request; no request was made.

## Prohibited transformations

- Do not merge the three studies into one prevalence estimate.
- Do not convert survey outcomes into daily/monthly values.
- Do not infer raw counts from rounded percentages.
- Do not treat hospital service-volume reductions as proof of refusal, unmet need, or causal effects.
- Do not describe this file as raw source data or an independently reproduced analysis.

# Phase 2 — Primary Source Mapping (Initial Verification)

Recorded: 2026-11-17 16:05:10 JST

## Scope and rule

This is an initial source map for the new study. The old MASTER, its values, and its derived analyses are not inputs. Existing Notion source records are discovery leads only; registration or historical verification does not establish adoption. Sources below are candidates pending file-level audit. No bulk data acquisition or analysis is authorized by this map.

## Initial source map

| Indicator | Candidate primary source | Measurement basis / verified points | Limitation and current decision |
|---|---|---|---|
| A1 Infection burden | [MHLW daily open data](https://www.mhlw.go.jp/stf/covid-19/open-data.html); [MHLW weekly reports after the legal-status change](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00485.html) | Pre-2023-05-08 daily new positives; source notes changes in aggregation source (2020-05-08) and date handling. Post-transition reports are weekly sentinel reports. | Do not connect daily all-case counts to weekly sentinel rates. Confirm date basis and reporting changes before period segmentation. Candidate for period-specific descriptive analysis. |
| A2 Severe/inpatient burden | MHLW daily severe/inpatient open data; [G-MIS bed status page](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html) | Severe cases, inpatient patients and new admissions are different measures. G-MIS defines secured beds, immediately available beds and patients hospitalized at the reference time. | Daily inpatients are a stock, not admissions flow. G-MIS archive includes a 2024-03-06 reference date; audit coverage, non-reporting and phase changes. Candidate, not adopted. |
| A3 Mortality | [e-Stat vital statistics: deaths by cause, sex and month of death (confirmed counts)](https://www.e-stat.go.jp/dbview?sid=0003411700); MHLW cumulative daily COVID death CSV as separate report-date series | Vital statistics provide death-month and cause-based counts; annual confirmed counts are distinct from daily cumulative reports. | Use monthly death-month counts as the principal candidate; obtain each 2020–2023 annual table and check cause classification/revisions. Daily cumulative differences must not be called deaths on that date. |
| A4 Excess mortality | All-cause vital statistics plus a separately specified expected-deaths method | No single adopted expected-deaths model or baseline has been selected. | Hold. No excess-mortality estimate until baseline, uncertainty and age adjustment are prespecified. |
| B1 Emergency transport difficulty | [FDMA COVID-19 emergency transport difficulty survey](https://www.fdma.go.jp/disaster/coronavirus/post-1.html) and its linked weekly workbook | Official weekly survey and linked workbook. FDMA white paper describes the difficulty criterion as 4+ hospital inquiries and 30+ minutes at scene for the cited period. | Verify period-specific definitions and fire department coverage. COVID-suspected subcategory stopped with the 2024-04-08 format change. Difficulty cases do not mean all cases were untransported. Candidate supporting indicator. |
| B2 Hospital capacity | [MHLW G-MIS bed status page](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html) | Secured beds, immediately available beds, inpatient patients and non-reporting are separately defined. | Do not treat secured beds as operational beds. Snapshot dates and facilities covered must be audited. Candidate supporting indicator. |
| B3 Workforce capacity | No suitable official series verified in this pass. | Potential measures include staffing shortages, workforce availability and facility service restrictions. | Hold; do not substitute non-representative surveys as national prevalence. |
| C1 Non-COVID care access | [11th MHLW NDB Open Data](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000177221_00017.html); Hospital Report as an alternative candidate to investigate | NDB provides medical treatment patient counts and claims counts, including monthly and prefectural breakdowns for listed categories. | Exact claim period, public-expense claim inclusion, and whether a longitudinal monthly series exists are unverified. Not yet accepted for pandemic-wide time series. |
| C2 Cancer care pathway | [National Cancer Center cancer statistics download](https://ganjoho.jp/reg_stat/statistics/data/dl/index.html) | National Cancer Registry data by diagnosis year (2016–2023), including national/prefectural incidence tables. | Annual registry counts are not monthly visits or treatment volumes. Check 2020 publication delay, registry coverage and provisional/final status. Candidate for annual descriptive analysis only. |
| C3 Unmet need / deferred care | No new primary survey selected. | Existing candidate studies need their sample, timing and definitions rechecked. | Hold until a primary survey with usable sampling information is identified. |
| D1 Resource allocation | Government guidance, professional society guidance, expert panel records and documented cases | Documentary comparison of formal criteria versus evidence of implementation. | No single quantitative indicator. Formal rules alone do not prove actual allocation practice. |
| D2 Restrictions / rights | Laws, government policy notices, official review records and affected-group evidence | Build a timeline of scope, duration, exceptions and review mechanisms. | Separate legal restrictions from implementation and lived effects. |
| D3 Equity | Official stratified data and primary studies, where attributes and denominators align | Age and region are more likely to be available than disability or socioeconomic status. | Do not infer unobserved groups; report unavailable dimensions and denominator limits. |
| D4 Healthcare worker burden | Existing candidate primary studies in Notion, including the 2020 ICU-worker survey | Survey evidence can support specific experiences and measured outcomes. | Samples are not national workforce estimates; no direct generalization or causal inference. |
| D5 Personal data governance | [Personal Information Protection Commission COVID-19 guidance portal](https://www.ppc.go.jp/news/careful_information/portal_covid-19/) | Official materials address infection information, contact tracing and medical-provider data sharing. | Supports analysis of legal/governance rules, not proof of actual compliance or practice. |
| E1/E2 Transparency and policy revision | [MHLW Advisory Board archive (21st onward)](https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00216.html); [MHLW expert panel / government measures index](https://www.mhlw.go.jp/stf/covid-19/seifunotorikumi.html) | Meeting agendas, minutes/summaries, evidence materials and policy-change documents can support a decision timeline. | Verify archive coverage across all relevant periods and distinguish expert advice from government decisions. Temporal sequence alone is not policy-effect evidence. |
| E3 Policy evaluation | No adequate ex-post evaluation source verified in this pass. | Requires explicit evaluation metrics and, where causal claims are made, a defensible counterfactual. | Hold. |

## Preliminary source decisions

- Candidate for primary descriptive analysis: A3 monthly cause-specific mortality, subject to acquisition of the 2020–2023 tables and classification audit.
- Candidate for period-specific descriptive analysis: A1 and A2; retain separate measurement regimes and date bases.
- Candidate supporting evidence: B1, B2, C2, D4, D5, E1 and E2.
- Not yet accepted: C1 pending NDB period/coverage verification.
- Hold: A4, B3, C3 and E3 pending a defensible source and operational definition.
- D1–D3 require a documentary evidence matrix; quantitative indicators should not be forced where no valid measure exists.

## Audit actions before acquisition

1. Retrieve the official source files or source documentation for each candidate.
2. Record exact temporal coverage, observation unit, date basis, denominator, revisions, missingness and reporting changes.
3. For A3, retrieve 2020–2023 vital-statistics annual confirmed tables and compare cause classifications across years.
4. For A1/A2, document the 2020-05-08 and 2021-09-03 source changes and the 2023-05-08 surveillance transition.
5. For B1/B2, audit FDMA survey coverage/definition changes and G-MIS snapshot dates/non-reporting.
6. For C1, inspect the NDB guide and data period before deciding whether it can support longitudinal comparison.
7. For D/E, assemble the relevant official laws, notices, meeting minutes and evidence documents; distinguish rules, advice, decisions and implementation.
8. Do not download all candidate datasets until these checks and adoption decisions are complete.

## References checked on 2026-11-17

- MHLW open data and data notes: https://www.mhlw.go.jp/stf/covid-19/open-data.html ; https://covid19.mhlw.go.jp/public/aboutdata.html
- MHLW surveillance change page: https://www.mhlw.go.jp/stf/covid-19/kokunainohasseijoukyou.html
- FDMA survey page: https://www.fdma.go.jp/disaster/coronavirus/post-1.html
- MHLW G-MIS bed status: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00327.html
- e-Stat vital statistics: https://www.e-stat.go.jp/dbview?sid=0003411700
- NDB 11th Open Data: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000177221_00017.html
- National Cancer Center cancer statistics: https://ganjoho.jp/reg_stat/statistics/data/dl/index.html
- MHLW Advisory Board archive: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00216.html
- Personal Information Protection Commission: https://www.ppc.go.jp/news/careful_information/portal_covid-19/

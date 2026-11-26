# National cancer QA stage 3

Date JST: 2026-11-27 (exact time not captured).

Direct pandas audit of preserved national_prefecture_comparison.csv.gz and rate_recalculation_audit.csv.gz. Keys year, sex, age_group, site_code, icd10. Duplicate keys: 0 in 5298 DIFFERENT incidence_rate rows, 0 in 12325 national recalculation rows, 0 in 12376 prefecture national-row recalculation rows. Both joins validated one_to_one. Both matched 4515, prefecture only 25, neither 758. Unmatched ages 85+ 491, 80-84 267, others 25. Six equal-denominator cases also have equal numerators and displayed rates to six decimal places (2017, site codes 1 and 101, total 70-74 and female 65-69/75-79). Exact precision classification still pending; do not infer true epidemiological differences. Sixteen joined prefecture rates exceed absolute recalculation difference 1e-8; tolerance review pending. No original workbook check yet.

Sources: https://drive.google.com/drive/folders/1HKGAXwAfD-JaXMtRy2FG7eMqYyP94YZo ; National Cancer Center aggregate downloads https://ganjoho.jp/reg_stat/statistics/data/dl/index.html (official page displays update 2026-07-10). No new dataset acquired. PENDING_QA; no imputation, no public data upload.

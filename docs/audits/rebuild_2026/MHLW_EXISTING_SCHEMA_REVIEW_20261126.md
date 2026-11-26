# Existing MHLW schema audit review

2026-11-26 JST (minute unverified). Review of existing JSON, not a new workbook-level audit.

Sources: data/audits/mhlw/weekly_inpatient_survey_audit.json; weekly_inpatient_survey_crosswalk_review_summary.json; gmis_all_snapshots_audit.json; https://www.mhlw.go.jp/stf/seisakunitsuite/newpage_00023.html

Weekly: 171 audited, zero SHA256 mismatches, missing books, prefecture detection errors or workbook errors in prior review. Nine schema groups, 100 header signatures, 28 unclassified headers, 15098 dash cells. Intervals 7d:168, 2d:1, 12d:1. Archive labels Feb 2 2024, discrepancy with PDF remains unresolved. Schema representative dates/counts: 2020-12-23:2; 2021-01-06:10; 2021-01-13:1; 2021-03-24:10; 2021-06-02:29; 2021-12-22:40; 2022-09-28:32; 2023-05-10:21; 2023-10-04:26.

G-MIS: 43 audited snapshots, zero unrecognized/failed, 3 header variants (41/1/1), intervals 14–56 days. Facility coverage changes; do not equate with prefecture weekly survey or ICU-specific count.

Decision: retain raw dash tokens, no zero imputation. Crosswalk remains candidate only. Next review 100 signatures and 28 unclassified headers against workbook footnotes, including secured vs immediately available beds, denominator and date discrepancies. Final crosswalk and cell-level QA pending. No raw data altered.

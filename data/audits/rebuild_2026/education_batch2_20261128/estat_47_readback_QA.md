# e-Stat 4-7 readback and arithmetic QA
JST 2026/11/28 10:45:18
Drive materialize returned two raw files without warnings. Actual sha256sum matches original uploads and manifest:
- 2019 22394 bytes f97d9a87128393953b53b1adcd0de4944af2c708206a639826d052fa58074d0b
- 2022 20015 bytes e06c2ea94a32c0e8bfdd11a19723469a540ce92656053756b6f52aba7842494c
Arithmetic QA on existing extracted cell CSVs: 2019 rows 6,14,22,30,42,50,58,66,78,86,94,102: sum D:Q equals C in all 12 groups. 2022 rows 5,9,...49: sum F:S equals E in all 12 groups. For primary and secondary counts, recompute percentage using denominator and Decimal ROUND_HALF_UP to 0.1 percentage point; 2019 published fraction multiplied by 100; 324 comparisons per year, zero mismatches. Secondary reasons allow up to two selections; do not sum as unique persons. Source notes 2019 A35:A37, 2022 A53:A55. Sources https://www.e-stat.go.jp/stat-search/files?stat_infid=000032011621 and https://www.e-stat.go.jp/stat-search/files?stat_infid=000040108364 . Existing CSV arithmetic checks only, not independent XML extraction. Cell CSV GitHub registration, normalized output, errata visual reconciliation and legacy rerun pending. No formal adoption.

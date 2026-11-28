# Education scope freeze
Recorded: 2026-11-28 11:15:27 JST

Collection closed for current research phase; formal adoption and PR merge not implied.

Primary candidate: prefecture_panel_2017_2024.csv (11730 rows, prior QA only; current connector returned empty content, blob f09e6ed1c2c0c4dbdcaadbc66615a478b307effe). Use comparable school/year/geography definitions; exclude 2019 conflicting illness/other/long_absence values until vintage resolved. Infection avoidance only where actually reported; never fill missing with zero.

Secondary candidates: estat47_normalized_2019.csv and estat47_normalized_2022.csv (648 rows; descriptive snapshots, not annual panel); ICT all sheets (5616 cells; 5202 numeric, 414 symbols; exclude symbols and unverified definitions). All-cell exports and errata ledgers are audit-only. Legacy gate excludes 298 pending and 3 differences; 54 matches remain candidates, not automatic adoption.

Methods: annual education outcomes cannot be merged directly with daily Rt without defined aggregation; distinguish national and prefectural levels; observational association is not causal effect. Exclude unresolved data rather than impute. No additional broad collection in this phase. Existing remaining.csv retained. Historical SHA256 discrepancies, Drive CSV location, full errata and final panel readback remain unresolved. PR remains open.

Sources: https://www.e-stat.go.jp/stat-search/files?stat_infid=000032011621 ; https://www.e-stat.go.jp/stat-search/files?stat_infid=000040108364 ; manifests and source IDs in this directory.

# National cancer QA stage 9

Date JST 2026-11-27; exact time not captured.
Four original binary OLE XLS files materialized from Drive (despite .csv suffix). SHA256 computed directly and compared against source_sha256 in every extracted row using Python csv.DictReader. Counts: national incidence 48993, prefecture incidence 1591632, all cancer mortality 73728, site mortality ASR75 16512. Total 1730865; hash-reference mismatches 0. Original workbook cell comparison blocked: xlrd unavailable, artifact_tool XLSX import returned FileContainsCorruptedData on legacy XLS; this does not establish corruption of original XLS. No cell-level verification claimed. Next use compatible read-only XLS parser in Colab or other supported environment. No data edits or adoption. PENDING_QA.

Source: https://ganjoho.jp/reg_stat/statistics/data/dl/index.html ; Drive raw cancer_statistics folder and analysis_ready/ncc_annual_long_2017_2024.csv.gz. No new dataset acquisition.

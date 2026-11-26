# Cancer data rights and coverage audit

Audit date (JST): 2026-11-26 (exact time not captured).

## Rights
Official sources:
- National Cancer Center, Cancer Information Service, copyright: https://ganjoho.jp/aboutus/attention/copyright.html
- National Cancer Center, Cancer Statistics, download tables (updated 2026-10-26): https://ganjoho.jp/reg_stat/statistics/data/dl/index.html
- Statistics FAQ: https://ganjoho.jp/reg_stat/statistics/qa_words/statistics_qa.html

The six national mortality/incidence workbooks are subject to dataset-specific attribution rules. Research use is supported; explicit permission for bulk public redistribution of reconstructed CSVs was not established. Keep rights pending, DRY_RUN true, PENDING_QA. HBCR report-derived data likewise remain pending. No new data acquired. For mortality with 2015 standard population, preserve the related Journal of Epidemiology 2023;33(7):372-380 citation and applicable official English attribution for original articles. For incidence cite the National Cancer Registry and NCC Cancer Information Service. Verify per-file citations before release.

## Coverage filename collision
Compared headers and first two records only. MEDIAS header: dataset,month,metric,covered_geographies,expected_geographies,status. NDB header: fiscal_year,release,scope,section,axis,source,member,sheet,source_period,dimension_columns,extracted_cells. NCC header: source_scope,measure,year,prefecture_code,value_status,rows. Distinct datasets; no overwrite. Proposed NCC path: data/processed/non_covid_access/cancer/pending_qa/national/coverage.csv. Full record comparison not performed. Prior dry run confirmed intended path absent among same-name paths.

## Status
30/30 processed files verified by Colab at 2026-11-26 23:45:47 JST; see data/audits/non_covid_access/cancer/colab_preservation_20261126_234547.json. Public upload remains gated on rights. Original 61 file byte recheck pending.

# National cancer QA stage 6

Recorded 2026-11-27 07:17 JST (runtime clock, minute precision).

Actual pandas recalculation from ncc_annual_long_2017_2024.csv.gz, using 18 age bins 0-4 through 85+, candidate Segi weights 12,10,9,9,8,8,6,6,6,6,5,4,4,3,2,1,0.5,0.5 (sum 100). Official NCC identifies Segi 1960 as world standard; individual weights not independently verified against original Segi publication in this run. Pivot keys source_scope,year,prefecture_code,site_code,icd10,sex. National 728 total, 679 compared, 49 both missing, max error 6.821210e-13; prefecture 34944 total, 32592 compared, 2352 both missing, max 7.776009e-09. All 33271 numeric within 1e-7. No asymmetric missingness. Excludes national_detail (2471 per standard, only all-age rate available). No imputation. Original workbook QA and Japan 2015 weights pending. PENDING_QA.

Sources: NCC Cancer Information Service, standard population https://ganjoho.jp/reg_stat/statistics/qa_words/word/kijunjinko.html (updated 2024-07-10; cites Segi M. Cancer mortality for selected sites in 24 countries (1950-57). Department of Public Health, Tohoku University School of Medicine, Sendai, Japan, 1960); ASR definition https://ganjoho.jp/reg_stat/statistics/qa_words/word/nenreityouseirikanritu.html; accessed 2026-11-27 JST. Data https://drive.google.com/drive/folders/1HKGAXwAfD-JaXMtRy2FG7eMqYyP94YZo .

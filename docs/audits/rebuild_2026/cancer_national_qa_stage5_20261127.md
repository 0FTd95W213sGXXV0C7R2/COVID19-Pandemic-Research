# National cancer QA stage 5

Date JST: 2026-11-27; exact time unavailable.

Recalculated Japan 1985 ASR from preserved long CSV using official 18 age weights (thousands): 8180,8338,8497,8655,8814,8972,9130,9289,9400,8651,7616,6581,5546,4511,3476,2441,1406,784. Sum 120287. Used age 85+ and excluded overlapping detailed bins. No duplicate age or ASR keys. National: 728 target, 679 numeric, 49 held, max absolute error 6.821210e-13. Prefecture workbook: 34944 target, 32592 numeric, 2352 held, max 8.878885e-09. All numeric within 1e-7 by maximum error. Python subsequently failed on optional groupby attribute access; preceding aggregates successfully computed. No imputation. Not independent original workbook extraction. Segi and 2015 standards pending. PENDING_QA.

Sources: National Cancer Center Cancer Information Service, age-adjusted incidence rate and standard population (updated 2024-07-10), https://ganjoho.jp/reg_stat/statistics/qa_words/word/nenreityouseirikanritu.html and https://ganjoho.jp/reg_stat/statistics/qa_words/word/kijunjinko.html ; Cancer Statistics 2026 appendix https://ganjoho.jp/public/qa_links/report/statistics/pdf/cancer_statistics_2026_app_J.pdf ; accessed 2026-11-27 JST. Data https://drive.google.com/drive/folders/1HKGAXwAfD-JaXMtRy2FG7eMqYyP94YZo .

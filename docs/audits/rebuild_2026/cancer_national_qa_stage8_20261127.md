# National cancer QA stage 8

2026-11-27 08:01 JST (runtime clock).
Independent rerun using pandas on preserved long CSV. Stage 7 outer join 735 keys; 56 published-only and 7 calculated-only. Seven pairs are female breast cancer ICD10 leading whitespace (C50), resolved by str.strip on temporary keys, no source changes. Remaining 49 published-only are total-sex rows for site codes 16,17,18,19,20,116,117 across 2017–2023; all 20 approximation input ages missing. Cause of original dash semantics unverified. Normalized one-to-one join 728 keys, 679 numeric pairs, max absolute error 1.0231815394945443e-12, 0 above 1e-7, 49 published-only, 0 calculated-only. Same stage 7 weights, sum 125319; approximate 20-bin calculation not exact official 21-bin validation. No imputation, source modifications, or adoption. PENDING_QA.

Sources: https://drive.google.com/drive/folders/1HKGAXwAfD-JaXMtRy2FG7eMqYyP94YZo ; NCC standard population https://ganjoho.jp/reg_stat/statistics/qa_words/word/kijunjinko.html (accessed 2026-11-27 JST).

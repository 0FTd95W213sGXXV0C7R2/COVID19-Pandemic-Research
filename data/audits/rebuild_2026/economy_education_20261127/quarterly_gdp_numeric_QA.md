# Quarterly GDP numeric QA
JST 2026-11-27 18:18
Source https://www.esri.cao.go.jp/jp/sna/data/data_list/sokuhou/files/2026/qe261_2/gdemenuja.html
Local CP932 originals parsed by quarter with inherited year. Six SHA256 match prior record. Counts 3225,3225,2838,2838,2322,2322 =16770; study 4160. Fiscal annual original sum Q2 Q3 Q4 next Q1: real 800 nominal 704, max absolute difference 0.2 billion yen each, all within 0.25. Deflator ratio original 2322, 2 exceed 0.05 (columns 18 and 23), max 0.05345866034; adjusted 2322, zero exceed 0.05, max 0.04995844743. Investigate input rounding before adoption. Long CSV generated locally; remote upload and readback pending. No full task adoption.

# ③ 全国・日次重症者数（厚生労働省CSV採用系列）

## データ
- 保存ファイル：`national_severe_cases_daily_20200509_20230508.csv.gz.b64`
- 復元後CSV：`national_severe_cases_daily_20200509_20230508.csv`
- 復元方法：リポジトリルートで `python scripts/decode_m1_data.py` を実行
- 対象：全国（厚生労働省CSVの `ALL` 列）
- 採用期間：2020-05-09〜2023-05-08（1,095日）
- 列：`Date`、`Severe_cases`

## 出典
- 厚生労働省オープンデータ：https://www.mhlw.go.jp/stf/covid-19/open-data_00002.html
- 原CSV：https://covid19.mhlw.go.jp/public/opendata/severe_cases_daily.csv
- 第117回新型コロナウイルス感染症対策アドバイザリーボード資料：https://www.mhlw.go.jp/content/12404000/001064697.pdf

## 定義・制約
- 全国値は厚労省CSVの `ALL` をそのまま採用。補間・推計・ゼロ補完・手動修正なし。
- 一部自治体は独自基準を使用。沖縄は2021-05-19、大阪・京都は2021-05-26に国基準へ変更。大阪は2022-04-14に独自基準へ戻った。全国値を全期間同一の臨床基準による重症者数と解釈しない。
- 重大な未解決差異：2021-09-03の厚労省CSV全国値は1,778人。一方、第117回アドバイザリーボード資料に再掲された公式グラフでは同日のピークが2,223人。原因・データ版・集計基準の差は未特定。**CSV値1,778を保持し、グラフ値2,223へ置換しない。**
- 2023-05-09は共通採用終期2023-05-08に合わせて除外。元CSVの値を変更したものではない。

## QA
- 採用日数：1,095
- Date欠損・重複：0
- 全国 `ALL` 欠損：0
- 都道府県47列すべて揃う日：993/1,095
- 都道府県列の欠損：104セル
- 47都道府県がすべて揃う993日について、県別合計と全国 `ALL` は全日一致
- 既存M1分析用MASTERの `Severe_cases` と1,095日すべて一致

## 取得・ハッシュ
- 取得artifact：`mhlw-m1-acquisition-audit-44047413844`
- 取得日時：2026-11-17 17:31:19 JST
- 原CSV SHA-256：`9a3947cf629c12461978b1d847e668ef33500c354dc1892bf7727d3d0a9d5a61`
- 採用CSV SHA-256（復元後）：`cad82552fdce4f67aa45cd78dcae629e8b0d63c244b339f33cfa6ddced7a91b1`
- gzip SHA-256：`c471c12dce234fad28f27f3624d74b66d3b6f2db4f2b9582b1148a851d81bd37`
- artifact ZIP SHA-256：`6814d5e6b3170b9349e4c912a459b41ec675c794a3814f95ebf47a27b02b8643`

分析上の推奨ラベル：「全国・日次重症者数（厚生労働省CSV掲載値）」。2021-09-03の公式CSVと公式グラフの不一致、および自治体別定義差を併記する。


## Pre-May 2020 supplement (multiple documented definitions)

Supplemental file: `national_severe_cases_pre20200509_supplement.csv`

- 2020-04-21: **232** persons under the MHLW status-report category "人工呼吸器又は集中治療室に入院している者" (persons on a ventilator or admitted to an ICU), as of 2020-04-21 12:00.
- 2020-04-30: **328** severe cases, explicitly annotated in the later MHLW daily trend graph.
- These two observations have different indicator definitions and source materials. They are retained in one conceptual supplement only because the user explicitly approved combining different definitions when the difference is documented. They must not be interpreted as a homogeneous daily series.
- No values were estimated from chart bar heights. No missing days were interpolated.
- MHLW's source method for the severe-case trend changed from MHLW-held individual records to municipal website/report aggregation from the 2020-05-08 publication. This source-regime change is separate from the indicator-definition difference above.

Sources:
- MHLW 2020-04-21 status report: https://www.mhlw.go.jp/content/000623854.pdf
- MHLW severe-case trend graph (published 2021-02-10): https://www.mhlw.go.jp/content/10601000/000746793.pdf

Research update recorded: 2026-11-18T15:33:52 JST

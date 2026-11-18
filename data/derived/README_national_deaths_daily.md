# ④ 全国・累積報告死亡者数と日次計上増分

## データ
- 保存ファイル：`national_deaths_daily_20200509_20230508.csv.gz.b64`
- 復元後CSV：`national_deaths_daily_20200509_20230508.csv`
- 復元方法：リポジトリルートで `python scripts/decode_m1_data.py` を実行
- 対象：全国（厚生労働省CSVの `ALL` 列）
- 期間：2020-05-09〜2023-05-08（1,095日）
- 列：`Date`、`Deaths_cumulative`、`Deaths_reported_increment`

## 出典
- 厚生労働省オープンデータ：https://www.mhlw.go.jp/stf/covid-19/open-data_00002.html
- 原CSV：https://covid19.mhlw.go.jp/public/opendata/deaths_cumulative_daily.csv

## 指標の定義と計算
- `Deaths_cumulative`：厚労省CSVの全国累積報告値を保持したもの。人口動態統計の「COVID-19を原死因とする死亡数」とは別系列。
- `Deaths_reported_increment`：累積報告値の連続日差分。計算式は `当日累積値 - 前日累積値`。
- 先頭日2020-05-09は前日値が採用系列にないため空欄（NA）。ゼロ埋めしない。
- この差分は「累積報告死亡者数の計上増分」であり、当日に死亡した人数を示すとは限らない。死亡日別死亡数として扱わない。
- 厚労省注記では、自治体の報道発表とウェブサイト更新時点の違いにより、個別事例の積上げ値と差が生じる場合がある。2022-09-28以降の情報更新日の扱いの変化、2022-09-29/30および2023-03-21の公表資料とCSVの不一致も任意補正しない。
- 2023-05-09は5都道府県の値が欠損し、全国値60,935が前日74,688を下回るため、採用期間から除外。元CSVの値は変更しない。

## QA
- 採用日数：1,095
- Date欠損・重複：0
- 全国累積値欠損：0
- 採用期間内の都道府県47列欠損：0セル
- 日次計上増分：1,094日
- 負の差分：0、ゼロ差分：37
- 最大差分：491（2023-01-12）
- 既存M1分析用MASTERの累積値と1,095日すべて一致
- 既存M1分析用MASTERの日次計上増分と、先頭日のNAを除く1,094日すべて一致
- 欠損補完・補間・推計・負値の切捨て：なし

## 取得・ハッシュ
- 取得artifact：`mhlw-m1-acquisition-audit-44047413844`
- 取得日時：2026-11-17 17:31:19 JST
- 原CSV SHA-256：`4dc69ea34da6bc6ba7874568b7f95560d06d63a4e012d8261f84bdaff00dc7f0`
- 採用CSV SHA-256（復元後）：`2f35538e867fe94de180c7579fbe5a95d0e78d89ad753093f93c78bc013a57e0`
- gzip SHA-256：`113b309f02e6c540deaf9cc9c0e51bf9655cd1fb95ee484581657a835cb281b2`
- artifact ZIP SHA-256：`6814d5e6b3170b9349e4c912a459b41ec675c794a3814f95ebf47a27b02b8643`

分析上の推奨ラベル：「累積報告死亡者数」と「累積報告死亡者数の計上増分（日次差分）」を区別する。

## Pre-May 2020 supplement

Supplemental file: `national_deaths_cumulative_pre20200509_supplement.csv`

- Report date 2020-04-30: cumulative domestic deaths **432**.
- The MHLW report was published 2020-05-01 and states that the 432 total includes persons still undergoing reconciliation.
- The MHLW notes that the source for deaths changed from MHLW-held individual records to counts accumulated from municipal websites/reports from the 2020-04-21 publication. Thus the 2020-04-30 report is already within the municipal-report source regime, but the reconciliation caveat remains.
- Per the research decision dated 2026-11-18 (JST), this observation is retained in the same conceptual cumulative reported-deaths series with the source regime and publication date explicitly recorded.
- No values are supplied for 2020-05-01 through 2020-05-08 because a reconciled, consistently dated daily sequence has not been confirmed. Do not interpolate.
- This is a cumulative reported count, not a count of deaths occurring on 2020-04-30.

Source: https://www.mhlw.go.jp/stf/newpage_11127.html

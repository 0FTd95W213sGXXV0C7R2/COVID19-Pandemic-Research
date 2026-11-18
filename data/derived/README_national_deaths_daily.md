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


## Pre-May 2020 supplement (expanded with daily MHLW reports)

Supplemental file: `national_deaths_cumulative_pre20200509_supplement.csv`

- Primary report-date series: **2020-04-20 to 2020-05-08**, daily observations.
- 2020-04-20 anchor: 186.
- 2020-04-21: 277; daily cumulative difference +91. The 4/21 report states 17 deaths were reported that day and 74 cases under reconciliation were added to the previous total. Therefore +91 is a reporting/accounting increment, not 91 deaths occurring that day.
- 2020-04-30: primary municipal-report cumulative value 432. A separate MHLW status report at 4/30 12:00 gave 415; both are preserved as separate rows with different source regimes and roles.
- 2020-04-21 also has a separate 12:00 legacy-source snapshot of 186, preserved as an alternate row.
- 2020-04-26: the MHLW index's serial range (339–351) overlaps the prior day's range (335–348). The published endpoint 351 is retained, and the difference from the previous primary cumulative value is +3. Do not infer the daily increment from the serial-number range.
- 2020-05-08 release was published on 2020-05-09. The supplementary file uses **report date** as its date key and separately records publication date. Alignment with the existing open-data CSV's `Date` field must be checked before physically concatenating files.
- Primary rows calculate `deaths_reported_increment` as current cumulative report value minus the previous calendar day's primary cumulative value. Alternate snapshots have a blank increment.
- The difference remains a reporting/accounting increment, not necessarily deaths occurring on that calendar day.
- Source regime changes on the 2020-04-21 release from MHLW-held individual records to municipal website/report aggregation. This is documented per row.
- All primary cumulative values are retained as published; no interpolation or correction has been applied.

Sources:
- MHLW April 2020 press-release index: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00191.html
- MHLW May 2020 press-release index: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000121431_00192.html
- 2020-04-21 release: https://www.mhlw.go.jp/stf/newpage_10971.html
- 2020-04-25 release: https://www.mhlw.go.jp/stf/newpage_11047.html
- 2020-04-30 release: https://www.mhlw.go.jp/stf/newpage_11127.html
- 2020-05-02 release: https://www.mhlw.go.jp/stf/newpage_11163.html
- 2020-05-03 release: https://www.mhlw.go.jp/stf/newpage_11165.html
- 2020-05-07 release: https://www.mhlw.go.jp/stf/newpage_11198.html
- 2020-05-08 release: https://www.mhlw.go.jp/stf/newpage_11228.html
- MHLW 2020-04-21 status PDF: https://www.mhlw.go.jp/content/000623854.pdf
- MHLW 2020-04-30 status PDF: https://www.mhlw.go.jp/content/000626590.pdf

Research update recorded: 2026-11-18T15:33:52 JST

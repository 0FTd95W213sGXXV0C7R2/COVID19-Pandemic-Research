# FDMA 救急搬送困難事案・週次データ辞書

## 出典・構築
- 発行主体：総務省消防庁
- 公式ページ：https://www.fdma.go.jp/disaster/coronavirus/post-1.html
- 公式Excel：https://www.fdma.go.jp/disaster/coronavirus/items/coronavirus_data.xlsx
- 原本SHA-256：bc586c494b32dd83c8d79c1ffd736e828ca208c93a7932667c5a606e1a6a4101
- 粒度：週次
- 単位：件
- 収録単位：調査対象52消防本部および52本部合計
- 構築：公式Excelの4シートから直接抽出。過去のミラーCSV・加工CSVは入力に不使用。

## 系列
| metric_code | 公式シート | 意味 |
|---|---|---|
| transport_difficulty_overall_current | 搬送困難事案（今回） | 今回の全体系列 |
| transport_difficulty_overall_previous_year | 搬送困難事案（前年同期） | 前年同期比較用の別系列。今回系列と週番号で対応し、開始日は364日差 |
| transport_difficulty_covid_suspected_current | うちコロナ疑い事案（今回） | 今回のうちコロナ疑い事案 |
| transport_difficulty_non_covid_suspected_current | うち非コロナ疑い事案（今回） | 今回のうち非コロナ疑い事案 |

## 主な列
| 列 | 定義 |
|---|---|
| week_index | シート内の週番号。シートごとに1から付番 |
| period_start_date | 見出し開始日。初週の令和年表示を基準にし、全見出しの月日・曜日と照合 |
| period_end_date | 終了日見出しが7日間の期待期間と一致した場合のみ設定。不一致の場合は空欄 |
| period_end_date_expected | 開始日から6日後の期待終了日。検証用であり、印刷見出しの置換ではない |
| period_end_date_printed | Excel見出しに印字された終了日 |
| date_header_status | matched または printed_end_date_or_weekday_mismatch |
| raw_week_header | Excelの週見出し原文 |
| prefecture | 消防本部所在地の都道府県。縦方向に結合されたExcelセルは、結合範囲の先頭セルから値を取得 |
| prefecture_value_source | 都道府県値が明示セルか、原本の縦結合セルから取得されたか |
| fire_department | 消防本部名。合計行は「52本部合計」 |
| aggregation_level | fire_department または 52_fire_department_total |
| value | 件数。原本空欄は空欄のまま、明示的な0は0 |
| observation_status | reported_numeric_value、reported_zero、blank_in_source、cached_excel_total_formula 等 |
| paired_current_week_start_date | 前年同期シートの週番号に対応する今回シートの開始日 |
| source_cell | 原本Excelのセル番地 |
| source_formula | 合計行の原本数式（数式がある場合） |
| source_file_sha256 | 原本ファイルのSHA-256 |

## 解釈上の制約
- 調査対象は52消防本部であり、日本全国の全消防本部の悉皆集計ではない。
- 救急搬送困難事案は受入照会・現場滞在に関する指標であり、搬送拒否・未搬送・治療不能と同義ではない。
- 空欄と0を区別する。補間・ゼロ埋めはしない。
- 全体シートの2022-03-07開始週、秋田市消防本部の値は原本空欄。コロナ疑い・非コロナ疑いシートは両方0。
- 全体シートの2024-04-01開始週の印刷見出しは終了日が2024-04-08と記載されるが、7日間の連続週として期待される終了日は2024-04-07。原文を保持し、period_end_dateは空欄としている。
- COVID疑い・非COVID疑いの分類は消防庁原本の分類であり、患者の確定診断区分と同一と断定しない。
- 消防庁の説明資料は正式調査開始を2020-04-27としている一方、Excelには2020-03-30〜2020-04-26の4週分にも数値がある。これらの収集経緯は未確認のため、source_series_phaseで正式調査開始前として識別し、正式調査期間と同条件と仮定しない。
- 2024-04-08から新様式となり、COVID疑い事案数（内数）は調査中止。全体系列は継続するが、旧様式と新様式の切替点として識別する。月報告も終了。
- 週次データを日次に補間しない。時系列上の関連は因果関係を意味しない。

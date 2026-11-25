# Project Status

最終更新：2026-11-25 JST

> **進捗・取得状況の正本はGitHubのみ。** 30項目のファイル単位の根拠・判定は [docs/GITHUB_CANONICAL_PROGRESS_20261125.md](docs/GITHUB_CANONICAL_PROGRESS_20261125.md) を参照。Notion・会話履歴の進捗記述は過去時点の履歴であり、現行状態の判定には使用しない。

## Current Status（2026-11-25 JST）

| Area | GitHub上の確認状況 |
|---|---|
| Epidemiology / medical burden | 新規陽性者・重症者・死亡者・病床使用・RtのファイルとREADMEあり。系列ごとに監査・比較可能性の未解決事項あり |
| Emergency access | 消防庁原本、週次longデータ、監査成果物あり。明示されたソース問題を残す |
| Non-COVID healthcare access | 3研究の公表集計値47行をCSV化。個票・原データではなく、研究ごとの制約あり |
| Resource allocation ethics | Mori et al.本文由来の監査記録あり。補足ファイルの実監査は未完了 |
| Patient/family autonomy and dignity | 現在確認できるのは主に出典登録。構造化された証拠データは未整備 |
| Healthcare worker burden and reciprocity | 現在確認できるのは主に出典登録。構造化された証拠データは未整備 |
| Policy / governance | 出典候補はあるが、政策時系列・通知・議事録の体系的整理は未完了 |
| Integration and recommendations | 未完了 |

## Existing Data Assets

- 日本版疫学5指標・流行波データ：GitHub `MASTER_01_Epidemiology/` に集約（2026-11-18）
- 正式Excel `MASTER_01_Epidemiology.xlsx`：Google Drive上の保護対象ファイル。GitHubには複製せず、変更・移動していない
- OxCGRT
- 消防庁救急搬送関連資料
- NCC院内がん登録
- 厚生労働省レセプト関連資料

※ファイルの現存状態・最新版・再実行可能性は個別に確認する。

## Immediate Priorities

1. M1の実証結果を確定する。
2. E1の倫理的論点を3〜5件抽出する。
3. M1・M2とE1・E2の証拠を接続する。
4. 将来対策の提案を証拠から導出する。

## Restrictions

- 保護対象MASTERを変更・削除しない。
- 原データを無断でGitHubにアップロードしない。
- 未検証の分析結果を確定結果として扱わない。

## GitHub Actions: MHLW M1 Acquisition

記録日時：2026-11-17 14:45:29 JST

- `scripts/acquire_mhlw_m1.py` を追加。登録済みの厚労省CSV 4系列を取得し、ファイルサイズ・SHA-256・文字コード・列名・行数・欠損数・日付候補・重複日を監査する。
- `.github/workflows/mhlw-m1-acquisition-audit.yml` を追加。GitHub Actionsの `workflow_dispatch` による手動実行のみ。自動定期実行は設定していない。
- 成果物は14日間のActions Artifactとして保存し、Gitへの原データコミットは行わない。既存の `data/raw/*` のgitignoreも維持。
- 読み込み時の定義確認や分析採用可否は別工程。特に入院関連CSVは既知の乖離が解消するまで監査専用とし、主分析へ投入しない。
- 2ファイルはGitHub上で作成済み・再取得確認済み。
- **未実施**：GitHub Actionsの初回実行。GitHubコネクタからworkflow_dispatchを呼び出す機能がないため、GitHubのActions画面から初回の手動実行が必要。実行成功・取得成功とはまだ判定しない。

## MHLW M1 初回GitHub Actions実行結果

記録日時：2026-11-17 14:49:06 JST

- Workflow run #1（ID: 44026425372）は `completed / success`。全5ステップ成功。
- Artifact `mhlw-m1-acquisition-audit-44026425372`（421,494 bytes）を取得・展開し、4 CSVと監査JSON/Markdownを確認。Artifactの有効期限は2026-12-01。
- 4系列すべてHTTP取得成功、空ファイルではなく、取得時のSHA-256とArtifact内ファイルのSHA-256が一致。CSV構造監査も完了。

| CSV | 行数 | 列数 | 日付範囲（独立して日付解析） | 欠損 |
|---|---:|---:|---|---|
| newly_confirmed_cases_daily.csv | 1,209 | 49 | 2020-01-16–2023-05-08 | 0セル |
| severe_cases_daily.csv | 1,096 | 49 | 2020-05-09–2023-05-09 | 北海道1、青森1、福島1、埼玉2、神奈川101、沖縄2 |
| deaths_cumulative_daily.csv | 1,096 | 49 | 2020-05-09–2023-05-09 | 北海道1、埼玉1、千葉1、愛媛1、佐賀1 |
| requiring_inpatient_care_etc_daily.csv | 1,096 | 145 | 2020-05-09–2023-05-09 | 複数列に欠損あり。岐阜「To be confirmed」は全1,096行欠損、北海道3列各225、三重3列各241、神奈川2列各102など |

- 全CSVはUTF-8 BOM付き。各ファイルで日付は一意（YYYY/MM/DDとして独立解析）、重複日なし。各行の列数はヘッダーと一致。
- 注意：初回スクリプトの監査JSONは日付文字列を辞書順でmin/max判定していたため、JSON内の日付範囲は信頼できない。上表の日付範囲はArtifact内CSVを別途日付として解析した結果。
- この問題を修正し、日付形式を解析して時系列順にmin/max・重複を判定するよう `scripts/acquire_mhlw_m1.py` を更新した（commit: `1ec41d19cdd1d8a97c3d73efb08979e3ae6aca57`）。修正版による再実行は未実施。
- 入院関連CSVは既知の週次資料との乖離が未解決のため、引き続き監査専用。欠損の意味・定義変更・系列の比較可能性も未確認であり、今回の成功は分析採用の承認を意味しない。
- 原データはArtifact内にのみ保存。Gitへのコミットなし。


## MHLW M1 日付監査コード修正の確認

記録日時：2026-11-17 14:51:09 JST

- GitHub mainブランチの `scripts/acquire_mhlw_m1.py` を再取得して確認した。
- `%Y/%m/%d`、`%Y-%m-%d`、`%Y%m%d` を日付型に変換し、`min(dates)` / `max(dates)` で時系列上の最小日・最大日を求める実装を確認した。
- 重複日も文字列ではなく解析済み日付で判定する実装を確認した。
- したがって、前回記録した辞書順比較の不具合はコード上修正済み。ただし、修正版ワークフローの再実行は未実施であり、修正版の実行結果は未確認。
- 次の作業：GitHub Actionsの「MHLW M1 acquisition and audit」を手動で再実行し、新しいArtifactのJSONに日付範囲が正しく出力されることを確認する。
- 再実行後も、定義・収録範囲・単位・欠損の意味を確認するまでは統計分析に進まない。入院関連CSVは既知の不一致が解消するまで監査専用とする。


## MHLW M1 修正版ワークフロー再実行結果

記録日時：2026-11-17 14:53:51 JST

- Workflow run: 44027107276
- Job: 133849975652
- 結果：全ステップ success。取得・監査・Artifact upload が完了。
- Artifact ID: 14303292238
- Artifact: mhlw-m1-acquisition-audit-44027107276.zip
- Artifact size: 421,526 bytes
- Artifact SHA-256: 1dacf78da245c94e079ac592c2592e5103cb7b7b48223a48b00be58d2b56f81c
- Artifact retention expiry: 2026-12-01 05:52:30 UTC（14日間）

### 修正版監査JSONで確認した構造

| ファイル | 行数 | 列数 | 日付範囲 | 重複日 | 未解析日 |
|---|---:|---:|---|---:|---:|
| newly_confirmed_cases_daily.csv | 1,209 | 49 | 2020-01-16–2023-05-08 | 0 | 0 |
| severe_cases_daily.csv | 1,096 | 49 | 2020-05-09–2023-05-09 | 0 | 0 |
| deaths_cumulative_daily.csv | 1,096 | 49 | 2020-05-09–2023-05-09 | 0 | 0 |
| requiring_inpatient_care_etc_daily.csv | 1,096 | 145 | 2020-05-09–2023-05-09 | 0 | 0 |

- 4ファイルともHTTP 200、UTF-8 BOM（utf-8-sig）で取得。
- Artifact内CSVを独立に再ハッシュし、4件すべて監査JSON記載のSHA-256と一致することを確認。
- newly_confirmed_cases_daily.csv：欠損セル0。
- severe_cases_daily.csv：欠損は北海道1、青森1、福島1、埼玉2、神奈川101、沖縄2。
- deaths_cumulative_daily.csv：欠損は北海道1、埼玉1、千葉1、愛媛1、佐賀1。
- requiring_inpatient_care_etc_daily.csv：北海道各3指標225、神奈川県2指標102、山梨県各3指標2、岐阜県入院中1・退院225・確認中1096、三重県各3指標241の欠損。既知の系列不一致もあるため監査専用のままとする。
- 欠損値の意味は未確定。補完・ゼロ置換を行わない。
- 日付の辞書順比較修正後の監査結果で、4系列すべての期間・重複・未解析日が正常に出力された。これにより日付処理修正を実行結果でも確認した。
- この確認は構造監査であり、公式定義、観測時点、単位、都道府県別収録範囲、改定履歴、既存MASTERとの比較可能性を証明するものではない。
- raw CSVはGitHubリポジトリにコミットせず、Actions Artifact内のみ（14日間）に保存。

### 次工程

1. MHLW公式資料で各系列の定義、日付の意味、単位、集計・報告方法、改定履歴を確認。
2. 既存MASTERの対応系列と項目単位で照合し、差異・欠測・期間差を記録。
3. 3つのM1系列について利用可否を判定する。入院関連CSVは既知の不一致解消まで分析投入禁止。
4. 監査完了前に統計分析へ進まない。


### 再実行Artifact内CSVの個別SHA-256

記録日時：2026-11-17 14:54:11 JST

| ファイル | サイズ(bytes) | SHA-256 |
|---|---:|---|
| newly_confirmed_cases_daily.csv | 202,245 | 6493df56c3b46ee15bae36e69de1c176562e8535efd95b0aa15452d61e6ad9d7 |
| severe_cases_daily.csv | 130,329 | 9a3947cf629c12461978b1d847e668ef33500c354dc1892bf7727d3d0a9d5a61 |
| deaths_cumulative_daily.csv | 200,118 | 4dc69ea34da6bc6ba7874568b7f95560d06d63a4e012d8261f84bdaff00dc7f0 |
| requiring_inpatient_care_etc_daily.csv | 676,410 | 702f451366d76d18a3435e0e794ae90e534e658793fbef301759db05c8d832a4 |

各SHA-256はArtifactから展開した実ファイルを独立に計算し、監査JSONの値と一致することを確認。


## M1 定義監査：厚労省3系列の一次資料照合（暫定）

記録日時：2026-11-17 14:56:35 JST

### 照合対象・公式根拠
- 厚労省オープンデータ一覧：https://www.mhlw.go.jp/stf/covid-19/open-data.html
- 厚労省COVID-19ダッシュボード注記：https://covid19.mhlw.go.jp/extensions/public/parts/current_situation.html
- 2021-09-03事務連絡（HER-SYS切替）：https://www.mhlw.go.jp/content/10900000/000830314.pdf

### New_cases
- CSV構造監査：1,209行×49列、Date 2020-01-16〜2023-05-08、欠損・重複日・未解析日なし。
- 2020-05-08公表分から、国内事例（チャーター便除く）のデータ源を厚労省が把握した個票の積み上げから自治体ウェブサイト公表値の積み上げへ変更。
- 2021-09-13以降は、報告後14日間を自治体公表値、15日目以降をHER-SYSデータに切替。自治体公表値は必ずしも報告日ベースではなく、HER-SYS値は報告日ベースだが入力遅延により当日・翌日は未確定の場合がある。
- ダッシュボード注記上、新規陽性者数は個別事例（再陽性例を含む場合あり）の積み上げであり、前日累計との差分とは一致しない場合がある。
- 判定：系列全体を単一の同質な測定方式とみなさない。2020-05-08、2021-09-13の変更と、報告後14日/15日目の情報源差を分析上明示する。

### Severe_cases
- CSV構造監査：1,096行×49列、Date 2020-05-09〜2023-05-09、重複日・未解析日なし。欠損セル108（北海道1、青森1、福島1、埼玉2、神奈川101、沖縄2）。
- 厚労省ダッシュボード注記では、一部自治体の重症者数は自治体独自基準による公表値を使用すると説明。
- 判定：都道府県間で臨床的な重症定義が完全に均一であるとは確認できない。全国合計を完全に同一基準の重症者数と断定しない。欠損補完なし。定義変更時点の追加確認が必要。

### Deaths_cumulative
- CSV構造監査：1,096行×49列、Date 2020-05-09〜2023-05-09、重複日・未解析日なし。欠損セル5（北海道1、埼玉1、千葉1、愛媛1、佐賀1）。
- CSVの列構成はDate、ALL、47都道府県で、ファイル名・既存DB定義どおり累積死亡者数系列。
- 判定：New_deaths（日別死亡数）と同一視しない。差分化する場合も過去訂正、負の差分、初期値、基準日を先に監査する。今回確認した公式注記だけでは死亡系列固有の算定・訂正履歴を確定できていない。

### 既存MASTERとの比較上の重要な未解決点
- 今回のActionsで取得したのは deaths_cumulative_daily.csv（累積値）。過去の旧Notion台帳には number_of_deaths_daily.csv（New_deaths候補）が別URLで記録されている。別系列として扱い、同一視しない。
- MASTER本体ファイルは今回の作業環境で読み取っていないため、行単位・値単位の照合は未実施。既存Notion記録だけでは最新ファイルの実データを再検証したことにならない。
- 入院等CSVは、2022年9月の自治体報告変更注記に加え、2022-08-24/31週次資料との大きな乖離が未解決。監査専用・主分析投入保留を継続。

### Notion出典DB更新
- 公式ダッシュボード注記、2021-09-03 HER-SYS切替事務連絡、旧MASTERのNew_deaths出典候補を追加登録。
- New_cases、Severe_cases、Deaths_cumulativeの既存レコードに今回の定義・欠損監査結果を反映。
- 新規登録URLは原資料確認済み。ただし number_of_deaths_daily.csv は候補として登録したのみで、今回未取得・未監査。

### 次工程
1. 既存MASTER①の実ファイルを読み取り専用で取得し、5変数の列定義・日付・値・欠損・元出典を照合する。
2. 特に New_deaths と今回の Deaths_cumulative の関係を特定する。number_of_deaths_daily.csv の現行配布状態を確認するまでは追加取得・差分化しない。
3. New_cases は定義変更前後、Severe_cases は自治体基準差・欠損、Deaths_cumulative は累積値の訂正履歴を個別に監査する。
4. 入院等系列は乖離原因が解明されるまで統計分析に戻さない。


## Research policy reset — 2026-11-17 15:53 JST

The new research plan supersedes the previous "Immediate Priorities" and any instruction to compare or repair the legacy MASTER.

- The legacy MASTER, its values, source inventory and derived analyses are historical records only; they are not inputs, baselines, target values or acceptance criteria for the new study.
- Existing data assets and prior acquisition results are not presumed valid or adopted. Each candidate source must be independently reselected from the research questions and re-acquired/verified as needed.
- The previous MHLW acquisition workflow is retained as an engineering prototype only. Its four downloaded files are not automatically designated as the new study's canonical variables or analysis dataset.
- New work starts with Phase 1: prioritize the research questions/domains and define indicator specifications (population, unit, date basis, definition, coverage, source and limitations).
- Bulk acquisition and statistical analysis are paused until Phase 1 is approved. No old-MASTER audit, value matching or repair is the next task.
- Notion research-plan page contains the full redesigned analysis policy: https://app.notion.com/p/41bffd9b97358133a48de75d8b2215e9
- GitHub `RESEARCH_PLAN.md` was rewritten to match this policy. Commit: `cca9a3728c860ae2aaa0d20c8d53270cc71f8d5f`.


## A3 e-Stat monthly mortality acquisition — 2026-11-17 16:10 JST

- Official e-Stat table 0003411700 exposes the required dimensions: month, sex, simplified cause-of-death classification and annual time axis; years 2020–2023 are present. COVID-19 cause code: 22201.
- The e-Stat API requires a registered application ID (appId). API documentation: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0
- Added `scripts/acquire_estat_a3.py` and manual workflow `.github/workflows/estat-a3-acquisition.yml`.
- The script requests 48 month cells plus four annual total cells, preserves raw API JSON, writes a normalized CSV and SHA-256 manifest, and stops on any missing/duplicate/non-numeric cell or annual mismatch.
- The workflow expects the GitHub Actions repository secret `ESTAT_APP_ID`; raw data are uploaded as a 14-day artifact and are not committed to Git.
- **Pending:** the secret has not been configured and the workflow has not been executed. Therefore, no monthly values have been acquired or validated yet.
- Do not treat A3 as data-complete until all 48 values are present and annual reconciliation passes.


## MASTER 01 Epidemiology — GitHub organization (2026-11-18)

- Japanese epidemiology five-indicator data and epidemic-wave information previously scattered under `data/derived/`, `data/derived/rt/`, `docs/methods/`, and `docs/audits/` have been consolidated under `MASTER_01_Epidemiology/`.
- Subdirectories: `data/01_New_cases/`, `02_Bed_occupancy/`, `03_Severe_cases/`, `04_Deaths/`, `05_Rt/`, `06_Waves/`, `methods/`, `audits/`, and `metadata/`.
- A dedicated README, file manifest, and data dictionary were added.
- Existing data blobs were moved without changing their contents. Only path references in methodology documents were updated.
- The protected Excel workbook remains in Google Drive and was not copied, modified, or moved.
- The Rt reconstruction remains separate from the legacy MASTER Rt series; the wave boundaries remain provisional and W09 remains ongoing/unconfirmed.

# Project Status

最終更新：2026-11-17 JST

## Current Status

| Area | Status |
|---|---|
| M1 Medical Burden | 既存データ・分析あり。結果の確定作業が必要 |
| M2 Healthcare Access | 既存資料あり。系列ごとの検証状態を整理する |
| E1 Ethics and Equity | 評価枠組みあり。根拠付き論点の抽出が必要 |
| E2 Transparency | 資料候補あり。証拠整理が必要 |
| I1 Integration | 未完了 |
| C1 International Comparison | 比較可能性の確認が必要 |
| F1 Future Policy | モデル案あり。証拠との対応づけが必要 |

## Existing Data Assets

- 日本版疫学MASTER
- 流行波MASTER
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

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

# COVID-19 Pandemic Research

新型コロナウイルス感染症パンデミックにおける医療面・倫理面の問題を、既存データと公的資料に基づいて分析し、将来のパンデミック対策を検討する研究。

## Research Objectives

1. パンデミックによる医療負荷を検証する。
2. COVID-19以外の医療への影響・アクセスの変化を検証する。
3. 権利、公平性、自律性に関する倫理的課題を整理する。
4. 政策決定の透明性と説明責任を検討する。
5. 医療面・倫理面の知見を統合し、将来の対策を提案する。

## Repository Structure

- `MASTER_01_Epidemiology/`: 日本版・疫学5指標と流行波情報のGitHub集約先
- `data/`: 全研究共通のデータ管理とメタデータ
- `src/`: 再利用可能な分析コード
- `analysis/`: 研究課題ごとの分析
- `notebooks/`: 探索・説明用ノートブック
- `results/`: 確定した分析結果
- `docs/`: 研究設計・方法・証拠・判断記録
- `audit/`: データ取得・検証・ハッシュ記録
- `tests/`: テスト

## Data Policy

- **All subsequent data collection must be rebuilt from original sources.** Existing processed datasets and historical extracts are reference/audit material only, not inputs to new canonical datasets, unless the user explicitly approves an exception. See [DATA_COLLECTION_REBUILD_POLICY.md](docs/DATA_COLLECTION_REBUILD_POLICY.md).
- 原データおよび保護対象MASTERは、利用条件と保全条件を確認するまで登録しない。
- 取得・加工・監査・採否の状態を区別し、未検証の成果物を確定データとして扱わない。

## Research Records and Source of Truth

- **研究の取得状況・整理状況・進捗の唯一の正本は、このGitHubリポジトリとする。**
- 現行の進捗スナップショット：[docs/GITHUB_CANONICAL_PROGRESS_20261125.md](docs/GITHUB_CANONICAL_PROGRESS_20261125.md)
- プロジェクト全体の短い状態：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- 参照文献・参考文献・データ取得元の正本は `docs/references/references_master.csv` とする。管理方法は [docs/references/README.md](docs/references/README.md) を参照。
- 新規出典・書誌情報・URL・参照日（JST）、取得コード、監査結果、データ辞書、判断理由はGitHubに記録する。
- Notionは研究目的・倫理的判断・研究設計等の参照用とし、進捗・取得状況の二重管理には使用しない。過去のNotion進捗記録は履歴であり、現在の状態を示す正本ではない。

## Daily indicator analysis files

GitHub is the canonical basis for subsequent analysis. Japanese epidemiology indicators and wave information are organized under [`MASTER_01_Epidemiology/`](MASTER_01_Epidemiology/README.md). The folder contains the five indicators, weekly wave aggregation, provisional wave boundaries, methods, audits, and a dedicated file manifest/data dictionary. Existing files are not automatically approved for new canonical analysis; follow the rebuild policy and each dataset's audit status.

## Research workflow

- The integrated operating procedure for GitHub, source acquisition, validation, and analysis is documented in [RESEARCH_WORKFLOW_PLUGIN_INTEGRATION.md](docs/RESEARCH_WORKFLOW_PLUGIN_INTEGRATION.md).

# Data Management Policy

## 1. General Policy

GitHubではデータ本体よりも、出典・定義・取得状況・検証履歴を管理する。

## 2. Directory Rules

- `metadata/`: データ台帳・変数定義・ファイル一覧
- `raw/`: 利用許諾と保全条件を確認した原データ
- `processed/`: 再現可能な手順で作成した加工データ

## 3. Required Metadata

各データについて、可能な範囲で以下を記録する。

- データ名
- 提供機関
- 出典URL
- 取得日
- 対象期間
- 変数定義・単位
- 更新頻度
- 欠測の扱い
- 加工履歴
- 利用条件
- ファイルハッシュ
- 検証状態

## 4. Protected Data

保護対象MASTERおよび既存の原データは、許可なく移動・変更・削除・複製しない。利用条件が未確認のデータはGitHubに登録しない。

## 5. Reproducibility

分析に使用したデータの版、処理コード、パラメータ、実行環境を記録する。欠測補間やゼロ埋め等の処理は、根拠と方法を明示する。


## 6. Metadata Ledgers

The following CSV files are the metadata records of this repository:

- `metadata/source_registry.csv`: source institutions, canonical URLs, source roles, acquisition and verification states.
- `metadata/data_dictionary.csv`: variable definitions, units, periods, frequency, missingness rules, and comparability limitations.
- `metadata/file_manifest.csv`: file-level inventory for research assets stored outside or inside this repository.

### Status semantics

- `used_in_existing_master`: recorded in the existing research workflow; does not imply a fresh file-level audit.
- `reference_used`: source consulted for definitions or methodology, not necessarily downloaded as a dataset.
- `reference_only`: source is documented, but the underlying data file has not been confirmed as downloaded.
- `partially_verified`: some checks are recorded; definition, coverage, or independent reproduction remains incomplete.
- `series_definition_review`: the source is known, but the exact adopted series or its definition still requires reconciliation.
- `verified_in_notion`: verification is recorded in the cited Notion research log; it is not a claim of a new verification in this GitHub commit.

### File manifest policy

`file_manifest.csv` intentionally contains only its header at initialization. Add an asset only after confirming its current existence, exact filename/path, version, and (where possible) SHA-256. Do not guess paths or hashes. Protected MASTER files must remain in their existing storage location; the manifest records metadata only and does not authorize copying them into GitHub.

### CSV conventions

- UTF-8 encoding, comma delimiter, first row as header.
- Empty fields mean unknown or not yet recorded; they do not mean zero.
- Dates use ISO 8601 where possible.
- Do not silently overwrite historical acquisition records; add a new record for a new acquisition/version.
- The Notion research records remain the detailed source of truth for acquisition history and decisions.


## 7. MASTER 01 Epidemiology

Japanese COVID-19 epidemiology data for the five indicators and epidemic-wave information are consolidated in the repository-root directory `MASTER_01_Epidemiology/`. Refer to its README, local data dictionary, and file manifest. The shared `data/metadata/` ledgers remain repository-wide and are not moved because they also describe non-epidemiology research assets.

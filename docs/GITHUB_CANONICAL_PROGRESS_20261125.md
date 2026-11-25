# GitHub基準・研究資料30項目の取得／整理状況

- 基準日時：2026-11-25（日本時間）
- 正本リポジトリ：https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research
- 判定対象：mainブランチのファイルツリー、README、データ辞書、出典マニフェスト、取得・品質監査記録
- 判定原則：Notionの進捗記述・会話履歴・外部サイトに資料が存在するという事実だけでは取得済みにしない。GitHub内に実ファイルまたは実行可能な取得・監査成果がある場合に限り、その範囲を記録する。

## 1. 判定区分

| 区分 | 意味 |
|---|---|
| 整理済み（監査記録あり） | GitHubに加工データと監査結果があり、監査範囲が文書化されている |
| 一部整理済み | GitHubに一部の集計値・データ・資料があるが、必要範囲全体や最終監査は未完了 |
| 原資料あり・整理中 | 原本・スナップショットは保存されているが、変数統合や比較可能性の確定が未完了 |
| 出典記録のみ | 出典・書誌情報・URL等はあるが、対応するデータ／本文抽出物をGitHubで確認できない |
| 未確認 | 対応する資料・データをGitHub上で確認できない |

「GitHubにファイルがある」ことと「研究で採用可能」なことは別である。監査中・保留中のデータを確定データとして扱わない。

## 2. 30項目の状況

| No. | 収集対象 | GitHub上の確認物 | 現在の整理状況 | 未完了事項 |
|---:|---|---|---|---|
| 1 | 希少資源配分の実態調査（Mori et al.） | `docs/audits/MORI_2026_SUPPLEMENTARY_AUDIT.md` | 一部整理済み | 論文本文の集計結果・変数は整理済み。補足XLSX/DOCXの実ファイル取得・照合は未完了 |
| 2 | 医療機関の資源配分方針・倫理相談体制 | `docs/medical_frontline_impacts/source_register_20261119.md`、`docs/references/references_master.csv` | 出典記録のみ | 院内指針、倫理相談、複数職種レビュー等の実施状況を示す資料・データの抽出が必要 |
| 3 | 病床・ICU・ECMO・人工呼吸器の稼働状況 | `data/raw/mhlw/weekly_inpatient_survey/`、`data/raw/mhlw/gmis_all_snapshots/`、`data/audits/mhlw/` | 原資料あり・整理中 | 週次Excel171件、G-MISスナップショット43件と複数監査を保存。変数クロスウォークは候補段階。ICU/ECMO/MVを含む統合系列は未確定 |
| 4 | 面会制限に関する調査・論文 | `docs/references/references_master.csv` | 出典記録のみ | 面会制限の期間・対象・例外・代替手段をGitHub上のデータ表に抽出する必要 |
| 5 | 患者・家族の心理的負担・意思決定参加 | `docs/references/references_master.csv` | 出典記録のみ | 患者・家族本人の回答・質的結果を出典本文から抽出し、対象・方法・限界を記録する必要 |
| 6 | 緩和ケア・終末期医療・ACP | `docs/references/references_master.csv`、`docs/medical_frontline_impacts/source_register_20261119.md` | 出典記録のみ | 緩和ケア・ACP・看取り支援の実態を示す資料・結果の抽出が必要 |
| 7 | 救急搬送困難事案 | `data/raw/fdma/emergency_transport/coronavirus_data.xlsx`、`data/processed/fdma/emergency_transport/weekly_long.csv`、`data/audits/fdma/emergency_transport/`、`docs/audits/FDMA_WEEKLY_DATA_AUDIT.md` | 整理済み（監査記録あり） | 週次長形式データと詳細監査あり。監査ステータスは `PASS_WITH_EXPLICIT_SOURCE_ISSUES`。2022-03-07の不完全区分、週末日見出し不一致、2024年度の調査方式変更等を明示して最終採否を確定する |
| 8 | 外来・入院・診断別の医療利用 | `data/processed/non_covid_access/article_reported_aggregate_evidence.csv`、`data/metadata/non_covid_access/source_manifest.json` | 一部整理済み | 26病院研究の論文報告集計値は抽出済み。MDV等の個票・病院原データは公開されていない。全国月次系列ではない |
| 9 | 手術・検査・治療の延期・中止 | 同上、`docs/audits/non_covid_access/initial_source_extraction_audit.md` | 一部整理済み | 選択的手術延期研究の公表集計値を抽出済み。自己申告Web調査であり、手術実績統計ではない。補足資料・推定値の区別を保持する |
| 10 | 受診回避・服薬中断・疾患悪化 | 同上 | 一部整理済み | Yoshida/JACSISの公表集計値を抽出済み。参加者個票は非公開。自己申告・横断調査の制約を保持する |
| 11 | 医療従事者の感染・欠勤 | `docs/medical_frontline_impacts/source_register_20261119.md`、`docs/references/references_master.csv` | 出典記録のみ | 感染・欠勤数を含む原資料の取得と、対象職種・施設・分母の抽出が必要 |
| 12 | 労働時間・休暇・人員不足 | 同上 | 出典記録のみ | 時間外労働・休暇・人員配置の実測値を示す資料の取得・構造化が必要 |
| 13 | 医療従事者の心理的負担・moral distress | 同上 | 出典記録のみ | 論文候補の結果・尺度・対象者・回答率をGitHub上に構造化する必要 |
| 14 | PPE・補償・組織的支援 | 同上 | 出典記録のみ | PPE供給・補償・休暇・心理支援の実施状況を示す数値・記述結果の抽出が必要 |
| 15 | 新規陽性者数 | `MASTER_01_Epidemiology/data/01_New_cases/national_new_cases_daily_20200116_20230508.csv`、同README | 整理済み（監査記録あり） | 1,209日・日付重複/欠損なし等のQA記録あり。報告方式の変更を期間別に扱い、新規の原資料再取得方針との整合を最終確認する |
| 16 | 新規死亡者数 | `MASTER_01_Epidemiology/data/04_Deaths/` 配下のCSV/B64・README | 一部整理済み | 累積報告値と日次計上増分を区別したデータあり。日次差分は死亡日別死亡数ではない。2020年5月以前の補足値も異なる報告方式を分けて保持 |
| 17 | 入院患者数 | `data/raw/mhlw/weekly_inpatient_survey/`、`data/raw/mhlw/gmis_all_snapshots/`、各監査JSON | 原資料あり・整理中 | 週次171ブック（2020-12-23〜2024-03-27）とG-MIS 43スナップショット（2021-12-01〜2024-03-06）あり。列構造・定義が複数あり、単一の確定系列には未統合 |
| 18 | 重症患者数 | `MASTER_01_Epidemiology/data/03_Severe_cases/`、週次調査の原本・監査 | 一部整理済み | 日次系列1,095日と異なる定義の初期補足値あり。自治体基準差・2021-09-03の公式CSVと公式グラフの不一致を未解決事項として保持 |
| 19 | ICU患者数 | `docs/medical_frontline_impacts/source_register_20261119.md`、MHLW/G-MIS関連資料 | 出典記録のみ | ICU患者数の連続・再現可能な実データ系列をGitHub上で確認できない。G-MIS病床スナップショットをICU患者数と読み替えない |
| 20 | ECMO・人工呼吸器管理患者数 | `docs/medical_frontline_impacts/source_register_20261119.md` | 出典記録のみ | CRISIS/ECMOnet等の出典候補・制約は記録済み。再現可能な実データ系列の取得・監査は未完了 |
| 21 | 実効再生産数（Rt） | `MASTER_01_Epidemiology/data/05_Rt/EpiForecasts_Japan_Rt_20200830_20220331.csv`、README | 一部整理済み | 579日分（2020-08-30〜2022-03-31）の履歴再構成CSVあり。411コミット由来の中央値集約。上流R実装との完全一致は未検証。2022-04-01以降の東洋経済系列は未取得・未接続 |
| 22 | 緊急事態宣言・重点措置 | `docs/references/references_master.csv`、研究方針文書 | 出典記録のみ | 地域別の発出・開始・変更・終了を機械可読な政策時系列に整理した成果物を確認できない |
| 23 | 医療提供体制に関する行政通知・事務連絡 | 出典マスター・個別監査文書 | 出典記録のみ | 通知本文の対象・日付・文言・改訂履歴を体系化したデータセットは未確認 |
| 24 | 病床確保・転用・受入制限等の医療機関運用 | 週次入院調査171件、G-MISスナップショット43件 | 原資料あり・整理中 | 病床数等の実績資料はあるが、施設の運用変更・受入制限・実施状況を政策時系列に統合できていない |
| 25 | 日本集中治療医学会の資源配分提言 | `docs/references/references_master.csv` | 出典記録のみ | 提言本文の取得・規範項目の抽出・研究の評価軸との対応付けが必要 |
| 26 | 生命・医療倫理研究会の人工呼吸器配分提言 | 同上 | 出典記録のみ | 提言本文の取得・判断手続や配分原則の抽出が必要 |
| 27 | WHOの資源配分倫理指針 | 同上 | 出典記録のみ | PDF本文のGitHub保存または取得監査、原則・評価項目の構造化が必要 |
| 28 | 患者の権利・意思決定・インフォームドコンセント | 出典マスター・研究方針文書 | 出典記録のみ | 国内外の規範資料を選定し、本文と評価項目をGitHubに整理する必要 |
| 29 | 医療従事者の安全・互恵性に関する倫理指針 | 出典マスター・研究方針文書 | 出典記録のみ | 医療従事者への組織的責任・互恵性を評価する規範資料の本文抽出が必要 |
| 30 | 政策決定会議の議事録・検討資料・改訂履歴 | 現在のツリー上で該当する統合データセットを確認できない | 未確認 | 会議録・資料・改訂履歴を一次資料から取得し、政策判断の根拠と時系列を整理する必要 |

## 3. 重要な既存成果物と注意点

### 3.1 疫学データ

`MASTER_01_Epidemiology/` に新規陽性者数、病床使用状況、重症者数、死亡者数、Rt、流行波のデータ・README・辞書・ファイルマニフェストが存在する。ただし、各系列の出典・定義・期間・監査状況は異なる。ファイルが存在することだけで、研究全体の新規収集方針に対する最終採用を意味しない。

### 3.2 厚労省週次入院調査・G-MIS

- 週次入院調査：171原本、9種類の列構造、見出し階層・脚注・ダッシュ類似表記の監査ファイルあり。
- G-MIS：43スナップショットを取得・監査。期間は2021-12-01〜2024-03-06、スナップショット間隔は14〜56日、列構造3種類。
- これらは原資料・構造監査の蓄積であり、全期間・全指標を接続した完成系列ではない。

### 3.3 消防庁

- 原本Excel、週次long形式CSV、マニフェスト、シート・見出し・値監査を保存。
- 正規化データは44,308行。
- 監査は `PASS_WITH_EXPLICIT_SOURCE_ISSUES`。欠損・見出しの不一致・方式変更等の明示的な制約を残している。

### 3.4 非COVID医療アクセス

- 3研究（Yoshida/JACSIS、Yamaguchi、Kurokawa）の論文報告集計値47行をCSVに整理。
- これは患者個票・病院個票の再構築ではない。
- 補足資料の取得状況は研究ごとに異なる。Yamaguchiの補足ファイル取得はHTTP 500で失敗した記録があり、未取得のまま扱う。

### 3.5 倫理的問題の直接証拠

Mori et al.の本文集計は監査文書に整理されているが、補足資料の実ファイル監査は未完了。面会制限、患者・家族、医療従事者の心理的負担・労働環境・補償などは、出典登録とデータ抽出を区別し、現時点では主に出典記録段階として扱う。

## 4. 今後の運用規則（確定）

1. **研究の進捗・取得状況・整理状況の唯一の正本はこのGitHubリポジトリとする。**
2. 進捗の判定は、GitHubの実ファイル、README、データ辞書、マニフェスト、監査ログ、コミットを根拠に行う。Notionや会話履歴だけを根拠に取得済みと判定しない。
3. 各作業の開始・取得・変換・監査・採否をGitHubに記録し、ファイルパスとコミットSHAを追跡可能にする。
4. Notionは研究目的・倫理的判断・研究設計等の参照用に限定する。進捗や取得状態をNotionに重複管理しない。過去の進捗記録は履歴として残す場合も、現行状態の根拠として使用しない。
5. GitHubの進捗記録とNotionの過去記録に差がある場合、GitHubを優先する。Notionの過去記録は「当時の記録」として扱い、現在の状態に関する記述は本方針により訂正・失効させる。
6. 「出典を見つけた」「論文本文を読んだ」「原本を取得した」「整形した」「品質監査した」「研究採用を決定した」を別々の状態として記録する。
7. 旧データや既存加工値を新規の正本データへ無断転用しない。欠測をゼロ補完・補間しない。
8. 研究方針の変更は、ユーザーの明示的な指示とGitHub上の変更記録を必要とする。

## 5. 次の作業優先順位

1. GitHubにある疫学5指標の各README・監査を横断し、現行の採用可否・未解決差異を確定する。
2. MHLW週次入院調査171件とG-MIS43スナップショットのクロスウォーク・脚注・欠損の意味を確定し、比較可能な範囲だけを整形する。
3. 非COVID医療アクセス47行の抽出値と出典本文の対応・分母・重み付けを再点検する。
4. Mori et al.補足資料の取得可能性を再監査する。
5. 患者・家族の自律と尊厳、医療従事者の負担・互恵性について、GitHubに実データ・本文抽出・監査記録が不足している項目を優先取得する。
6. 政策・通知・議事録の一次資料を取得し、政策時系列と現場運用の証拠を区別して整理する。


## 6. Repository metadata / access status

- GitHub API metadata checked on 2026-11-25 JST: repository visibility is `public`, default branch is `main`, repository is `0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research`.
- This differs from the earlier Notion migration plan, which recorded an intended `private` repository. The actual GitHub setting takes precedence for current state.
- The available connected GitHub actions in this session can read and write repository files but do not expose a repository-visibility update operation. Therefore, this work did not change the visibility setting. If the intended access policy remains private, the repository owner must change it in GitHub repository settings before placing any restricted or sensitive material in the repository.

---
この文書は、2026-11-25 JST時点でGitHub mainブランチに存在する内容に基づくスナップショットである。以後の状態はリポジトリの後続コミットで更新する。

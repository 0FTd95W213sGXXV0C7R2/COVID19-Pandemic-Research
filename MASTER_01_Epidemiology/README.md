# MASTER 01 — Epidemiology（日本版）

このディレクトリを、日本版COVID-19研究における疫学5指標および流行波情報のGitHub上の集約先とする。

## 対象範囲

| 区分 | 内容 | 主な保存先 |
|---|---|---|
| 01 | 全国・日次新規陽性者数（New_cases） | `data/01_New_cases/` |
| 02 | 全国・病床使用率（週次） | `data/02_Bed_occupancy/` |
| 03 | 全国・日次重症者数（Severe_cases） | `data/03_Severe_cases/` |
| 04 | 全国・日次報告死亡者数／累積報告値の日次計上増分 | `data/04_Deaths/` |
| 05 | 実効再生産数（Rt） | `data/05_Rt/` |
| 06 | 流行波の週次集計・波区分 | `data/06_Waves/` |

## ディレクトリ構成

- `data/`: 指標別の原系列・補助系列・派生系列と各指標のREADME
- `methods/`: 移動平均・流行波判定等の方法文書
- `audits/`: 流行波境界等の監査記録
- `metadata/`: 本MASTERに含まれるファイル一覧と指標定義

## データの取り扱い

- このフォルダに移動した既存ファイルは、Git blobを再利用して配置を変更した。元データの数値・内容を再計算・修正していない（方法文書内の参照パスのみ更新）。
- 日次7日移動平均は元系列を置き換えない補助列であり、原値列を保持する。
- 病床使用率は週次系列であり、日次7日移動平均を付与しない。
- 死亡指標の `Deaths_reported_increment` は累積報告値の計上増分であり、死亡日別の死亡数とは限らない。
- RtのEpiForecasts再構成系列は、旧MASTERに記録されたRt系列と同一・同等と確認されていない。置換や連結をしない。
- 流行波は改正感染研基準 v1.0による暫定区分。W09は終了未確定。W01・W05・W07はデータ定義変更の影響を排除できない留保がある。
- 欠測の補間・推計・ゼロ置換は行わない。指標ごとの定義・期間・制約は各READMEとデータ辞書を参照する。

## 保護対象MASTER本体との関係

正式Excel `MASTER_01_Epidemiology.xlsx` はGoogle Drive上の保護対象ファイルとして別管理される。GitHubにはこのExcel本体を複製・移動していない。本ディレクトリは、GitHubで管理する疫学関連データ、派生データ、方法文書、監査記録の集約先である。

## 主な方法・監査文書

- [日次7日移動平均](methods/DAILY_7D_MOVING_AVERAGES.md)
- [改正感染研基準 v1.0](methods/EPIDEMIC_WAVE_DEFINITION_NIID.md)
- [流行波境界再監査（2026-11-18）](audits/EPIDEMIC_WAVE_BOUNDARY_AUDIT_20261118.md)

## グラフ

- [疫学5指標のグラフ一覧](figures/README.md)
- [新規陽性者数](figures/new_cases.svg)
- [病床使用率](figures/bed_occupancy.svg)
- [重症者数](figures/severe_cases.svg)
- [死亡者数の計上増分](figures/deaths.svg)
- [Rt（EpiForecasts再構成）](figures/rt.svg)

## 更新履歴

- 2026-11-18: 疫学5指標および流行波関連の既存GitHubファイルを本ディレクトリへ集約。データ内容は変更せず、方法文書の参照パスを更新。

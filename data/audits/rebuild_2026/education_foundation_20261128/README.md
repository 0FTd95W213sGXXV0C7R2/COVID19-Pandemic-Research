# 教育分野の取得・品質監査 第1バッチ

2026年11月28日 JST。基準は研究作業ブランチの `6cb6bf4`。既存の第2次取得計画、11月28日運用変更、経済・教育仕様、103項目の統合台帳、既存経済・教育監査群を使用。基準の追跡ファイル1,855点、data配下1,667点、Pythonコード61点をGitから棚卸しした。全原本の保全先、URL、分析コードの動作確認はこのバッチの対象範囲までで、全103項目の完了判定は未実施。

## 結果

- 暫定CSV 12点の行数と完全重複を確認し、完全重複0件。研究作業ブランチの既存ファイルと採用状態を保持した。
- 公式原本7点を新規取得し、ハッシュを記録。2年度の不登校報告と各正誤表、ICTのExcel3点。Driveで7点の名称・サイズを照合。正誤表は保全した段階で、訂正全件の影響評価は未完了。[Drive保全先](https://drive.google.com/drive/folders/19GBdw0O_Trwlt1SnwuMHiP1K4GuZp5rq)
- 2017・2018年度の全国と47都道府県の小中学校合計、表5-6を抽出。912件がPopplerとPDF座標抽出で一致し、都道府県合算と理由別合計も一致。全国の長期欠席217,040人、240,039人は既存暫定値と一致。「その他」の内数1列は2017年度にあるが2018年度のこの表にはない。旧暫定CSV全体の採否は変更していない。
- e-StatのICT実態調査について、中学校・高等学校（2022年3月）と義務教育学校（2024年3月）の第1シートを原本と照合。3,696セルはopenpyxlとOOXMLで一致。3,411セルは数値、285セルは原資料の記号で、補完していない。単位ラベルや比率の向き、専門学科等の再掲を保持。別シート・年次接続・記号の凡例は保留。
- 旧長期欠席CSVの出典URLはHTTP 404。今回の2017・2018年度は公式各年度報告により独立照合した。2019～2024年度の原典値は今回未照合。
- 統合台帳のEDU06・EDU15・EDU18をL3の部分到達として記録。年度カバレッジや訂正・定義を含む正式採用は未完。取得日時とSHA-256はマニフェスト、抽出検証日時はQAログに保存した。

出典は文部科学省の問題行動・不登校等調査および学校ICT環境調査（e-Stat）。出典を明示した加工値を研究成果として登録し、原本は保全先へ保存した。[不登校調査](https://www.mext.go.jp/a_menu/shotou/seitoshidou/1302902.htm) · [文科省利用規約](https://www.mext.go.jp/b_menu/1351168.htm) · [e-Stat利用規約](https://www.e-stat.go.jp/terms-of-use)

## 実行手順

Python 3.11以降とPopplerを使用。リポジトリ直下で実行する。

```bash
python -m pip install -r scripts/requirements-education.txt
mkdir -p work/education-run
python scripts/education_sources.py work/education-cache work/education-run/source_manifest.json
python scripts/audit_education_sources.py work/education-cache work/education-run data/audits/rebuild_2026/economy_education_20261127/education_long_absence_2017_2024_provisional.csv
PYTHONPATH=scripts python -m unittest discover -s tests -p test_education_sources.py
```

汎用の構造確認は `python scripts/extract_research_source.py <原本> <新規JSON>`。CSV・XLSX・XLS・PDF・JSON・HTMLに対応し、APIのJSON応答も読める。Excelの結合範囲とセル配列を出力し、指標の同等性は別途判定する。今回は公開URLからの直接取得を実行。e-Stat API認証を使う呼び出し、個別APIのページ送り、OCR、全ファイル形式の統合テストは未実施。

次回は保全した2年度報告から新規・継続、支援、高校地域表の座標を特定し、正誤表の該当箇所を照合する。続いてe-StatのICT第2シートと不足校種の原表を確認する。

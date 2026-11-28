# 企業倒産補足統計 BK06～BK11 過年度補完

実行日時（JST）、取得内訳、分類別の観測数と空欄数、比較結果は [品質監査JSON](../../../data/audits/rebuild_2026/bankruptcy_bk06_11_followup/quality_audit.json) に記録。前回の182行と原本ハッシュを照合し、分類・提供元・粒度・時点を観測キーとした。

## 取得・定義・照合

- TDB公式掲載一覧の2017～2024年から月報と暦年報のリンクを取得。従業員規模、資本金、主因、倒産形態を、産業別内訳と全国列がある表、旧式の列位置表、要約表から抽出。全分類の合計が全国件数と一致した表だけを保存した。旧式表の空欄はそのまま保ち、要約表の主因分類では残余の「その他」を独立した区分とした。分類ラベルが一致しても母集団の完全な同等性は未確定。 [TDB倒産情報](https://www.tdb.co.jp/report/bankruptcy/)
- 休廃業・解散の全国年次は2022年報と2024年訂正版の全国推移表で補完した。2017～2019年の旧調査の判明件数は定義差があるため別系列。2024年は2025年1月28日公表の訂正を優先。5ページ本文の建設、サービス、運輸・通信と、6ページの業種別表が訂正対象。抽出対象の全国合計は訂正対象に挙げられていない。過年の訂正版一覧と、年度別原報の全件取得は未完了。 [2017年旧調査](https://www.tdb.co.jp/report/economic/t1ynd5aam8ec/) · [2019年旧調査](https://www.tdb.co.jp/report/economic/e860t6_3qya/) · [2022年報](https://www.tdb.co.jp/report/economic/j86604z4pn/) · [2024年訂正告知](https://www.tdb.co.jp/report/economic/kyuhaigyo_kaisan2024/)
- TSR人手不足関連倒産は公式記事の見出しと本文に明記された暦年値を追加。2024年1～4月記事の集計値は複数月の累計で、月別は画像掲載。本文・表で確認できる単月値の収集は未完了。物価高倒産は前回の2023・2024年値を保持。 [TSR 2023年](https://www.tsr-net.co.jp/data/detail/1198293_1527.html) · [TSR 2024年1～4月](https://www.tsr-net.co.jp/data/detail/1198561_1527.html)
- 既存TSR月次のDriveリンクはHTMLを返し、原本の再取得ができなかった。政府統計ダッシュボードのCSVと系列メタデータからTSRの月次値を取得し、8年の月次合計をTSR自身の年次公表値に照合した。TDBは負債1,000万円以上の法的整理、TSRは同じ負債基準で法的・私的倒産を含む。差はTSR−TDB、比率はTSR÷TDB。相関は記述統計。 [政府統計ダッシュボード](https://dashboard.e-stat.go.jp/timeSeriesResult?indicatorCode=0701060100000010010) · [TSR長期推移](https://www.tsr-net.co.jp/news/status/transition/) · [内閣府 注11](https://www5.cao.go.jp/keizai3/2024/0212nk/n24_3_1.html)
- 前回403の中小企業庁URLは既存結果を継承。経済産業省の代替報告書も403。内閣府資料から定義差を確認し、政府統計ダッシュボードから全国月次CSVを取得した。過年度白書の分類別原表と開業率・廃業率は保留。 [取得台帳](../../../data/audits/rebuild_2026/bankruptcy_bk06_11_followup/source_manifest.json)

厳密な時点共通分類の確定、各発行版の遡及改定全件照合、別の抽出器による独立原表照合は残る。正式採用は保留。

## 再現と受け渡し

Python、lxml、Popplerの `pdftotext` を使用する。既存バッチの非公開ディレクトリを `--baseline` に指定する。

```sh
python scripts/audit_bankruptcy_history.py /workspace/work/bk/next --baseline /workspace/work/bk/supplement --audit data/audits/rebuild_2026/bankruptcy_bk06_11_followup
python -m unittest discover -s tests
```

同じ実行で原本、long、wide、変数辞書、コード、マニフェストと報告書をZIPにまとめる。マニフェストの `package_path` から同一ハッシュの原本を参照できる。原本、詳細CSV、ZIPは公開リポジトリ外で保持。Drive保存には [Colab用の単一セル](economy_bk06_11_colab_cell.md) を使用できる。Driveでのセル実行は未検証。

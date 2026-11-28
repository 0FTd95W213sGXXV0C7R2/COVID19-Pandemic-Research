# 企業倒産補足統計の最終補完

前回の2,221行と保存済みZIPを起点とした。追加表ごとに、対象期間、全国件数、分類の掲載行を照合した。資本金の要約表は隣接する負債規模表との境界を識別し、区分数や上限表記が異なる系列を分けた。主因別の「その他」は原表記載値を保持し、残差算出は行っていない。従業員規模について、対象月報・年報から照合できた表を超える期間は保留。原表空欄の意味は未確定のため、0への変換なし。

既存のTDB分類行はPyMuPDFで物理的な掲載行と値の存在を探した。行内一致は列位置や年次の独立確認に相当しない。列を確定できない空欄、未照合行、時点・定義差で比較できない分類別年次値を品質監査JSONで区別した。遡及改定の全件照合は保留。TSR物価高の2023年は当初公表と後年再掲に1件差があり、当初値に別ラベルを付与した。差の理由は未確認。 [TSR当初公表](https://www.tsr-net.co.jp/data/detail/1198289_1527.html) · [TSR後年再掲](https://www.tsr-net.co.jp/news/status/detail/1200857_1610.html)

BK11のTSR月次96行は、既存BK01の出典台帳にある同一指標・地域・期間の候補。年次8行も同一提供元・指標の候補だが、個別レコードを照合していない。TDBは法的整理、TSRは法的・私的倒産を含み、負債1,000万円以上という条件を共有する。 [政府統計ダッシュボード](https://dashboard.e-stat.go.jp/timeSeriesResult?indicatorCode=0701060100000010010) · [内閣府 注11](https://www5.cao.go.jp/keizai3/2024/0212nk/n24_3_1.html)

行政の開業率・廃業率は、中小企業白書付属統計資料の第12表を特定した。2025年版・2026年版のPDFは直接取得がHTTP 403。検索表示だけの値は保留。対象は雇用保険の成立・消滅に基づく年度別事業所率で、TDBの暦年・企業件数とは定義が異なる。TSR人手不足の単月原表と物価高の追加単月は確認できた分だけを収録した。 [2025年版付属統計資料](https://www.chusho.meti.go.jp/pamflet/hakusyo/2025/PDF/chusho/09Hakusyo_fuzokutoukei_web.pdf) · [2026年版付属統計資料](https://www.chusho.meti.go.jp/pamflet/hakusyo/2026/PDF/chusho/08Hakusyo_fuzokutokeishiryo_web.pdf)

再現は `python scripts/complete_bankruptcy_audit.py 旧ZIP 出力先 空の監査ディレクトリ` で実行する。依存はlxml、PyMuPDF、Poppler。数値CSV・原本・ZIPは作業領域に保管。図表が保存済み資料から確認できなかった期間は取得可能性一覧に記録し、本バッチを終了した。正式採用は保留。

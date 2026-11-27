# Prefecture closure text re-audit
JST: 2026/11/27 17:41:27
Source: https://www.mext.go.jp/content/20200513-mxt_kouhou02-000006590_2.pdf pp.8–10, locally preserved uploaded PDF.
SHA256: 27953fa4ed61fa5d5f473eba5f5505b33879295ce4b1b32f61d53b319e346137 (matches prior manifest).
Method: pdftotext -layout per page, regex prefecture and eight percentage/dash tokens, compare against local structured CSV raw_value keyed by prefecture,page,column. 376 original keys, 376 CSV rows and unique keys, 0 differences. 193 100%, 34 0%, 66 other numeric, 83 dash. This is local text re-extraction, not fresh official download, visual audit or Drive byte readback. Formal adoption pending.

# Drive binary readback QA
JST: 2026/11/27 17:42:37
All three Drive raw files materialized successfully, compared with original uploaded local files using sha256sum and cmp: 3/3 identical.
|File|Drive ID|Bytes|SHA256|
|---|---|---:|---|
|20200513-mxt_kouhou02-000006590_2.pdf|1xu-72zfYnQ9qll5pcV-uyS3OXy9s_lqW|273632|27953fa4ed61fa5d5f473eba5f5505b33879295ce4b1b32f61d53b319e346137|
|gaku-jfy2612.csv|1RA0wH-xfW2v5M6-GleCApMiO2nD8IExz|11529|c1a2fa495f01984ef789fdfea178bb58c3c3b18d3534f27c88d4621b4a8db9f0|
|gaku-mfy2612.csv|1rUGce6eeDuHoPld5alp-h5XuRC3aLWZk|10211|02aaa0dc6e6390fd2a4b7bf50f2a5aa8972297a656ca64e1cba1921309834c6d|
Official PDF https://www.mext.go.jp/content/20200513-mxt_kouhou02-000006590_2.pdf text accessible; online screenshots failed cache miss. Local PDF page 7 rendered and visually inspected, 36 cells consistent with existing record, kindergarten discrepancy of four confirmed visually. Other pages not visually audited this turn. Official distribution binary equality not established. Formal adoption pending.

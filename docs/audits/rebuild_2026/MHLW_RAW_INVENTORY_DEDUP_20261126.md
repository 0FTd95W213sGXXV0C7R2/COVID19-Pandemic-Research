# MHLW raw inventory deduplication audit

2026-11-26 JST (minute not verified).

GitHub contents API directory listing: weekly_inpatient_survey 513 files, 171 distinct nine-digit source IDs, 171 distinct Git blob SHAs. Every ID has exactly three filenames and identical blob SHA within its group. 342 redundant paths; retain all, process one dated path per source ID where available. G-MIS directory has 43 entries; audit directory has 8 JSON entries.

User-uploaded files checked locally using Git blob SHA-1 (hash of blob header plus file bytes):

| ID | Bytes | Git blob SHA | Result |
|---|---:|---|---|
|001168891|25088|89ce426d00e29da8bdb5106091d240f3a04ccdd5|matches all three existing paths|
|001221870|24737|3210e2d3a8b4813b8a71c5c87692c60b4ba5acd9|matches all three existing paths|
|001227209|24574|8dac18303fac2bedf57b582186233ed3373186b7|matches all three existing paths|

No new upload needed for these three. This confirms repository identity, not official-source authenticity or workbook cell validity. Earlier retrieval failures were not evidence of absence in repository. Next: audit existing workbook metadata and archive coverage, resolve date and dash semantics, validate cell values and revisions. No files deleted or moved.

# Drive readback QA
JST: 2026/11/27 22:17:59
All seven files in education_batch1_preservation_manifest.md were materialized from Drive. Actual sha256sum matched all seven manifest hashes; cmp -s against each local original returned success for all seven. CSV wc -l = 1729 including header. Total bytes 3505445. Source folder https://drive.google.com/drive/folders/1ztKwY-T5UCzC_-LhzoTVffMv_8GhdOsY . This establishes byte integrity only, not source-cell accuracy. Independent extraction QA and GitHub CSV registration remain pending.

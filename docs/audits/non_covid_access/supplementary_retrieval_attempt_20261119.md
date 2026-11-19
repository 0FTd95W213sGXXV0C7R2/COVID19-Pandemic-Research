# Supplementary-file retrieval attempt log

- Timestamp: 2026-11-19 14:37 JST
- Scope: Yoshida et al. (2022), JACSIS (PMCID PMC9037356); Yamaguchi et al. (2022), 26-hospital cohort (PMCID PMC9058318); Kurokawa et al. (2022), elective-surgery survey (PMCID PMC9556741).
- Policy: public sources only; no author, researcher, provider, or institution contact.

## Confirmed source metadata

- Yoshida/JACSIS: PMC lists `cmac016_suppl_Supplementary_Table` (DOC, 48 KB) and `cmac016_suppl_Supplementary_Checklist` (DOCX, 29.2 KB).
- Yamaguchi: PMC lists ten files, `bmjopen-2021-060390supp001.pdf` through `supp010.pdf`; reported sizes range from 195.9 KB to 1.1 MB.
- Kurokawa: no supplementary file was identified in the publisher PDF and PMC/PubMed records inspected so far. This is not proof of non-existence.

## Retrieval route investigation

- PMC article pages are indexed and expose the associated-data file names and reported sizes.
- Direct opening of PMC binary-file URLs was not available in this execution environment (PMC browser-check response / inaccessible direct URL).
- The local runtime also could not resolve external hosts, so no binary was downloaded by the container.
- An alternative public route was identified in Europe PMC's official service documentation: the `getSupplementaryFiles` SOAP operation can return supplementary files for an article as a ZIP attachment. Its availability is documented for full-text articles; actual invocation and returned archive contents have not yet been tested.
- Official documentation: https://dev.europepmc.org/doc/EBI_Europe_PMC_Web_Service_Reference.pdf
- Europe PMC bulk-download documentation: https://dev.europepmc.org/downloads

## Current status

| Study | Listing | Binary retrieval | Content audit |
|---|---|---|---|
| Yoshida/JACSIS | Confirmed: 2 files | Not completed | Not started |
| Yamaguchi | Confirmed: 10 PDFs | Not completed | Not started |
| Kurokawa | Not identified in inspected records | Not applicable yet | Not started |

No SHA-256 values are assigned because no binary files were obtained. No supplement-derived values were added to the 47-row evidence table. No existing MASTER or analytical dataset was modified.

## Next bounded action

Test Europe PMC's documented supplementary-file retrieval operation for one article (Yamaguchi, PMCID PMC9058318) before attempting the remaining files. If the archive is returned, enumerate its members, verify filenames and byte sizes, calculate SHA-256, and inspect each file. Do not infer numerical values from figures.


## API execution test initiated

- Triggered GitHub Actions workflow: `Retrieve Yamaguchi supplementary files from Europe PMC`.
- Run ID: `44466845755`.
- Run URL: https://github.com/0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research/actions/runs/44466845755
- The runner completed checkout, Python setup, and dependency installation. At the last status check, the bounded retrieval step was still in progress; no archive, extracted PDF, or SHA-256 has yet been confirmed.
- The workflow has an 8-minute job timeout and the HTTP request has a 90-second read timeout. It records a structured failure manifest rather than inventing a successful retrieval if the endpoint cannot be reached.
- No values have been added to the 47-row evidence table; no MASTER or analysis dataset was modified.

## Completed execution result and repository recording

- Checked the completed workflow run on 2026-11-19 (JST).
- The retrieval step ran and returned HTTP 500 from the Europe PMC REST `supplementaryFiles` endpoint. The response was HTML, not a ZIP archive.
- Result: 0 supplementary binaries downloaded; 0 files extracted; no SHA-256 hashes; content audit remains not started.
- The workflow did create the structured failure manifest, but its final push was rejected as non-fast-forward because the remote `main` branch had advanced after the runner checkout. No force push was attempted.
- The failure manifest was then committed separately at `data/metadata/non_covid_access/yamaguchi_supplementary_retrieval.json` (commit `debb5ecf641af1f710510fe75eefe9ffacbb0d5f`).
- The earlier "still in progress" statement above is superseded by this completed result.
- The 47-row evidence table, MASTER, and analytical dataset remain unchanged. No figure-derived or unverified values were added.
- Next action: do not repeatedly retry the same failing endpoint. Assess one distinct public retrieval route for the Yamaguchi files; if that is unavailable, move to the two Yoshida documents and record the outcome independently.

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

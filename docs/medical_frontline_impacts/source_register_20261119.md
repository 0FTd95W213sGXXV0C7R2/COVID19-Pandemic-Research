# Medical Frontline Impacts — Source Register

- Research date: 2026-11-19 (JST)
- Scope: ambulance transport difficulty, non-COVID medical service impacts by specialty, ICU / mechanical ventilation / ECMO utilization.
- Status: source discovery and initial metadata review only. No new raw data series accepted into MASTER in this commit.
- Policy: preserve source definitions, population, coverage, reporting frequency, revisions, and observation period. Do not merge unlike indicators or infer missing daily values.

## Existing approved-source database records

| Topic | Source | URL | Current status / limitation |
|---|---|---|---|
| Ambulance transport difficulty | Fire and Disaster Management Agency (FDMA), COVID-19 ambulance transport difficulty survey | https://www.fdma.go.jp/disaster/coronavirus/post-1.html | Original workbook already downloaded in prior work (286,999 bytes; SHA-256 bc586c494b32dd83c8d79c1ffd736e828ca208c93a7932667c5a606e1a6a4101). Four sheets. Weekly date/year-block, missingness, reporting changes, and consistency audits remain incomplete. |
| Ambulance workbook | FDMA original Excel | https://www.fdma.go.jp/disaster/coronavirus/items/coronavirus_data.xlsx | Existing file is not yet approved for MASTER. |
| Ambulance definition / reporting changes | FDMA FY2024 notice | https://www.fdma.go.jp/disaster/coronavirus-situ/items/240408_kyuuki_01.pdf | New format started 2024-04-08; COVID-suspected subcategory discontinued. Do not treat pre/post formats as a single unchanged series. |
| Non-COVID healthcare use | Yamaguchi et al. (2022), BMJ Open | https://pmc.ncbi.nlm.nih.gov/articles/PMC9058318/ | Retrospective cohort of 26 Japanese hospitals, Jan 2017–Nov 2020; report values only, not national census. |
| ECMO / ventilation utilization | Japan ECMOnet CRISIS public dashboard | https://crisis.ecmonet.jp/en-general/ | Public description notes retrospective backfill can revise past daily counts; mechanical ventilation-only capture estimated at about 80%; data aggregation ended 2023-03-31. Download format and reproducibility remain to be audited. |
| ECMO cumulative outcomes | MHLW, COVID-19 ECMO treatment in Japan | https://www.mhlw.go.jp/content/10802000/000951151.pdf | CRISIS-derived figures through 2022-06-12: 1,287 cumulative ECMO patients; 814 recovered and weaned, 466 deaths, 7 still receiving ECMO. Participating facilities and ICU coverage are incomplete; not a full national census. |
| ECMO clinical outcomes | Nationwide COVID-19 Registry Japan analysis (PubMed) | https://pubmed.ncbi.nlm.nih.gov/38868250/ | 731 hospitals; 49,590 analyzed patients; 196 received ECMO. Patient-level outcome study, not a daily utilization series. |
| Specialty outpatient trends | Japan specialty outpatient attendance, joinpoint analysis (PubMed) | https://pubmed.ncbi.nlm.nih.gov/38063563/ | Estimated Medical Expenses Database, 2009–2021; monthly clinic outpatient claims as a proxy. Full text and specialty-specific effect sizes still require review. |
| Non-COVID respiratory disease impacts | Public Health (2025), DOI | https://doi.org/10.1016/j.puhe.2025.03.031 | JMDC claims and 71-hospital data through 2023; not nationwide all-population/all-hospital census. Full text and results tables still require review. |

## Initial methodological notes

### Ambulance transport difficulty
FDMA's established COVID-era survey covered 52 fire departments. The definition used in FDMA explanatory material is at least four hospital acceptance inquiries and at least 30 minutes at the scene. This does not mean the patient was never transported: FDMA explains that the cases in the cited survey were ultimately transported. The exact definition and participating departments must be checked across the entire workbook before time-series comparison.

### Other specialties
The 26-hospital Yamaguchi study reported May 2020 year-on-year reductions of 27% in admissions and 22% in outpatient visits. Its results vary by specialty and service type; chemotherapy and maintenance haemodialysis were comparatively maintained. Do not extrapolate the sample directly to all Japan.

### ECMO and mechanical ventilation
CRISIS is a candidate for daily counts, but past daily values can be revised by later facility submissions. Capture coverage and input conventions differ between ECMO and mechanical ventilation. Preserve the date of retrieval and, where possible, a snapshot/version. The MHLW PDF provides a useful cross-check but its chart should not be treated as an independently verified raw daily dataset.

## Next steps
1. Reopen the already-downloaded FDMA workbook and existing audit CSVs; resolve only outstanding date-block, missingness, and definition questions. Avoid repeating completed audits.
2. Determine whether CRISIS offers a machine-readable export or stable downloadable snapshots; record retrieval date, revision behavior, and coverage caveats before extracting a series.
3. Review full texts and supplementary tables for Yamaguchi et al., the specialty outpatient trend study, and the 2025 JMDC respiratory study. Record denominators, specialty definitions, periods, and effect sizes.
4. Store raw files separately from derived data; record SHA-256, acquisition timestamp, script commit, and source URL.
5. Do not modify the existing MASTER datasets until each candidate passes a documented quality gate.

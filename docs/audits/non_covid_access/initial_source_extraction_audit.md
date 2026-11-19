# Non-COVID healthcare access: source extraction and supplementary-material audit

- Audit timestamp: 2026-11-19 14:30:34 JST
- Repository: `0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research`
- Output: `data/processed/non_covid_access/article_reported_aggregate_evidence.csv`
- Scope: Yoshida et al. (2022), Yamaguchi et al. (2022), Kurokawa et al. (2022)
- Status: `PASS_WITH_SOURCE_ACCESS_LIMITATIONS`

## 1. Dataset boundary

The CSV contains 47 rows of published aggregate estimates and cohort counts transcribed from the source articles. It is **not** a reconstruction of original participant-level or hospital-level data.

The source studies are not pooled:
- JACSIS: patient-reported behaviour and disease worsening.
- Yamaguchi: service volume in a restricted set of 26 anonymised hospitals.
- Kurokawa: patient-reported postponement/cancellation among respondents who had planned elective surgery.

No common prevalence estimate or continuous time series was created.

## 2. Source-by-source extraction audit

### 2.1 Yoshida et al. (2022), JACSIS

Citation: Yoshida S, Okubo R, Katanoda K, Tabuchi T. *Family Practice*. 2022;39(5):883–890. DOI: 10.1093/fampra/cmac016.

- Data collection: 2020-08-25 to 2020-09-30.
- Recall/outcome period: April–May 2020.
- Sampling frame: 224,389 candidates invited from a panel of approximately 2.2 million; 28,000 respondents selected.
- Analytic sample: 7,747 respondents aged 15–79 reporting a disease currently under treatment, after data-quality exclusions.
- Outcomes reported: scheduled visit avoidance 1,367/7,747 (17.7%); postponing hospitalization or surgery 161/7,747 (2.1%); running out of medication 379/7,747 (4.9%); disease exacerbation 414/7,747 (5.3%).
- Main publisher article page was inspected. The retrieved publisher page did not expose a supplementary-data link.
- **Correction to the earlier audit:** the PMC indexed full-text/Associated Data record does list two supplementary files:
  - `cmac016_suppl_Supplementary_Table` — DOC, 48 KB.
  - `cmac016_suppl_Supplementary_Checklist` — DOCX, 29.2 KB.
- The supplementary files were not downloaded or inspected in this pass. Their existence is verified from the PMC listing, but their contents are not yet independently checked.
- Data availability statement: underlying data cannot be shared publicly due to ethics approval restrictions.
- The outcome estimates are self-reported and cross-sectional. They are not claims-based utilization rates or causal effects.

Sources:
- Publisher full text: https://academic.oup.com/fampra/article/39/5/883/6555049
- PMC associated data: https://pmc.ncbi.nlm.nih.gov/articles/PMC9037356/

### 2.2 Yamaguchi et al. (2022), 26-hospital cohort

Citation: Yamaguchi S, Okada A, Sunaga S, et al. *BMJ Open*. 2022;12:e060390. DOI: 10.1136/bmjopen-2021-060390.

- Observation period: 2017-01 to 2020-11.
- Cohort: 785,495 patients from 26 anonymised Japanese hospitals.
- 609,101 discharges were recorded; 838 hospitalisations with suspected or definitive COVID-19 diagnoses were excluded; 608,263 non-COVID hospitalisations were analysed.
- Outpatient service volume: 10,932,126 visits by 773,797 unique patients.
- Hospitalisation counts were based on discharge month. Outpatient visits were counted using consultation fees.
- The paper compares monthly 2020 values with 2019 (and reports sensitivity analyses against the 2017–2019 average).
- **Supplementary files are confirmed listed in PMC: ten PDFs.** Names and reported sizes:
  1. `bmjopen-2021-060390supp001.pdf` — 195.9 KB
  2. `bmjopen-2021-060390supp002.pdf` — 463.8 KB
  3. `bmjopen-2021-060390supp003.pdf` — 602.7 KB
  4. `bmjopen-2021-060390supp004.pdf` — 390.9 KB
  5. `bmjopen-2021-060390supp005.pdf` — 479.7 KB
  6. `bmjopen-2021-060390supp006.pdf` — 215.6 KB
  7. `bmjopen-2021-060390supp007.pdf` — 1,012.8 KB
  8. `bmjopen-2021-060390supp008.pdf` — 1.1 MB
  9. `bmjopen-2021-060390supp009.pdf` — 818.9 KB
  10. `bmjopen-2021-060390supp010.pdf` — 1.1 MB
- The main article refers to supplementary figures/tables and ICD-10 code definitions. However, the ten PDF files themselves were not downloaded in this pass; their individual contents and exact filename-to-table/figure mapping remain unverified.
- Data availability statement: the MDV dataset is proprietary and not publicly available; it can be purchased from Medical Data Vision.
- Limitations include anonymised facility locations/infection status and cohort selection based on at least one serum creatinine measurement. Decreases cannot be attributed solely to access restrictions.

Sources:
- Publisher full text PDF: https://bmjopen.bmj.com/content/bmjopen/12/4/e060390.full.pdf
- PMC associated data: https://pmc.ncbi.nlm.nih.gov/articles/PMC9058318/

### 2.3 Kurokawa et al. (2022), elective surgery survey

Citation: Kurokawa T, Ozaki A, Bhandari D, et al. *BMJ Open*. 2022;12:e059886. DOI: 10.1136/bmjopen-2021-059886.

- Survey period: 2020-08-25 to 2020-09-30.
- 28,000 survey respondents; 3,678 reported a planned elective surgery during the emergency-declaration period.
- The article reports 223/3,678 (6.06%) as the unweighted respondent count in the Results/Table 2.
- The abstract and weighted Table 3 report 431/3,678 (11.72%) as the weighted estimate. Both values are retained as separate rows; they are not interchangeable.
- The publisher full-text PDF was inspected. It mentions online prepublication history but the retrieved PDF text contains no supplementary-material section or supplementary-file references.
- Searches of the PMC/PubMed indexed records did not surface a supplementary-file listing in this pass. This means no supplement was identified in the records inspected; it does not prove that no supplemental file exists anywhere.
- Data availability statement: data available upon reasonable request. No request was made.
- The article states that conditions for which elective surgeries were planned were not collected, and there was no normal-period comparator. Therefore, severity, clinical appropriateness and the causal effect of COVID-19 or emergency declarations cannot be established.

Sources:
- Publisher full-text PDF: https://bmjopen.bmj.com/content/bmjopen/12/10/e059886.full.pdf
- PMC record: https://pmc.ncbi.nlm.nih.gov/articles/PMC9556741/
- PubMed: https://pubmed.ncbi.nlm.nih.gov/36216420/

## 3. Important interpretation controls

1. The three studies measure different constructs and must not be pooled.
2. JACSIS and Kurokawa are self-reported cross-sectional surveys; Yamaguchi is a claims-based cohort of 26 anonymised hospitals.
3. A decline in service volume is not equivalent to a documented refusal or unmet medical need.
4. The data do not establish that the pandemic or emergency declarations caused all observed declines.
5. No weekly or monthly survey values were interpolated.
6. Supplementary-file presence is not the same as successful retrieval or content verification.

## 4. Outstanding work

1. Obtain and inspect the two JACSIS supplementary files listed by PMC.
2. Obtain and inspect all ten Yamaguchi supplementary PDFs, especially the supplementary table and disease-code definitions. Extract exact monthly values only when the original table supplies them.
3. Continue checking whether Kurokawa has a separately hosted supplementary file; until found, retain the current status as "not identified", not "none exists".
4. Do not attempt to reconstruct restricted individual-level JACSIS or MDV records.
5. Do not contact authors or providers, consistent with the project policy.

## 5. Audit conclusion

`PASS_WITH_SOURCE_ACCESS_LIMITATIONS`

Published aggregate evidence has been extracted and structurally stored. Supplementary file listings have now been confirmed for Yoshida (two files) and Yamaguchi (ten files), but the binaries were not retrieved or inspected in this pass. No Kurokawa supplementary file was identified in the records inspected. The original individual-level JACSIS and MDV data remain unavailable for public retrieval.

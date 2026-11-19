# Non-COVID healthcare access: initial source extraction and availability audit

- Audit timestamp: 2026-11-19 14:25:34 JST
- Repository: `0FTd95W213sGXXV0C7R2/COVID19-Pandemic-Research`
- Output: `data/processed/non_covid_access/article_reported_aggregate_evidence.csv`
- Scope: Yoshida et al. (2022), Yamaguchi et al. (2022), Kurokawa et al. (2022)
- Status: `PASS_WITH_SOURCE_ACCESS_LIMITATIONS`

## 1. What was built

A source-transcribed aggregate evidence table was created from the original publisher/PubMed/PMC article materials. It contains 59 rows covering:
- JACSIS self-reported scheduled visit avoidance, postponement, medication shortage, disease exacerbation and selected adjusted associations.
- 26-hospital claims-study cohort counts and reported percentage changes in admissions, outpatient visits, diagnostic services, rehabilitation, chemotherapy, dialysis and prescriptions.
- Elective-surgery postponement/cancellation survey results, keeping the unweighted and weighted estimates separate.

**This is not a reconstruction of original participant-level or hospital-level source data.** The original raw JACSIS participant data are not public; the MDV claims dataset is proprietary; and the surgery study data are available upon reasonable request. No author or provider was contacted.

## 2. Source-by-source audit

### 2.1 Yoshida et al. (2022), JACSIS

Citation: Yoshida S, Okubo R, Katanoda K, Tabuchi T. *Family Practice*. 2022;39(5):883–890. DOI: 10.1093/fampra/cmac016.

- Data collection: 2020-08-25 to 2020-09-30.
- Recall/outcome period: April–May 2020.
- Sampling frame: 224,389 candidates invited from a panel of approximately 2.2 million; 28,000 respondents selected.
- Analytic sample: 7,747 respondents aged 15–79 reporting a disease currently under treatment, after data-quality exclusions.
- Outcomes reported: scheduled visit avoidance 1,367/7,747 (17.7%); postponing hospitalization or surgery 161/7,747 (2.1%); running out of medication 379/7,747 (4.9%); disease exacerbation 414/7,747 (5.3%).
- Supplementary Table 1 is listed as a 48 KB DOC; it was not successfully downloaded in this pass. The article's main Tables 1–3 were extracted from publisher full text.
- Data availability statement: underlying data cannot be shared publicly due to ethics approval restrictions.
- The outcome estimates are self-reported and cross-sectional. They do not constitute claims-based utilization rates or causal effects.

### 2.2 Yamaguchi et al. (2022), 26-hospital cohort

Citation: Yamaguchi S, Okada A, Sunaga S, et al. *BMJ Open*. 2022;12:e060390. DOI: 10.1136/bmjopen-2021-060390.

- Observation period: 2017-01 to 2020-11.
- Cohort: 785,495 patients from 26 anonymised Japanese hospitals.
- 609,101 discharges were recorded; 838 hospitalisations with suspected or definitive COVID-19 diagnoses were excluded; 608,263 non-COVID hospitalisations were analysed.
- Outpatient service volume: 10,932,126 visits by 773,797 unique patients.
- Hospitalisation counts were based on discharge month. Outpatient visits were counted using consultation fees.
- The paper compares monthly 2020 values with 2019 (and reports sensitivity analyses against the 2017–2019 average).
- Ten supplementary PDFs are listed by the publisher; their files were not downloaded in this pass. The full publisher PDF was read.
- Data availability statement: the MDV dataset is proprietary and not publicly available; it can be purchased from Medical Data Vision.
- Limitations include anonymised facility locations/infection status and cohort selection based on at least one serum creatinine measurement. Decreases cannot be attributed solely to access restrictions.

### 2.3 Kurokawa et al. (2022), elective surgery survey

Citation: Kurokawa T, Ozaki A, Bhandari D, et al. *BMJ Open*. 2022;12:e059886. DOI: 10.1136/bmjopen-2021-059886.

- Survey period: 2020-08-25 to 2020-09-30.
- 28,000 survey respondents; 3,678 reported a planned elective surgery during the emergency-declaration period.
- The article reports 223/3,678 (6.06%) as the unweighted respondent count in the Results/Table 2.
- The abstract and weighted Table 3 report 431/3,678 (11.72%) as the weighted estimate. Both values are retained as separate rows; they are not interchangeable.
- Data availability statement: data available upon reasonable request. No request was made.
- The article states that conditions for which the elective surgeries were planned were not collected, and there was no normal-period comparator. Therefore, severity, clinical appropriateness and the causal effect of COVID-19 or emergency declarations cannot be established.

## 3. Key cross-source interpretation

These sources measure different constructs:
- JACSIS: patient-reported behaviour and experienced disease worsening.
- Yamaguchi: monthly service volume in a restricted set of anonymised hospitals.
- Kurokawa: patient-reported postponement/cancellation among respondents who had planned elective surgery.

They must not be pooled into a common rate or continuous time series. The survey recall period, hospital discharge-month period, and surgical planning period are distinct. A decline in service volume is not equivalent to a documented refusal or an unmet medical need.

## 4. Outstanding work

1. Download and audit JACSIS Supplementary Table 1 if the publisher file can be retrieved; otherwise retain the main-article-only extraction.
2. Retrieve and inspect the ten Yamaguchi supplementary PDFs, particularly monthly table values and ICD-10 code definitions. Do not create a monthly time series from figures unless exact values can be read reliably.
3. Retrieve the full Kurokawa supplementary materials and verify the weighted/unweighted tables and denominators.
4. Do not attempt to reconstruct restricted individual-level JACSIS or MDV records.
5. Add any additional source only after registering it in the Notion reference database.

## 5. Source links

- Yoshida et al. publisher full text: https://academic.oup.com/fampra/article/39/5/883/6555049
- Yoshida et al. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC9037356/
- Yamaguchi et al. publisher PDF: https://bmjopen.bmj.com/content/bmjopen/12/4/e060390.full.pdf
- Yamaguchi et al. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC9058318/
- Kurokawa et al. PubMed: https://pubmed.ncbi.nlm.nih.gov/36216420/
- Kurokawa et al. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC9556741/

## 6. Audit conclusion

`PASS_WITH_SOURCE_ACCESS_LIMITATIONS`

Published aggregate evidence was extracted and structurally stored. The raw individual-level JACSIS and MDV datasets were not available for public retrieval. The Kurokawa article's unweighted and weighted results require separate treatment. No claim is made that the original raw data were reconstructed or that the studies establish causal effects.

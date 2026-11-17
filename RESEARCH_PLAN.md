# Research Plan

最終改訂：2026-11-17 15:53 JST

## 1. Research Objective

COVID-19パンデミック下の日本で生じた医療上の負担・医療アクセス上の問題・倫理的課題を、独立に検証した証拠から特定し、将来のパンデミックにおける医療体制・権利・公平性・透明性を両立する対策を提案する。

中心課題はデータ量の拡大や相関の探索ではなく、医療面と倫理面の問題を証拠に基づいて特定し、政策提案へ接続することである。

## 2. Reset Rule: No Dependence on the Old MASTER

この計画は、従来のMASTER・旧分析結果・旧SOURCE_INVENTORY・過去の取得成功記録を新研究の入力・定義・採用基準として引き継がない。

- 旧MASTERとの数値一致・不一致を新データの正しさの判定基準にしない。
- 旧MASTERの列・期間に合わせるための補完、切り詰め、再構成をしない。
- 旧資料・旧Notion出典DBの登録資料は候補にとどめ、登録済みという理由で採用しない。
- 新しい問いから指標を定義し、一次資料を独立して選定・取得・監査する。
- 旧データや旧監査記録は、過去の問題を再発させないための履歴資料に限る。新分析データとして使用しない。

## 3. Research Questions

1. 感染拡大と重症化・死亡の負担は、時期ごとにどのように推移したか。
2. 救急・入院・通常医療へのアクセスや医療提供体制にどのような支障が生じたか。
3. 対応は、資源配分、公平性、自律、プライバシー、医療従事者の権利、説明責任・透明性の観点からどのような課題を持っていたか。
4. これらの証拠から、次のパンデミックに向けてどのような制度・運用・情報公開の改善が必要か。

## 4. Analytical Domains

| Domain | Focus | Candidate evidence | Key limitations |
|---|---|---|---|
| A. Epidemiology and burden | Infection, severe disease, mortality | New cases, hospitalization, severe cases, deaths, excess mortality if justified | Distinguish report date, onset date and date of death; document changes in definitions and reporting |
| B. Health-system capacity and emergency access | Emergency transport, beds, staffing and service capacity | Fire and Disaster Management Agency statistics, official hospital/capacity reports | Counts alone do not establish system collapse; verify survey coverage and unit |
| C. Non-COVID healthcare access | Delays, reductions or changes in routine care | Claims/receipts, cancer care/registry, essential health service data | A decline in visits is not automatically proof of unmet need; check coverage, case mix, seasonality and demand |
| D. Ethics, rights and equity | Allocation, restrictions, discrimination, workforce burden, privacy | Laws, policy documents, committee records, empirical studies, professional/affected-group reports | Separate normative arguments from empirical findings; do not generalize limited samples to the whole population |
| E. Policy and governance | Decision-making, rationale, transparency and accountability | Government decisions, minutes, policy evaluations and disclosure records | Policy indices and event counts are not policy effects |
| F. Wider social effects | Education, employment and economic burdens | Official statistics and focused studies | Include only when directly relevant to the central research question |

Not every candidate indicator will be used. Each must pass a relevance, source quality, definition clarity, comparability and missingness assessment.

## 5. Design and Analysis Rules

- Respect the source's true unit of observation: person, facility, prefecture, day, week, month or policy decision. Do not force unlike data into daily time series.
- Compare time periods only where definitions, reporting systems and coverage are sufficiently comparable. Split periods at documented definition changes unless comparability is demonstrated.
- For regional comparisons, check reporting coverage, population structure, resource distribution and institutional differences.
- For pre/post comparisons, consider seasonality, demographic changes, long-term trends, policy changes and changes in healthcare demand.
- Start with descriptive statistics, time-series plots, policy timelines and regional descriptions. Use regression, correlation or lag analysis only when they answer a defined question.
- Before inferential analysis, specify the hypothesis, unit, period, variable definitions, exclusions, confounders, missing-data handling and multiple-testing procedure.
- Correlation is not causation. Causal claims require an explicit identification strategy and defensible assumptions; otherwise report descriptive associations.
- Do not infer ethical acceptability from numerical indicators alone. Combine empirical evidence with policy rationale, ethical principles and relevant stakeholder evidence.

## 6. Source and Dataset Acceptance

Before acquisition, create a specification for each candidate source:

1. Research question and intended use.
2. Issuing body, title, original URL and source type.
3. Population, geography, time coverage and unit of observation.
4. Indicator definition, numerator/denominator, unit and date basis.
5. Collection method, reporting system, revision history and definition changes.
6. Missingness, duplicates, provisional/final status and coverage.
7. Acceptance decision and reasons/limitations.

Acceptance classes: **primary analysis**, **supporting evidence**, **descriptive background**, **hold**, or **reject**. Successful download does not imply analytical acceptance. Unknown definitions remain explicitly unknown; do not fill gaps by guesswork.

## 7. Project Phases

### Phase 1 — Lock research questions and specifications
Prioritize each domain as essential, supporting or out of scope. Finalize indicator specifications before large-scale acquisition or statistical analysis.

### Phase 2 — Identify primary sources
Find the responsible public agency, original dataset, official documentation or original research. Treat the existing Notion bibliography as a candidate list only. Register newly selected sources in Notion before use.

### Phase 3 — Acquire and audit raw sources
Manage acquisition scripts, specifications, data dictionaries and audit code in GitHub. Preserve raw files unchanged in an appropriate storage location. Record JST acquisition time, URL, filename, byte size, SHA-256, version/update date, coverage, schema, types, units, dates, duplicates, missingness, revisions and definition changes.

### Phase 4 — Domain-specific descriptive analysis
Analyze each domain separately. Keep raw, transformed and analytical datasets distinct. Do not begin with one giant integrated MASTER. Any harmonization must be documented and reversible.

### Phase 5 — Integrate medical and ethical findings
Map each medical problem (what happened, when, to whom, and at what scale) to ethical questions (who bore the burden, who benefited, and whether decisions were justified and explained). Report unresolved questions as unresolved.

### Phase 6 — Derive future-policy recommendations
For every recommendation, state: (1) evidenced problem, (2) supporting sources, (3) proposed measure, (4) expected benefit, (5) rights/equity risks and trade-offs, (6) responsible actor and implementation conditions, and (7) evaluation indicator.

## 8. Data Governance and Reproducibility

- Never use old MASTER values as inputs to the new analysis.
- Do not combine indicators with different definitions under one variable name.
- If cumulative data are differenced, verify the meaning of the difference, date basis, revisions, retrospective reporting, negative differences, missingness and initial value. Label reconstructed daily values separately from independent daily statistics.
- Do not convert missing values to zero. Any imputation, estimation or exclusion requires a stated rationale and method.
- If sources disagree, investigate definition, timing and coverage. If unresolved, keep the series separate and report the discrepancy.
- Link every major finding to its source and reproducible analysis step.
- GitHub stores plans, specifications, metadata, acquisition/audit/analysis code and change history. Do not commit raw data without checking licensing, size and retention requirements.

## 9. Immediate Next Step

Do not continue old-MASTER auditing or start bulk data acquisition. Complete Phase 1 first: prioritize the research domains and create the indicator specification table. Only then select the minimum primary sources needed to answer the research questions.

## 10. Framework References

- WHO, Research prioritization for pandemic and epidemic intelligence (2024): https://www.who.int/publications/i/item/9789240094529
- WHO, Ethics and COVID-19: https://www.who.int/teams/health-ethics-governance/diseases/covid-19
- WHO, COVID-19 ethics, resource allocation and priority setting: https://www.who.int/news-room/questions-and-answers/item/coronavirus-disease-covid-19-ethics-resource-allocation-and-priority-setting

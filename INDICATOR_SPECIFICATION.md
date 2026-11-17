# Indicator Specification — COVID-19 Pandemic Research

最終更新：2026-11-17 15:58:50 JST

## 0. Status and scope

これはPhase 1の指標設計案であり、取得・分析採用を確定したものではない。旧MASTER、その値・変数定義・出典・旧分析を新研究の入力や採用基準として引き継がない。既存Notion出典DBも候補一覧として扱い、登録済みという理由で採用しない。以下の機関・資料群は一次資料の探索候補であり、Phase 2で公開状況、定義、期間、利用条件を個別に検証する。

## 1. Priority

| Priority | Domain | Rationale |
|---|---|---|
| P1 Core | A. Epidemiology and burden | Establish scale, timing and health burden |
| P1 Core | B. Healthcare capacity and emergency access | Identify constraints in emergency and inpatient care |
| P1 Core | C. Non-COVID healthcare access | Assess effects on patients needing routine care |
| P1 Core | D. Ethics, rights and equity | Directly addresses the ethical research objective |
| P1 Core | E. Policy and governance | Connect evidence to decision-making and accountability |
| P2 Limited | F. Wider social effects | Include only where needed to explain unequal burdens; no exhaustive standalone survey |

## 2. Indicator specification table

| ID | Research question | Candidate indicator and operational definition | Primary-source candidates | Basic analysis | Priority and acceptance conditions |
|---|---|---|---|---|---|
| A1 | When and to what extent did infection burden occur? | Newly confirmed cases, using the source's stated counting unit and date basis; per-capita rates only with a documented denominator | MHLW and prefectural official statistics/releases | Weekly/monthly trends, epidemic-period and regional comparisons; annotate reporting-system changes | P1. Use only periods where date basis and coverage can be established |
| A2 | How did severe disease and inpatient burden change? | Hospitalized patients, severe cases and new admissions treated as distinct indicators; distinguish stock from flow | MHLW, prefectures and official healthcare-system reports | Time trends, epidemic-period and regional comparisons; calculate occupancy only with compatible bed denominators | P1. Verify severity definition, snapshot time, facility coverage and bed definition |
| A3 | How did mortality burden change? | Death counts with date of death, report date and publication date distinguished; direct daily/weekly statistics kept separate from differences reconstructed from cumulative values | MHLW and official vital-statistics authority | Weekly/monthly and age/region analysis; do not force daily reconstruction when unsupported | P1. Verify death definition, date basis, revisions and retrospective reporting |
| A4 | Can pandemic-period mortality be distinguished from normal variation? | Excess mortality or deviation from expected deaths, with model, baseline period and age adjustment stated | Official vital statistics, public demographic research institutions and peer-reviewed studies | Weekly/monthly description and sensitivity comparison across methods | P2. Accept only if method, uncertainty and baseline are transparent |
| B1 | Were there obstacles to emergency transport and acceptance? | Officially defined emergency-transport difficulty cases, counts/rates and coverage period | Fire and Disaster Management Agency and prefectural fire/emergency services | Weekly/monthly trends, regional comparison, temporal comparison with epidemic waves | P1. Verify official definition, survey scope, frequency and changes |
| B2 | Were hospital acceptance and bed capacity constrained? | Admissions/acceptance status, secured beds and occupied beds; distinguish nominal secured capacity from operational capacity | MHLW and prefectural healthcare-system reports | Time and regional comparison; occupancy only with compatible numerator/denominator | P1. Verify bed definitions, facilities covered, closed beds and staffing constraints |
| B3 | Where were healthcare delivery capacity constraints? | Workforce availability, staffing shortages and facility service restrictions, where measured | MHLW, prefectures and primary surveys by medical organizations | Descriptive and regional analysis; report sample and response rate | P2. Non-representative surveys remain supporting/illustrative evidence |
| C1 | How did routine outpatient and inpatient care change? | Non-COVID service volumes, patient counts or medical expenditure, separated by care type and statistical unit | MHLW claims/medical expenditure statistics and official medical-care surveys | Pre-pandemic comparison and monthly trends by care category | P1. Check coverage, system changes, fee revisions and patient mix |
| C2 | Did important diagnostic/treatment pathways such as cancer care change? | Cancer registrations, stage, screening, diagnosis or treatment volumes; registration counts are not incidence counts | National Cancer Center, prefectural cancer registries and MHLW | Annual trends by site, stage and region, with registry coverage and delay checks | P1. Verify registry coverage, reporting delay and final/provisional status |
| C3 | Was there evidence of unmet need or delayed care? | Surveys of deferred visits, postponed treatment, interrupted care and unmet need | Public patient surveys, official surveys and peer-reviewed primary studies | Descriptive and subgroup analysis consistent with sampling design | P2. Explicitly state self-report and sampling limitations; do not equate with actual missed-care counts |
| D1 | Were healthcare resources allocated fairly and transparently? | Allocation criteria and application for beds, intensive care and treatment opportunities; documentary/case evidence where no quantitative measure exists | Government/prefectural guidance, professional-society guidance, committee minutes and ethics research | Compare formal rules and analyze decision processes | P1. Distinguish formal policy from actual implementation |
| D2 | How did restrictions affect rights, autonomy and equity? | Scope, duration, exceptions and review/appeal mechanisms for movement, isolation, visitation and institutional restrictions | Laws, government/prefectural notices, policy documents, evaluations and affected-person studies | Policy timeline and subgroup/exception analysis | P1. Separate legal rules from real-world implementation and impact |
| D3 | Were burdens and disadvantages unevenly distributed? | Differences by age, region, disability, socioeconomic status or occupation, limited to available attributes | Official statistics, prefectural sources, peer-reviewed studies and affected-group surveys | Stratified description; disparity metrics only with consistent definitions and denominators | P1. Check privacy, sample size and overinterpretation risk |
| D4 | What ethical and work-related burdens did healthcare workers face? | Work hours, infection exposure, psychological burden, discrimination/harassment and safety measures | MHLW, medical organizations, labor authorities and peer-reviewed primary studies | Descriptive/subgroup analysis and review of institutional responses | P2. State survey scope, response rate and self-report limitations |
| D5 | Were personal data and data uses governed appropriately? | Purpose, scope, retention, sharing, third-party provision, notice and oversight of personal data use | Laws, Personal Information Protection Commission, government guidance and committee records | Comparative documentary/governance analysis | P2. Do not infer actual practice from rules alone |
| E1 | Were policy rationales and decision processes transparent? | Decision date/actor, published evidence, expert advice, minutes and stated reasons | Cabinet Secretariat, MHLW, official expert panels and advisory committee records | Policy timeline and documentary analysis | P1. Limit factual claims to what public records establish |
| E2 | Were policies revised in response to new evidence? | Timing of policy changes, stated reasons, disclosed evidence and review processes | Government/prefectural policy documents, review reports and meeting minutes | Map policy changes to contemporaneous rationales and evidence | P1. Temporal coincidence is not proof of policy effect |
| E3 | Were policy benefits and side effects evaluated? | Evaluation metrics, ex-ante/ex-post reviews, independent evaluations and unevaluated areas | Government evaluation materials, research/oversight reports and peer-reviewed studies | Compare evaluation design and findings | P2. Assess metric validity and whether a counterfactual exists |
| F1 | Were education, employment and income burdens unevenly distributed? | Changes in learning opportunities, employment, hours and income, restricted to questions relevant to equity | MEXT, Statistics Bureau, MHLW and other official statistics | Focused pre/post and subgroup description | P2. Exclude indicators not directly linked to the central question |

## 3. Common analytical rules

- Preserve the source's true temporal and observational unit (daily, weekly, monthly, annual; person, facility, prefecture, etc.).
- Distinguish stocks from flows.
- Distinguish report date, onset date, date of death and publication date.
- For per-capita measures, document denominator source, reference date and population definition.
- Never convert missing values to zero. Any imputation or estimate must be a separately named variable with a stated method.
- Split periods at definition/reporting-system changes unless comparability is demonstrated.
- Separate numerical analysis from normative ethical evaluation. Ethical conclusions require relevant laws, policy records, empirical studies and affected-group evidence.
- Do not describe association as causation.
- Each candidate source must be independently assessed in Phase 2 before acceptance.

## 4. Decisions required before Phase 2

1. Confirm the provisional priority: A–E as core, F as limited supporting analysis.
2. Decide whether to include P2 indicators (A4, B3, C3, D4, D5, E3) based on relevance and source quality.
3. Identify the actual primary source for each selected indicator and verify definitions, dates, coverage and access conditions.
4. Assign each indicator to: primary analysis, supporting evidence, descriptive background, hold or reject.

## 5. Important limitation

This specification is a candidate design. It does not establish that any listed dataset is currently available, comparable, complete or suitable for analysis.

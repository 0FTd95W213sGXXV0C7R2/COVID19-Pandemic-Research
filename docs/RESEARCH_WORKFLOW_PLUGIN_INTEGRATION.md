# Research workflow and connected-plugin operating procedure

Last updated: 2026-11-19 11:26 JST

## 1. Purpose and operating principles

This document defines the intended operating procedure for the COVID-19 pandemic study. It is a plan, not a claim that every stage or dataset has been completed.

Research objective: analyze the medical burden, indirect effects on healthcare access, ethical issues concerning rights/equity/autonomy, and transparency/accountability in COVID-19 policy decisions; then develop evidence-based recommendations for future pandemics.

Core rules:
- Preserve provenance: every quantitative value and substantive claim must be traceable to an original source, retrieval date, definition, and processing method.
- Separate source facts, researcher decisions, and analytical interpretation.
- Do not treat absence of a record as zero. Do not silently impute, interpolate, extrapolate, or harmonize incompatible series.
- Preserve raw/source files; perform transformations in versioned scripts and write derived outputs separately.
- Record methodological decisions and changes in Notion with Japan Standard Time (JST).
- GitHub is canonical for code, approved datasets, metadata, audits, analysis outputs, and bibliographic/reference records. Notion is canonical for the chronological research log and decision history.
- Airtable is an optional operational index; it must not become a competing canonical copy of data or references.
- Do not contact source providers or external organizations unless the user separately changes that instruction.

## 2. Roles of connected tools

| Tool | Primary responsibility | Must not replace |
|---|---|---|
| Notion | Research plan, decisions, progress log, unresolved questions, methodology rationale | GitHub's versioned code/data/reference files |
| GitHub | Version-controlled code, datasets, metadata, audits, outputs, bibliography | Notion's chronological decision record |
| Consensus | Discover peer-reviewed literature; compare claims, methods, and evidence | Reading and verifying the original paper |
| Airtable | Track source candidates, data audits, extraction status, and task status | Canonical CSV/analysis data or GitHub reference master |
| Python / GitHub Actions | Reproducible retrieval, validation, transformation, tests, scheduled runs | Human review of definitions and methodological suitability |
| Canva (optional) | Presentation slides, posters, explanatory visual assets after review | Statistical analysis or primary data storage |
| Vercel (optional) | Publish a reviewed interactive dashboard if justified | Research archive, raw data store, reproducibility record |

## 3. End-to-end research workflow

### Stage 0 — Define the research question and analysis unit
1. State the research question, population/geography, period, outcome/exposure, and intended comparison.
2. Define the unit of analysis (person, prefecture, country, day, week, policy event, or study).
3. Write inclusion/exclusion criteria and planned analysis before inspecting outcome patterns where feasible.
4. Record the protocol and unresolved decisions in Notion.
5. Create/update the corresponding GitHub methodology document.

Gate 0: Do not begin data collection until the question, unit, period, and intended estimand or descriptive target are explicit enough to audit.

### Stage 1 — Literature discovery (Consensus)
1. Convert the research question into searchable concepts and synonyms.
2. Search Consensus for peer-reviewed studies; save candidate papers and record search date and query.
3. Screen titles/abstracts against predefined inclusion criteria.
4. Verify each included paper's title, authors, year, journal, DOI/URL, study design, population, period, variables, limitations, and relevant findings against the original paper or publisher record.
5. Extract claims with page/table/figure locations where available. Distinguish primary results from discussion and Consensus-generated summaries.
6. Store verified bibliographic metadata and source URL in docs/references/references_master.csv. Store evidence notes in the relevant docs/ or analysis/ file.
7. Record search strategy, screening decisions, and uncertainty in Notion.

Gate 1: A Consensus summary alone is never sufficient evidence for a final claim. A paper enters the verified reference set only after bibliographic and methodological checks.

### Stage 2 — Source and dataset inventory (Airtable + GitHub)
1. Register candidate sources in an Airtable source-tracking table if a suitable base/table exists. Suggested fields: source ID, institution, dataset/title, URL, geography, start/end dates, native frequency, unit, definition, update status, access/license terms, retrieval date (JST), file path, checksum, audit status, notes.
2. Keep definitive reference metadata and downloaded source files in GitHub according to repository storage policy.
3. Inspect documentation and actual file headers/rows. Never infer columns or geographic coverage from a dataset name.
4. Record schema, missingness, duplicates, date coverage, revisions, definitional breaks, and reporting delays.
5. Separate candidates from accepted datasets. Suggested statuses: candidate, under audit, accepted, rejected, needs review.

Gate 2: Do not accept a dataset until provenance, definition, period, frequency, unit, coverage, license/storage conditions, and limitations are documented.

### Stage 3 — Retrieval and provenance (Python / GitHub Actions)
1. Implement retrieval as a versioned script under src/ or an appropriate project subfolder.
2. Store non-secret configuration in the repository; store credentials only in GitHub Actions Secrets or approved secret storage.
3. Save original downloaded files unchanged where policy and source terms permit. Otherwise record stable source URL, retrieval timestamp, and checksum, and explain why the raw file is not stored.
4. Write a manifest with source URL, retrieval time in JST/UTC, filename, byte size, SHA-256, schema/version if available, and script commit.
5. Make retrieval idempotent where possible; handle pagination, rate limits, transient errors, and partial responses explicitly.
6. Never commit API keys, tokens, passwords, personal data, or secret configuration.

Gate 3: Retrieval is successful only when expected files are present, the response is complete, schema checks pass, and provenance metadata is written. HTTP success alone is insufficient.

### Stage 4 — Data validation and harmonization
1. Validate date parsing, column names, types, units, geographic identifiers, duplicate keys, missingness, and value ranges.
2. Compare observed schema with documented schema; stop on unexpected changes rather than guessing.
3. Preserve native frequency and definition. Aggregate or transform only when the method is explicit and justified.
4. For differing definitions/reporting bases, retain separate series or mark discontinuities; do not join them as equivalent.
5. Record every exclusion, correction, aggregation, conversion, and derived variable in a method document.
6. Automate tests for row counts, date bounds, uniqueness, null rates, and known invariants. Store audit reports under audit/ or the relevant MASTER audits folder.

Gate 4: Do not release an analysis-ready dataset until the validation report is reviewed and unresolved discrepancies are documented.

### Stage 5 — Statistical analysis and reproducibility
1. Keep exploratory notebooks in notebooks/; move reusable/final calculations into scripts under src/ or analysis/.
2. Specify analysis population, denominator, time basis, missing-data handling, uncertainty method, and sensitivity analyses.
3. Separate descriptive trends, associations, and causal claims. Temporal coincidence alone does not establish causality.
4. Generate tables and figures from scripts and versioned inputs; do not edit plotted values manually.
5. Record software versions, parameters, random seeds if applicable, input hashes, and commit SHA.
6. For major results, run robustness checks against plausible alternative definitions, periods, and exclusions.

Gate 5: A result remains provisional until it can be regenerated from versioned inputs/code and its limitations are documented.

### Stage 6 — Evidence synthesis and ethical analysis
1. Integrate epidemiological results, healthcare-system evidence, policy records, and peer-reviewed literature without collapsing unlike measures into one score.
2. For each policy/ethical claim, identify affected rights/interests, evidence, uncertainty, distributional effects, alternatives, and accountability implications.
3. Distinguish empirical findings from normative judgments and policy recommendations.
4. Test whether conclusions differ across population groups, regions, periods, and policy contexts where data permit.
5. Record competing interpretations and evidence gaps.

### Stage 7 — Review, publication, and communication
1. Conduct a source-to-claim audit: every important factual statement maps to a source and, where relevant, a table/figure or page.
2. Conduct a reproducibility audit: another person can identify inputs, run the documented process, and regenerate outputs.
3. Use Canva only after analysis is reviewed, to prepare materials that faithfully reproduce approved results.
4. Use Vercel only if an interactive public-facing dashboard is justified; publish reviewed outputs only, with definitions, update dates, and limitations.
5. Archive final manuscript, tables, figures, code commit, and reference list in GitHub. Record final review and decisions in Notion.

Gate 7: Do not publish without source verification, limitation disclosure, and reproducibility checks.

## 4. Proposed Airtable schema (not yet created)

Airtable should be a workflow index, not a second data warehouse. Recommended tables:

- Sources: source ID, institution, title, URL, source type, geography, period, frequency, unit, definition, retrieval date, license, GitHub path, SHA-256, status, reviewer notes.
- Dataset audits: audit ID, source ID, schema check, date coverage, missingness, duplicates, definition breaks, validation report path, decision, audit date.
- Research tasks: task ID, research question, stage, status, dependency, GitHub issue/PR URL, Notion decision URL, next action.
- Evidence records (optional): claim ID, claim text, supporting paper/source IDs, evidence type, limitations, confidence assessment, manuscript location.

Do not copy large daily time-series into Airtable if the canonical CSV belongs in GitHub. Link to the GitHub file and record its checksum. Inspect the existing Airtable workspace before creating tables to avoid duplicates.

## 5. Repository organization

Use existing repository conventions. Suggested destinations:
- docs/research/RESEARCH_WORKFLOW_PLUGIN_INTEGRATION.md — this procedure or its final chosen path.
- docs/references/references_master.csv — verified bibliographic/source register.
- src/ — reusable retrieval and transformation scripts.
- analysis/ — question-specific analysis code and outputs.
- notebooks/ — exploratory work.
- audit/ and MASTER-specific audits/ — validation evidence.
- results/ — reviewed tables, figures, and reports.

Do not move or overwrite existing MASTER data as part of this procedure. Confirm current files before choosing final paths.

## 6. Research record cadence

Write a Notion entry with JST timestamp when the research question/protocol changes; a source/dataset is accepted or rejected; a definition, transformation, or statistical method changes; an audit finds a discrepancy; a key result is generated or revised; or a conclusion/recommendation changes.

Each entry should include date/time JST, what changed, rationale, evidence/source, affected GitHub paths/commit, status (proposal/provisional/accepted), and remaining uncertainties.

## 7. Immediate execution order

1. Complete the current Rt source/series audit without expanding scope.
2. Finish the MASTER01 dataset and methods audit, preserving current provisional statuses.
3. Use Consensus to build a verified literature set for each research question.
4. Inventory the existing Airtable workspace before creating tables; if no suitable base exists, propose a minimal schema for approval.
5. For each newly accepted source, add verified metadata to GitHub and update Airtable tracking status.
6. Begin cross-domain analysis only after epidemiological and policy-source definitions are stable.

## 8. Security and access controls

The repository was made public on 2026-11-19. Before adding more material, run a history-wide secret and personal-data scan. GitHub Secrets are not normally exposed by repository visibility alone, but credentials accidentally committed to files or prior commits may be exposed. Rotate any confirmed exposed credential. Do not place API keys/access tokens in Airtable, Notion, source files, notebooks, or Git history. Use least-privilege access and review publication/storage rights for third-party datasets.

## 9. Status at time of writing

- Connected and available: GitHub, Notion, Consensus, Airtable; Canva and Vercel are connected for optional communication/deployment work.
- Not established by this procedure: an Airtable base/table schema, automated Consensus-to-reference export, new data retrieval, or completion of the current Rt audit.
- This document defines intended workflow; it does not claim that the proposed Airtable schema has been created or that quality gates have passed.

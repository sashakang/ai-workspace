---
description: Analytical research workflow for hypothesis-driven investigation, observable notebook reasoning, and stakeholder-ready reporting. Use when the task requires structured research with explicit assumptions, EDA, hypothesis testing, and gate-reviewed conclusions.
---

# Analytical Research

Use this skill when the task is a substantive analytical research task that requires one or more of:

- a business decision to support
- explicit assumptions
- data discovery or cleaning
- EDA
- hypothesis formulation and testing
- notebook-based analytical reasoning
- gate reviews
- a final report or presentation

Do not use this full workflow for:

- simple metric lookups
- quick one-off SQL answers
- lightweight descriptive pulls with no real research question
- pure presentation cleanup after the analysis is already settled

In those lighter cases, a simpler analysis workflow should be used instead.

## Dependencies

This skill assumes:

- `core-aiws` provides the platform SOP, escalation protocol, and `/aiws-improve`
- `memory-aiws` provides shared cross-project analyst memory

Read from these surfaces when available:

- `${CLAUDE_PLUGIN_DATA}/shared-memory/`
- `${CLAUDE_PLUGIN_DATA}/project-memory/current/`

Consult these shared references when the task touches their domain:

- `references/research-framing.md` — steps 1-2 (interview, brief)
- `references/hypothesis-and-evidence.md` — step 6 (hypothesis formulation)
- `references/statistical-test-selection.md` — step 9 (testing)
- `references/statistical-interpretation.md` — step 9 (testing)
- `references/experiment-and-observational-caveats.md` — step 9 (testing)
- `references/stakeholder-readouts.md` — step 11 (presentation)
- `references/source-hierarchy.md` — step 4 (data discovery)
- `references/freshness-and-caveats.md` — step 4 (data discovery)

## Grounding Rules

- the notebook is the live research medium, not just a reporting surface
- all analytical reasoning must be visible in the notebook
- no large helper objects, no class-like notebook structure, no hidden logic in external scripts the notebook only imports
- intermediate outputs shown, not only final outputs
- default flow per section: question → code → output → observation → implication
- **enforcement:** each analytical section must contain at least one markdown cell between code output and the next code cell; that markdown must state (a) what the output shows in plain language, (b) what it means for the research question; code followed immediately by more code with no intervening observation is a structural violation that gate reviewers must flag
- all assumptions explicit at notebook top
- cache query results locally for consecutive runs; make cache usage explicit; invalidate on query/parameter/freshness change; see `references/notebook-style.md` for caching rules
- allowed minimal helpers: query runner, cache loader/saver, chart export, repeated routine if reused 3+ times
- if off-notebook work is done for convenience, reconstruct the reasoning visibly in the notebook before passing any gate

## Default Output Format

The default deliverable format is a Jupyter notebook (.ipynb). Before presenting the notebook to the user or passing it to a gate:

- run the notebook end-to-end and confirm it executes without errors
- verify that the actual computed results support the narrative conclusions — do not write conclusions first and then hope the numbers agree
- all data must be loaded via queries or reads from the source; never paste hard-coded dataframes, arrays, or CSVs inline as a substitute for a live query

The presentation layer (1 slide + supporting materials) is built on top of the notebook after the research is complete. The notebook remains the research record; the presentation is the communication layer.

## Notebook Handoff Protocol

The notebook is built incrementally by multiple sub-agents across steps. `references/notebook-skeleton.md` defines section markers that serve as handoff boundaries.

- each execution sub-agent receives: (a) the `.ipynb` file path, (b) the specific section(s) it owns, (c) instruction not to modify sections outside its scope
- sub-agents receive the file path and read the notebook themselves (not inline content in the prompt)
- the notebook skeleton includes a workflow-state cell at the top that the main agent updates after each major step (for session recovery)
- if the notebook exceeds the context budget for gate reviewers, generate section-specific extracts for each reviewer lens rather than passing the full `.ipynb`
- execution sub-agents that write to the notebook run sequentially; only read-only gate reviewers run in parallel

## Workflow

### 1. Interview

SOP Phase 1: Intake.

Resolve before analysis starts:

- what decision must this work support
- who is the audience
- what is already believed internally
- what is fixed and what is open to challenge
- what level of evidence is expected
- what constraints or sensitivities exist
- what prior context should be considered

Consult: `references/interview-checklist.md`, shared `research-framing.md`.

**Exit:** Interview summary written in notebook. Business question, audience, and evidence standard are clear. Proceed to step 2.

### 2. Research brief + assumptions

SOP Phase 2: Planning (start).

Write in the notebook:

- business question (one sentence: what decision does this analysis support)
- research question (one sentence: what specific question will the analysis answer)
- scope (time window, segments in scope, segments excluded)
- audience (who reads this, what they need to decide)
- fixed definitions (not open to challenge)
- open definitions (can be refined by evidence)
- exclusions (what is deliberately out of scope and why)
- evidence standard (directional, statistical significance, other)
- what this analysis can support
- what this analysis cannot support
- success criteria

Consult: shared `research-framing.md`.

**Exit:** Brief section complete in notebook with all fields populated. Proceed to step 3.

### 3. Confirm research brief

Phase 2 checkpoint. Not a gate; no sub-agent review.

Present brief + assumptions to user. Wait for explicit confirmation before data work.

**If rejected:** If user challenges scope or decision context → return to step 1 (re-interview). If user requests brief revisions → revise step 2 and re-present. Do not proceed to step 4 without explicit approval.

**Exit:** User has confirmed the brief. Proceed to step 4.

### 4. Data discovery + cleaning

SOP Phase 2: Planning (continued). Exploratory, delegated to specialist.

Delegate to `data-analyst` sub-agent. Sub-agent receives the notebook file path and owns sections "Data Discovery" and "Data Cleaning."

Checks:

- source coverage: what data sources are available, date range, known gaps
- field availability: fields present for planned comparison, schema changes in window
- key distributions: primary metric distribution, obvious outliers, volume per segment
- time coverage: grain consistency, seasonality patterns, history length
- feasibility: comparison group available, sample sizes sufficient, confounders visible
- obvious inconsistencies: totals reconcile, duplicates, join key alignment

Consult: shared `source-hierarchy.md`, `freshness-and-caveats.md`.

**Exit:** Data discovery and cleaning sections complete in notebook. All query results cached. Feasibility of planned comparison confirmed or flagged. Proceed to step 5.

### 5. EDA

SOP Phase 2: Planning (continued). Exploratory, delegated to specialist.

Delegate to `data-analyst` sub-agent. Sub-agent receives the notebook file path and owns section "EDA."

Mandatory checks:

- missingness: percentage of key fields null or missing, random or systematic, correlation with outcome
- distributions: shape (normal, skewed, bimodal, heavy-tailed), floor/ceiling effects
- time trends: primary metric over time, level shifts, trend changes, anomalies, baseline stability
- segment balance: comparison group similarity, confounding differences, segments too small
- outliers: count, impact on conclusion, data errors vs real extremes
- denominator sanity: stability over time, consistent bases for ratio metrics, dangerously small denominators

**Exit:** EDA section complete. All mandatory checks addressed or explicitly marked not-applicable with reason. Proceed to step 6.

### 6. Hypothesis formulation

SOP Phase 2: Planning (continued).

Write hypotheses in the notebook before testing. Each hypothesis states:

- what is expected (directional claim about a metric or behavior)
- how it will be tested (specific comparison or statistical test)
- what metric will be used (exact measure and definition)
- what result would support it (what outcome counts as evidence for)
- what result would weaken it (what outcome counts as evidence against)

Include at least one "data/measurement issue" hypothesis and one "external factor" hypothesis. Do not rank confidently without evidence — rank by testability first.

Consult: shared `hypothesis-and-evidence.md`.

**Exit:** Hypotheses written in notebook with all five required fields per hypothesis. The notebook through step 6 is the input to Gate 1.

### 7. Gate 1: Research readiness

SOP Phase 2.4: Gate 1. Gate mechanics follow SOP consensus rules and escalation protocol.

Spawn 3 `data-analyst` sub-agents in parallel, each with independent prompt and the notebook (or section extracts if notebook exceeds context budget):

**Reviewer A — Data Quality & Cleaning Credibility**

Prompt focus: Is the data coverage sufficient for the planned comparisons? Are cleaning decisions (exclusions, imputations, deduplication) documented with rationale? Are there silent gaps in time coverage, segment coverage, or denominator composition? If any data source was excluded, is the reason defensible? Would a different cleaning choice materially change the downstream analysis?

**Reviewer B — EDA Completeness & Interpretation**

Prompt focus: Were all mandatory EDA checks addressed? Are observed patterns (trends, distributions, segment differences) correctly described and not over-interpreted? Is anything missing that could change the interpretation — unexamined segments, unchecked time windows, ignored outliers? Are denominators stable and large enough? Is there mandatory markdown between every code output and the next code cell?

**Reviewer C — Hypothesis Quality & Test Readiness**

Prompt focus: Are hypotheses specific enough to be falsified? Does each hypothesis name the metric, the comparison, and the expected direction? Is there a plausible business mechanism for each? Is the proposed test appropriate for the data structure (paired vs unpaired, parametric vs non-parametric)? Are confounders acknowledged? Is at least one "data/measurement issue" hypothesis included?

Each reviewer returns a structured verdict:

- **pass** — no material issue found in their domain
- **revise** — specific change to the notebook that should be made before proceeding
- **block** — fundamental flaw that must be resolved

Resolution: block → delegate fix to a new `data-analyst` sub-agent with the blocker feedback, then re-run the blocking reviewer with fresh context. Revise → incorporate change, proceed. Final round: all 3 must return pass. Iteration limits per escalation protocol.

**Exit:** All 3 reviewers pass. Proceed to step 8.

### 8. Present findings + test plan

SOP Phase 3: User Approval. Only after Gate 1 passes.

Present to the user:

- what was discovered in the data
- what was cleaned and why
- what the EDA showed
- what hypotheses will now be tested
- what reviewers challenged and how it was resolved
- open assumptions
- what happens next if approved
- what remains out of scope

Wait for explicit user approval. Testing cannot begin without it.

**If rejected:** If user challenges data or EDA findings → return to step 4 or 5. If user wants hypothesis revisions → return to step 6. Re-running Gate 1 required only if revision materially changes what the gate reviewed.

**Exit:** User has approved. Proceed to step 9.

### 9. Testing and analysis

SOP Phase 4: Execution.

Delegate to `data-analyst` sub-agent. Sub-agent receives the notebook file path and owns sections "Testing and Analysis", "Interpretation", "Limitations", "Final Analytical Conclusion."

The notebook continues question/code/output/observation/implication flow throughout.

Consult: shared `statistical-test-selection.md`, `statistical-interpretation.md`, `experiment-and-observational-caveats.md`.

**Null result handling:** If testing disproves all hypotheses, document the null finding. If the null result is decision-relevant (e.g., "no significant difference" answers the business question), conclude with it. If the null result leaves the business question unanswered and revision is substantial, formulate revised hypotheses and loop back through step 6 → Gate 1 with user approval.

**Exit:** Testing complete. Interpretation, limitations, and analytical conclusion written in notebook. Proceed to step 10.

### 10. Gate 2: Analytical quality

SOP Phase 5: Validation. Gate mechanics follow SOP consensus rules and escalation protocol.

Spawn 3 sub-agents in parallel:

**Challenger A — Analytical Validity**

Prompt focus: Are the statistical tests appropriate for the data structure (paired vs unpaired, parametric vs non-parametric, multiple comparison correction)? Do sample sizes support the claimed precision? Are conclusions stated with appropriate hedging? Are effect sizes reported and meaningful, or just p-values? Are limitations honestly stated — not buried, not inflated? Is there mandatory markdown between every code output and the next code cell?

**Challenger B — Business Readability**

Prompt focus: Can a non-analyst read the conclusion section and explain back: what was compared, what was found, what it means, and what the main caveat is? Are assumptions stated where a reader needs them, not just at the top? Is each section understandable on its own? Are tables and charts labeled, titled, and annotated? Is jargon defined on first use? Is the per-section flow (question/code/output/observation/implication) maintained throughout?

**Challenger C — Decision-Readiness & Communication Quality**

Prompt focus: Does the deliverable answer the original business question from step 1? Is uncertainty honestly communicated — would a stakeholder walk away with false confidence? Are caveats visible in the conclusion, not only in a limitations section? Is the recommended action (or explicit "no action recommended") stated? Could this deliverable be misinterpreted if read without the notebook context?

Each challenger returns a structured verdict:

- **pass** — no material issue found in their domain
- **flag** — concern that should be disclosed in the narrative but does not block delivery
- **block** — material flaw that must be resolved before the research ships

Resolution: block → delegate fix to a new `data-analyst` sub-agent with blocker feedback, then re-run the blocking challenger with fresh context. Flag → incorporate caveat into narrative, proceed. Final round: all 3 must return pass. Iteration limits per escalation protocol.

**Release standard (Gate 2 exit criterion):** The work is not done until a non-analyst could explain back: what was compared, what was found, what the result means, what the main caveat is, what decision the work supports.

**Exit:** All 3 challengers pass. Proceed to step 11.

### 11. Presentation

SOP Phase 7: Documentation.

Build the presentation layer after the research is complete. The notebook remains the research record; the presentation is the communication layer built on top of it.

Main slide:

- short answer (1-2 sentences answering the business question)
- recommendation (what action to take)
- 2-3 key reasons (strongest evidence supporting the recommendation)
- confidence level (high / medium / low with brief justification)
- key caveat (the single most important thing that could weaken confidence)

Supporting materials:

- what was compared (groups, time windows, definitions)
- why the method is credible (brief methodology note)
- what we found (key results with visuals)
- what could weaken confidence (limitations, caveats, open questions)
- appendix (detailed tables, additional charts, technical notes)

Story structure: answer first → context → evidence → so what → caveats → recommendation.

Language: assume no analytical background in the reader. Define each concept on first use. Explain what the metric means, not just its value. Explain what was excluded and why. State what the result supports and what it does not support.

Consult: shared `stakeholder-readouts.md`.

Notebook + presentation together satisfy Phase 7. If the research established reusable methodology or revised metric definitions, flag for reference doc update.

**Exit:** Presentation package assembled. Proceed to step 12.

### 12. Deliver and confirm

SOP Phase 8: Delivery.

Present final notebook + presentation package to the user. Wait for explicit acceptance. Work is not done without it.

**If rejected:** If issue is analytical → return to step 9. If issue is presentational → return to step 11. If issue is foundational (scope, question, data) → escalate as scope expansion and discuss with user whether to restart or abandon.

**Exit:** User has accepted. Proceed to self-improvement.

## Mandatory Self-Improvement

After every non-lightweight research task, run Phase 9 self-improvement through `/aiws-improve`.

Domain-specific dimensions to review:

- was the interview thorough enough
- were assumptions made explicit early enough
- was EDA genuinely exploratory or just confirmatory
- did hypothesis formulation precede testing
- was the report understandable by a non-analyst
- what confused the audience
- what should change in the workflow next time

## Safety Rules

- never invent data, findings, or statistical results
- never hide assumptions behind implicit choices
- never present uncertain conclusions as definitive
- never skip EDA
- never start testing before Gate 1 passes
- never deliver before Gate 2 passes
- never hard-code data in notebooks
- never let polished prose hide weak evidence or wide intervals

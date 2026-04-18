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

Agents used:

- `data-analyst` — steps 4, 5, 9 (execution); steps 7, 10 (gate review); step 12 (Gate 3 fix delegation)
- `customer-rep` — step 12 (Gate 3 stakeholder comprehension review)

Consult these shared references when the task touches their domain:

- `references/research-framing.md` — steps 1-2 (interview, brief)
- `references/hypothesis-and-evidence.md` — step 6 (hypothesis formulation)
- `references/statistical-test-selection.md` — step 9 (testing)
- `references/statistical-interpretation.md` — step 9 (testing)
- `references/experiment-and-observational-caveats.md` — step 9 (testing)
- `references/stakeholder-readouts.md` — steps 11-12 (presentation, Gate 3 fix resolution)
- `references/source-hierarchy.md` — step 4 (data discovery)
- `references/freshness-and-caveats.md` — step 4 (data discovery)

Consult these question-specific pattern references when the research question matches:

- `references/cohort-patterns.md` — steps 4-5 (cohort definition and validation)
- `references/retention-patterns.md` — steps 6, 9 (retention-focused hypotheses and testing)
- `references/experiment-design-patterns.md` — steps 2, 6, 9 (experiment design and execution)

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

If reviewers contradict each other on the same frozen `element_id`, apply the SOP contradiction-resolution step before choosing the next fix path. The Representative owns the contradiction record and any required `next_action` normalization. Only the contradictory reviewer slots for that `element_id` need refreshed post-conference verdicts.

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

If challengers contradict each other on the same frozen `element_id`, apply the SOP contradiction-resolution step before choosing the next fix path. The Representative owns the contradiction record and any required `next_action` normalization. Only the contradictory challenger slots for that `element_id` need refreshed post-conference verdicts.

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

**Exit:** Presentation package (PDF) assembled. Proceed to step 12.

### 12. Gate 3: Stakeholder comprehension

Stakeholder comprehension validation gate. Gate mechanics follow SOP consensus rules and escalation protocol.

The notebook is the analytical work product for analysts. The presentation package (PDF: main slide + supporting materials) is the customer deliverable, derived from the notebook's visuals, logic, and conclusions. Gate 3 reviews the PDF.

Spawn 4 `customer-rep` sub-agents in parallel, each with independent prompt. Each reviewer receives ONLY the presentation PDF. They do NOT receive the notebook, code cells, or methodology sections. Reviewers must not reason about statistical methodology or critique analytical choices — their scope is comprehension, not correctness.

**Reviewer V — Language and Clarity**

Persona: First-time reader who has never seen this topic before AND a senior leader with 5 minutes.

Prompt focus: Go term by term. Is every term either plain language or explicitly defined on first use with plain words? Are sentences short enough to parse without re-reading? Can the main finding be stated in one sentence using only words that appear with definitions in the report? Are there sentences where the meaning depends on unstated technical knowledge? If a term is defined, does the definition use more technical terms that also need defining?

**Reviewer W — Assumption Transparency**

Persona: Risk-aware operations director who needs to know what could be wrong.

Prompt focus: Are ALL assumptions underlying the analysis explicitly stated in the PDF? Does each assumption say what happens to the conclusion if it turns out to be wrong? Are there hidden assumptions the reader would not know to question? Is the difference between what was measured and what was concluded clearly stated? Would a reader know exactly what was NOT checked or NOT included?

**Reviewer Y — Actionability and Completeness**

Persona: Project manager who needs to turn this into a plan.

Prompt focus: After reading the recommendation, list: (1) the exact action with verb, object, and success metric; (2) required preconditions — what must be true for this to work; (3) how you will know it worked — measurement or validation approach; (4) what you will do if it does not work — fallback or trigger for re-analysis. For each item, note whether it is stated in the report or would require asking the analyst. Is it clear what this analysis does NOT cover, so I do not over-extend the conclusion? If the answer is genuinely "no specific action," is that stated explicitly rather than left ambiguous?

**Reviewer Z — Caveat Completeness and Narrative Flow**

Persona: Marketing professional who has been burned by misleading reports before.

Prompt focus: List every place where the narrative could be misinterpreted if someone skipped to the recommendation without reading the supporting evidence. For each, what clarification is missing? Does the narrative flow logically from question to answer without losing a non-technical reader? Can every visual be understood in 10 seconds without analyst help? Does every element in the supporting material serve a non-analyst, or are there sections that use unexplained technical terms beyond those already defined in the main narrative? If this recommendation failed, would the reader understand why from the caveats provided?

Each reviewer returns a structured verdict:

- **pass** — every statement in the reviewed materials can be understood by someone with no analytical training; all jargon is defined or avoided; all recommendations are actionable without analyst consultation
- **flag** — minor comprehension issue (e.g., one term used without definition, one chart that needs a single-sentence annotation); fix is additive; does not change analytical content
- **block** — major comprehension failure (e.g., entire section depends on unstated assumptions, recommendation is not actionable without further analysis, narrative logic breaks for a non-analyst reader); requires rework, not just annotation

Resolution — triage the failure into one of three cases:

**Case 1: PDF clarity issue** — content exists in the notebook but is unclear in the PDF. Delegate fix to a new `data-analyst` sub-agent. The fix agent receives the PDF, the blocker feedback, and shared `stakeholder-readouts.md`. Fix scope: PDF only. May rewrite text, add definitions, change wording if meaning is preserved. May NOT change analytical conclusions or numbers.

**Case 2: Extraction gap** — notebook has the content but it did not make it into the PDF, or it is in the wrong place. Rebuild the relevant PDF section from existing notebook content. No notebook changes needed.

**Case 3: Content gap** — the PDF needs something that is not in the notebook (e.g., a missing assumption, an unexplained exclusion, a visual that was never produced). This is a notebook revision. Delegate to a `data-analyst` sub-agent to add the missing content to the notebook first, then rebuild the relevant PDF section. Notebook additions must be complete and include necessary context. The notebook is the source of truth — everything in the PDF must trace back to it. If the same content gap is flagged again after notebook revision, escalate immediately.

Fix tiers:

- **simplification** — reduce wordcount, rewrite for clarity, cut jargon, tighten language; no justification needed
- **clarification** — add definitions, explicit scope statements, unit explanations; OK without length justification if it prevents misapplication of findings
- **caveat addition** — add limitations, conditions, risk statements; allowed ONLY if the caveat is necessary for correct decision-making; must escalate to user if the caveat materially changes the recommendation strength; a caveat is material if it changes the recommended action, moves the confidence level by at least one step (high→medium or medium→low), or constrains the decision to a subset the original recommendation did not specify (e.g., "all customers" → "US enterprise customers only"); if uncertain whether a caveat is material, escalate

The fix agent must flag if the comprehension failure is structural (cannot be resolved by PDF or notebook changes alone). Escalate to user rather than forcing a workaround.

After fix, re-run ONLY the blocking reviewer with: (1) revised PDF, (2) fix agent's summary of changes, (3) previous blocker feedback for context. Re-run counts toward the reviewer's 3-iteration budget.

Flag → incorporate the minor fix and proceed.

Final round: all 4 must return pass.

Each reviewer that blocks gets independent fix-and-recheck cycles, up to 3 per reviewer per escalation protocol. Gates 1, 2, and 3 have independent iteration budgets — "gate iterations: 3" from the escalation protocol applies per gate, not across all gates combined. If any reviewer remains blocked after 3 attempts, escalate to user.

If two or more reviewers issue conflicting feedback on the same frozen `element_id` and prescribe mutually exclusive fixes, run the SOP contradiction-resolution step first inside the existing reviewer-specific recheck flow. If the contradiction record ends `converged`, continue with the existing case-based fix/recheck path using the updated reviewer verdicts. If it ends `strategically_unresolved` or `slot_unavailable`, escalate to the user.

**Relationship to Gate 2 Challenger B:** Gate 2 Challenger B validates that a non-analyst *could* understand (checked by an analyst). Gate 3 validates that a non-analyst *does* understand (checked by a simulated non-analyst). Complementary, not redundant.

**Exit:** All 4 reviewers pass. Proceed to step 13.

### 13. Deliver and confirm

SOP Phase 8: Delivery.

Present final notebook + presentation PDF to the user. Wait for explicit acceptance. Work is not done without it.

**If rejected:** If issue is analytical → return to step 9. If issue is presentational → return to step 11 (then re-run Gate 3). If issue is foundational (scope, question, data) → escalate as scope expansion and discuss with user whether to restart or abandon.

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
- did Gate 3 reviewers identify comprehension failures that Gate 2 missed
- what jargon or complexity passed Gate 2 but failed Gate 3
- what pattern of Gate 3 failures should refine Gate 2 Challenger B prompts
- what should change in the workflow next time

## Shared-Memory Staging

After delivery, if the task produced reusable cross-project learnings, stage one candidate event per learning with the plugin-local staging utility into `${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/`.

If `aiws-host-memory` is not bootstrapped yet and the outbox path is unavailable, skip shared-memory staging and continue. Do not block delivery on helper setup.

Use shared memory for durable analyst heuristics, recurring tool quirks, and workflow patterns that should help future projects. Keep project-specific findings, dataset-specific notes, and transient debugging state in project memory instead.

## Safety Rules

- never invent data, findings, or statistical results
- never hide assumptions behind implicit choices
- never present uncertain conclusions as definitive
- never skip EDA
- never start testing before Gate 1 passes
- never deliver before Gate 2 passes
- never deliver before Gate 3 passes
- never hard-code data in notebooks
- never let polished prose hide weak evidence or wide intervals

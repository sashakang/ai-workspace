---
description: Time-series forecasting workflow for analyst-grade projections, uncertainty quantification, and stakeholder-safe narratives. Use this skill when the user needs a forecast, projection, or trend extrapolation rather than a descriptive summary or a statistical test.
---

# Data Analyst Forecast

Use this skill when the user needs a time-series forecast, projection, or forward-looking estimate rather than a retrospective summary or a hypothesis test.

This is a forecasting workflow:
- frame the business question the forecast serves
- lock the metric, granularity, horizon, and data source
- explore the series for frequency, trend, seasonality, gaps, and outliers
- draft the modelling plan
- **Gate 1** — three reviewer agents check feasibility, methodology fit, and business alignment; approved plan goes to the user for final sign-off
- fit a model (Prophet by default; ARIMA/SARIMAX when more control is needed)
- validate on a holdout period and check residual assumptions
- deliver forecast, confidence intervals, decomposition, and a stakeholder-safe narrative
- **Gate 2** — three challenger agents independently stress-test data, methodology, and decision risk; reviewed forecast goes to the user for approval

## Dependencies

This skill assumes:
- `core-aiws` provides the platform SOP and `/aiws-improve`
- `memory-aiws` provides shared cross-project analyst memory
- project-specific context comes from imported project memory

Read from these surfaces when available:
- `${CLAUDE_PLUGIN_DATA}/shared-memory/`
- `${CLAUDE_PLUGIN_DATA}/project-memory/current/`

Consult these references when the task touches their domain:
- `references/statistical-interpretation.md` — for uncertainty language and interval semantics
- `references/freshness-and-caveats.md` — for data-age warnings and regime-change flags
- `references/metric-definitions.md` — for canonical metric names and computation rules
- `references/domain-analytics.md` — for domain-specific forecasting conventions

## Grounding Rules

- do not invent forecasts, confidence intervals, or decomposition components
- do not present point forecasts without an accompanying uncertainty range or explicit caveat
- do not invent sample sizes, seasonality patterns, or trend inflections
- if the history is too short for the chosen granularity, say so and recommend a coarser grain or a simpler model
- if the series is too noisy for a defensible forecast, say so rather than forcing a fit
- be explicit about data gaps, regime changes, and structural breaks that limit forecast reliability
- if key context (e.g., planned promotions, known supply shocks) is missing, flag the omission
- never hard-code data into the deliverable; all values must come from queries against the source data
- every conclusion in the deliverable must be supported by an executed result visible in the notebook

## Default Output Format

The default deliverable format is a Jupyter notebook (.ipynb). Before presenting the notebook to the user or passing it to a gate:
- run the notebook end-to-end and confirm it executes without errors
- verify that the actual computed results support the narrative conclusions — do not write conclusions first and then hope the numbers agree
- all data must be loaded via queries or reads from the source; never paste hard-coded dataframes, arrays, or CSVs inline as a substitute for a live query

If the user explicitly requests a different format, honour that, but the notebook remains the default.

## Workflow

### 1. Frame the business question

Lock down:
- the decision this forecast should inform (revenue projection, demand planning, capacity sizing, budget allocation, etc.)
- who will consume the forecast and what action it drives
- the cost asymmetry of over- vs under-forecasting, if the user has a view

A forecast without a clear decision context is just a chart. Push for the "so what" before modelling.

### 2. Lock scope

Before touching data, agree on:
- the target metric and its exact definition
- granularity (daily, weekly, monthly, quarterly)
- forecast horizon (how far forward)
- data source and any known filters or exclusions
- whether exogenous regressors (holidays, promotions, macro indicators) are in scope

### 3. Explore the data

Before modelling, characterise the series:
- auto-detect or confirm frequency and date alignment
- visualise trend, seasonality, and any obvious structural breaks
- quantify missing values and decide on imputation strategy (or exclusion)
- flag outliers and decide whether to clip, winsorise, or leave them
- note the effective history length relative to the chosen granularity and horizon

If the effective history is shorter than two full seasonal cycles, flag this as a material limitation.

### 4. Draft the modelling plan

Before the gate, assemble a plan document that covers:

**What we learned from the data**
- effective history length and date range
- detected frequency, trend direction, and seasonality pattern (or absence thereof)
- data-quality issues found: missing values, outliers, structural breaks, regime changes
- any limitations that constrain what can be defensibly forecast

**Proposed modelling plan**
- recommended model family and why (Prophet, ARIMA/SARIMAX, or both for comparison)
- key parameter choices or auto-selection strategy
- planned holdout window for backtesting
- exogenous regressors to include, if any
- imputation or outlier treatment to apply before fitting

**Risks and caveats**
- whether the history is long enough for the requested horizon
- whether detected regime changes make the trailing data less representative
- any missing context (promotions, policy changes, external shocks) that could materially affect the forecast

This document is the input to Gate 1. Do not present it to the user yet.

### 5. Mandatory Gate 1 — Automated plan challenge

This gate is mandatory. The plan does not reach the user until it survives independent challenge by three reviewer agents.

Spawn three sub-agents in parallel. Each receives the full plan document from Step 4 (data findings, proposed model, validation strategy, risks) and is tasked with finding weaknesses before any compute is spent.

**Reviewer A — Feasibility & Data Sufficiency**
Prompt focus: is the effective history long enough for the proposed granularity and horizon? Does the data quality support the planned imputation and outlier treatment? Are there silent gaps, frequency mismatches, or upstream schema issues that would undermine the model before it even fits? If the plan is over-ambitious given the data, say so.

**Reviewer B — Methodology Fit**
Prompt focus: is the proposed model family the right match for the patterns found in exploration? Would the detected trend, seasonality, or autocorrelation structure be better served by an alternative? Is the holdout window representative or does it risk flattering the model? Are the parameter choices justified or just defaults that happen to be convenient?

**Reviewer C — Business Alignment & Scope**
Prompt focus: does the plan actually answer the business question from Step 1? Is the metric the right one for the stated decision? Is the forecast horizon what the stakeholder needs, or what the data makes easy? Are asymmetric loss functions, known future events, or missing regressors being ignored when they should shape the approach?

Each reviewer returns a structured verdict:
- **pass** — no material issue found in their domain
- **revise** — specific change to the plan that should be made before presenting to the user
- **block** — fundamental flaw (e.g., insufficient data for any defensible forecast) that must be resolved or disclosed prominently

If reviewers contradict each other on the same frozen `element_id`, apply the SOP contradiction-resolution step before choosing the next fix path. The Representative owns the contradiction record and any required `next_action` normalization. Only the contradictory reviewer slots for that `element_id` need refreshed post-conference verdicts.

Resolution rules:
- If any reviewer returns **block**, address the issue — which may mean narrowing scope, coarsening granularity, or recommending against forecasting entirely — and re-run the blocking reviewer.
- If a reviewer returns **revise**, incorporate the change into the plan and proceed.
- The final review shall employ all three reviewers. The plan clears the gate only if all three return **pass**.

### 6. Present the approved plan to the user

After Gate 1 clears, present the reviewed plan to the user. Include:
- the plan document (updated with any revisions from Gate 1)
- a summary of what the reviewers challenged and how it was resolved
- any residual risks the reviewers flagged that the user should weigh

Wait for explicit user approval before proceeding to modelling. If the user requests changes to scope, granularity, model choice, or data treatment, revise the plan accordingly. If changes are substantial enough to invalidate the Gate 1 review, re-run the affected reviewer(s). Do not treat silence as approval.

### 7. Model

Default to Prophet for its transparency, built-in seasonality handling, and interpretable decomposition. It is the right first choice for most analyst-facing forecasts.

Escalate to ARIMA or SARIMAX when:
- the user needs explicit control over differencing, AR, or MA order
- the series has strong autocorrelation structure that Prophet handles poorly
- exogenous regressors need a classical regression framework

In either case:
- state the model choice and the reason
- list the key parameters and whether they were auto-selected or manually set
- if multiple models are plausible, fit both and compare on the holdout

### 8. Validate

No forecast ships without validation:
- hold out the most recent portion of the series (default: the last forecast-horizon-length window) and backtest
- report holdout error in business-meaningful terms (MAPE, MAE, RMSE — pick the one the stakeholder understands)
- inspect residuals for autocorrelation, heteroscedasticity, and remaining pattern
- if residuals show structure, revisit model choice or feature engineering before proceeding

### 9. Deliver

Package the deliverable as a Jupyter notebook (the default output format). Run the notebook end-to-end before proceeding — it must execute cleanly with all data queried from source, not hard-coded. Verify that computed results match the narrative.

A complete forecast deliverable includes:
- **forecast values** with explicit date labels
- **confidence intervals** (80% and 95% by default, or as the user specifies)
- **decomposition** — trend, seasonality, and residual components visualised or tabled
- **stakeholder narrative** that separates:
  - what the model projects and why
  - what the model does not capture (regime changes, one-off events, missing regressors)
  - what the confidence intervals mean in plain language
  - what next action is justified given the uncertainty

Never let strong prose hide wide intervals. If the 95% band spans a range that would change the decision, say so directly.

### 10. Mandatory Gate 2 — Challenger review

This gate is mandatory. The forecast does not ship until it survives independent challenge by three analyst agents.

Spawn three sub-agents in parallel. Each agent receives the full forecast deliverable from Step 9 (data, model choice, validation results, narrative) and is tasked with finding weaknesses. Each challenger has a distinct focus:

**Challenger A — Data & Assumptions**
Prompt focus: interrogate data quality, imputation choices, outlier handling, and whether the effective history length supports the chosen granularity and horizon. Look for silent data gaps, frequency mismatches, and upstream schema changes that could invalidate the series.

**Challenger B — Model & Methodology**
Prompt focus: question model selection, parameter choices, and validation rigour. Would an alternative model family produce a materially different forecast? Are the residuals genuinely clean or is structure being ignored? Is the holdout period representative or does it cherry-pick a calm window?

**Challenger C — Stakeholder & Decision risk**
Prompt focus: stress-test the narrative and the uncertainty communication. Does the deliverable honestly convey what the confidence intervals mean for the decision at hand? Are regime-change risks, missing regressors, or asymmetric loss functions adequately surfaced? Would a non-technical reader walk away with false confidence?

Each challenger returns a structured verdict:
- **pass** — no material issue found in their domain
- **flag** — concern that should be disclosed in the narrative but does not block delivery
- **block** — material flaw that must be resolved before the forecast ships

If challengers contradict each other on the same frozen `element_id`, apply the SOP contradiction-resolution step before choosing the next fix path. The Representative owns the contradiction record and any required `next_action` normalization. Only the contradictory challenger slots for that `element_id` need refreshed post-conference verdicts.

Resolution rules:
- If any challenger returns **block**, address the issue and re-run the blocked challenger (not all three) before proceeding.
- If a challenger returns **flag**, incorporate the caveat into the stakeholder narrative in Step 9 and proceed.
- The final review shall employ all three challengers. The forecast clears the gate only if all three return **pass**.

Do not suppress or summarise away challenger objections. If a challenger raises a legitimate concern and you disagree, document the disagreement and your reasoning in the deliverable.

### 11. Present the reviewed forecast to the user

After Gate 2 clears, present the final deliverable to the user. Include:
- the forecast, confidence intervals, decomposition, and stakeholder narrative (updated with any revisions or caveats from Gate 2)
- a summary of what the challengers raised and how each issue was resolved or disclosed

This is a review and discussion step, not a hand-off. The user may request refinements — changes to the narrative tone, different confidence interval widths, additional scenario analysis, or deeper investigation of a challenger concern. Incorporate changes and, if they are substantial enough to invalidate a Gate 2 verdict, re-run the affected challenger(s).

Do not proceed until the user explicitly approves the deliverable. Do not treat silence as approval.

### 12. Mandatory self-improvement

After every non-lightweight forecasting task, run Phase 9 self-improvement through `/aiws-improve`.

Capture:
- what worked and what did not in model selection and validation
- any data-quality issues that should be flagged for future runs
- reusable patterns (e.g., holiday calendars, imputation defaults) worth persisting to shared memory

### 13. Shared-memory staging

After delivery, if the task produced reusable cross-project learnings, stage one candidate event per learning with the plugin-local staging utility into `${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/`.

If `aiws-host-memory` is not bootstrapped yet and the outbox path is unavailable, skip shared-memory staging and continue. Do not block delivery on helper setup.

Capture to shared memory only when the learning is reusable across projects, stable enough to keep, and relevant beyond the current forecast. Keep project-specific notes, one-off debugging details, and dataset-specific quirks in project memory instead.

## Safety Rules

- never invent forecast outputs or fabricate model diagnostics
- never present a point forecast as a commitment; always pair it with uncertainty
- never hide wide confidence intervals behind confident narrative
- never extrapolate beyond the defensible horizon without explicit caveat
- never recommend action from a forecast whose assumptions were not checked

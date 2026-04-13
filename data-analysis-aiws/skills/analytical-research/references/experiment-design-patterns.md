# Experiment Design Patterns

Pre-launch design decisions for controlled experiments.

For post-launch interpretation pitfalls, see `../../references/experiment-and-observational-caveats.md`.

## Randomization

- choose the randomization unit before anything else: user, session, device, or geographic region
- match the randomization unit to the metric unit — if the metric is per-user, randomize per-user
- if the randomization unit is coarser than the analysis unit (e.g., randomize by cluster, measure by user), plan for clustered analysis from the start
- use a single assignment mechanism and log the assignment at the moment it happens
- verify balance on key covariates after assignment, before exposure

## Control group

- the control group must experience exactly the existing state, not a degraded or novel alternative
- if a true holdout is not possible, document what the control actually receives
- never reuse a control group across concurrent experiments without checking for interaction effects
- if the experiment requires a ramp (1% → 10% → 50%), define the ramp schedule and decision criteria before launch

## Sample size and duration

- compute the required sample size before launch using the minimum detectable effect that would change the decision
- state the assumed baseline rate, expected effect size, significance level, and power
- run the experiment for at least one full business cycle (typically one week) to capture day-of-week effects
- do not stop early on significance — pre-register a fixed duration or use a sequential testing framework with spending rules
- if the required sample size exceeds available traffic, either accept lower power and document it, or redesign the experiment with a larger effect threshold

## Pre-registered success criteria

- define the primary metric, the direction of expected change, and the minimum meaningful effect before launch
- limit primary metrics to 1–2; additional metrics are secondary and should be labeled as such
- state the decision rule: what result leads to ship, iterate, or kill
- if multiple primary metrics exist, define how conflicts are resolved (e.g., metric A must improve without metric B degrading beyond threshold)

## Anti-patterns

- choosing the randomization unit after seeing unbalanced results
- running without a pre-registered duration or sample size and stopping when results "look good"
- using more than 2 primary metrics without a pre-registered conflict resolution rule
- designing the experiment around available data rather than the decision it must support
- launching without verifying that the logging and assignment infrastructure is working

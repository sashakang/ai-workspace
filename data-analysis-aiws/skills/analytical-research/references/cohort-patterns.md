# Cohort Patterns

Rules for defining, bounding, and comparing cohorts in analytical research.

## Cohort definition

- define entry criteria before looking at outcomes — never reverse-engineer cohort membership from results
- use a single, unambiguous event as the cohort entry point (first purchase, signup date, feature activation)
- state the entry window explicitly: "users who signed up between X and Y"
- if the entry event can repeat, decide whether only the first occurrence counts and document the rule
- exclude users who cannot possibly complete the observation (e.g., signed up after the observation window closes)

## Observation windows

- fix the observation window length before analysis — do not extend it to chase significance
- align observation windows across cohorts: every cohort gets the same number of days/weeks post-entry
- if cohorts have different calendar start dates, check for seasonal or external confounds across windows
- distinguish calendar time (Jan 1 – Jan 31) from tenure time (days 0–30 since entry)
- report which time frame is used and why

## Overlap and membership

- a user must belong to exactly one cohort per comparison; shared membership invalidates the comparison
- if users can migrate between segments during the window, decide at the start whether to use intent-to-treat (classify by initial assignment) or as-treated (classify by actual behavior) and document the choice
- when comparing cohorts of different sizes, report both absolute counts and rates — do not rely on rates alone if one cohort is very small
- check for survivorship: if only users who stayed active appear in later periods, the cohort shrinks silently and comparisons become biased

## Anti-patterns

- defining cohorts after seeing outcomes ("users who churned" as a starting cohort for churn analysis)
- mixing calendar time and tenure time in the same comparison without disclosure
- comparing cohorts with materially different observation window lengths
- ignoring cohort size imbalance when interpreting rate differences
- allowing users to appear in multiple cohorts in a between-group comparison

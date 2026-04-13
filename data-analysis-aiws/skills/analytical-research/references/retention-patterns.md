# Retention Patterns

Rules for computing retention curves, defining churn, and applying survival metrics.

## Retention curve computation

- anchor the denominator to the original cohort size at entry — do not rebase to "active at period N"
- state the denominator rule explicitly: "retained = active in period N / signed up in cohort"
- choose a period grain (day, week, month) that matches the product's natural usage cadence
- use consistent period boundaries: if week 1 starts on the entry date, every subsequent week starts exactly 7 days later
- report the denominator alongside the retention rate so readers can judge small-sample periods
- if users can return after absence, decide whether a return counts as retained in the return period, the gap periods, or both — document the rule

## Churn definition

- define churn as a specific observable absence, not a latent state: "no activity in X consecutive days"
- choose the churn window based on the product's return distribution, not convenience
- distinguish voluntary churn (cancellation, explicit departure) from inactivity churn (silence)
- if a user "churns" and returns, decide whether they re-enter the cohort or start a new tenure — document the rule
- never define churn by a threshold chosen after looking at the data

## Survival and hazard metrics

- use survival analysis when the question is "how long until event X" and censoring is present
- right-censoring is expected: users who haven't churned yet are censored, not excluded
- report median survival time and confidence interval, not just the curve shape
- if comparing two groups, use a log-rank test or equivalent before claiming one survives longer
- check proportional hazards assumption before applying Cox regression — if hazards cross, the summary hazard ratio is misleading

## Anti-patterns

- rebasing the denominator to "still active" at each period, inflating later-period retention
- treating day-1 retention as meaningful when it is 100% by construction
- picking a churn window that conveniently minimizes or maximizes the churn rate
- dropping censored observations instead of handling them with survival methods
- reporting retention rates without the underlying cohort size per period
- comparing retention curves from cohorts with different entry-window lengths without disclosing the mismatch

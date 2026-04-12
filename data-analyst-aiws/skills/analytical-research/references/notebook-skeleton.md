# Notebook Skeleton

Canonical section order and handoff boundaries for analytical research notebooks.

## Workflow state cell (cell 1)

First cell in every notebook. Updated by the main agent after each major step.

| Step | Status | Timestamp |
|------|--------|-----------|
| Interview | pending/done | |
| Brief + assumptions | pending/done | |
| User approval 1 | pending/approved | |
| Data discovery | pending/done | |
| Data cleaning | pending/done | |
| EDA | pending/done | |
| Hypotheses | pending/done | |
| Gate 1 | pending/passed | |
| User approval 2 | pending/approved | |
| Testing + analysis | pending/done | |
| Interpretation | pending/done | |
| Limitations | pending/done | |
| Conclusion | pending/done | |
| Gate 2 | pending/passed | |
| Presentation | pending/done | |
| User approval 3 | pending/approved | |

## Section markers (handoff boundaries)

These markdown headers serve as anchor points for sub-agent handoff.
Each sub-agent owns specific sections and must not modify sections outside its scope.

1. `# Brief and Decision Question`
2. `# Interview Summary`
3. `# Assumptions and Scope`
4. `## [User Approval 1 — Brief Confirmed]`
5. `# Data Discovery` — owned by step 4 sub-agent
6. `# Data Cleaning` — owned by step 4 sub-agent
7. `# EDA` — owned by step 5 sub-agent
8. `# Hypotheses` — owned by step 6 (main agent or sub-agent)
9. `## [Gate 1 — Research Readiness]`
10. `## [User Approval 2 — Test Plan Confirmed]`
11. `# Testing and Analysis` — owned by step 9 sub-agent
12. `# Interpretation` — owned by step 9 sub-agent
13. `# Limitations` — owned by step 9 sub-agent
14. `# Final Analytical Conclusion` — owned by step 9 sub-agent
15. `## [Gate 2 — Analytical Quality]`
16. `# Presentation Outputs`
17. `## [User Approval 3 — Delivery Accepted]`
18. `# Self-Improvement Notes`

## Rules

- Remove sections that don't fit the specific question
- Question-specific patterns (cohort design, retention curves) belong in separate reference files, not the generic skeleton
- Each section should be independently readable
- Gate and approval markers are informational headers, not code cells

## Per-section flow (enforceable)

Every analytical section follows:

1. Question — what are we checking here?
2. Code — the computation
3. Output — visible result
4. Observation (markdown cell) — what do we see?
5. Implication (markdown cell) — what does this mean for the research question?

**Structural rule:** There must be at least one markdown cell between any code output and the next code cell. A section with code followed immediately by more code, with no intervening observation, is a structural violation.

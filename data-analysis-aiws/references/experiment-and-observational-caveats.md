# Experiment And Observational Caveats

Statistical conclusions depend as much on design quality as on formula choice.

## Experiment caveats

- rollout contamination can break treatment-control separation
- sample-ratio mismatch may indicate assignment or logging issues
- novelty effects can distort early windows
- metric definitions may shift during the test

## Observational caveats

- confounding can create fake differences
- selection bias can distort comparisons
- time-window misalignment can create misleading before/after conclusions
- survivorship bias can make cohorts look stronger than they are

## Multiple testing

If many metrics, regions, or cuts were explored:
- acknowledge multiplicity
- avoid overconfident interpretation of one surviving positive result

## Decision rule

If the design is weak, say so directly.

A weak design can still justify:
- descriptive monitoring
- a follow-up experiment
- a narrower claim

It should not be dressed up as strong causal evidence.

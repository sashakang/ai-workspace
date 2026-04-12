# Statistical Test Selection

Choose the simplest valid test family that matches the decision and design.

## Start with these facts

Before naming a test, identify:

- unit of analysis
- randomized vs observational design
- number of comparison groups
- metric type: binary, continuous, count, or ratio-like
- whether the same unit appears multiple times

## Safe selection rules

- binary outcome with two independent groups:
  - proportion comparison family
- continuous outcome with two roughly comparable groups:
  - mean-comparison family
- highly skewed or heavy-tailed outcome:
  - consider robust or non-parametric comparison
- repeated observations or clustered units:
  - call out dependence first; simple independent tests may be invalid
- observational data with meaningful confounding risk:
  - simple significance alone is not enough; adjustment or cautious descriptive framing may be required

## Anti-patterns

- naming a specific test before the unit is defined
- using many sliced tests without acknowledging multiplicity
- treating ratio metrics as if they were simple independent observations without checking construction
- defaulting to a fancy model when a simpler, interpretable method answers the question

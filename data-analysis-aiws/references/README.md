# Analyst Reference Pack

This directory is the shipped knowledge pack for `data-analysis-aiws`.

It is the primary home for publishable analyst knowledge that should be available even in standalone mode.

## Referenced by `data-analyst-forecast`

These references are declared dependencies of the forecast skill:

- [metric-definitions](./metric-definitions.md) — canonical metric names and computation rules
- [domain-analytics](./domain-analytics.md) — domain-specific forecasting conventions
- [statistical-interpretation](./statistical-interpretation.md) — uncertainty language and interval semantics
- [freshness-and-caveats](./freshness-and-caveats.md) — data-age warnings and regime-change flags

## Referenced by `analytical-research`

These references are declared dependencies of the analytical research skill:

- [research-framing](./research-framing.md) — interview + brief (steps 1-2)
- [hypothesis-and-evidence](./hypothesis-and-evidence.md) — hypothesis formulation (step 6)
- [stakeholder-readouts](./stakeholder-readouts.md) — presentation (step 11)
- [statistical-test-selection](./statistical-test-selection.md) — testing (step 9)
- [statistical-interpretation](./statistical-interpretation.md) — testing (step 9)
- [experiment-and-observational-caveats](./experiment-and-observational-caveats.md) — testing (step 9)
- [source-hierarchy](./source-hierarchy.md) — data discovery (step 4)
- [freshness-and-caveats](./freshness-and-caveats.md) — data discovery (step 4)

## General analytical references

These references support future skills (stat-test, research, extraction) and provide general analytical grounding:

- [source-hierarchy](./source-hierarchy.md)
- [join-and-grain-rules](./join-and-grain-rules.md)
- [research-framing](./research-framing.md)
- [hypothesis-and-evidence](./hypothesis-and-evidence.md)
- [stakeholder-readouts](./stakeholder-readouts.md)
- [statistical-test-selection](./statistical-test-selection.md)
- [experiment-and-observational-caveats](./experiment-and-observational-caveats.md)
- [mcp-and-bootstrap-assumptions](./mcp-and-bootstrap-assumptions.md)

Design intent:

- primed plugin, not blank slate
- portable, publishable knowledge
- no personal paths, private memory, or hidden local assumptions

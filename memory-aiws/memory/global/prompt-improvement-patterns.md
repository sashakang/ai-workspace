# Prompt Improvement Patterns

Prompt and process improvement patterns that apply across multiple plugins belong here.

## Behavioral detection over introspection

Do not use LLM introspection prompts ("did you consider X?", "rate your confidence"). LLMs confabulate self-assessments. Instead, use behavioral detection: check whether the output exhibits the desired property by examining the artifact directly.

Source: Phase 9 self-improvement on analytical-research v0.2.0.

## Descriptive names, not invented phase numbers

When naming steps, phases, or stages in skills and protocols, use descriptive names that convey what happens (e.g., "data discovery", "hypothesis formulation"). Do not invent sequential phase numbers (e.g., "Phase 3.2") unless the SOP already defines them — invented numbering creates false precision and makes reordering painful.

Source: Phase 9 self-improvement on analytical-research v0.2.0.

## Define qualitative terms with operational thresholds

When a protocol or skill uses qualitative terms (e.g., "thorough", "sufficient", "material"), define them with operational thresholds that a reviewer can check. Example: "sufficient sample size" → "sample size that achieves 80% power at the pre-registered effect size." Without thresholds, qualitative terms become subjective and unenforceable in gate reviews.

Source: Phase 9 self-improvement on analytical-research v0.2.0.

---
description: Thin SOP adapter for backend Python implementation, debugging, TDD, refactors with behavior risk, and code review inside AIWS. Use when the task is substantive software engineering work and should follow the canonical SOP rather than an ad hoc coding flow.
---

# Dev

Use this skill for software-engineering work inside AIWS when the task is primarily:

- backend Python implementation
- debugging or root-cause isolation
- targeted test work
- refactors with behavior risk
- code review of Python changes

Do not use this skill in v1 for:

- infrastructure or deployment work
- SQL or data-pipeline work
- prompt or protocol authoring
- broader polyglot engineering outside the current AIWS Python surface

## Canonical Process

[`core-aiws/protocols/sop.md`](../../core-aiws/protocols/sop.md) is the canonical workflow.

This skill does not replace the SOP. It only adds AIWS-specific engineering policy for the supported code path.

## AIWS-Specific Rules

### 1. Classify first

Classify the task using the SOP before doing anything else.

- if the task is `lightweight`, follow the SOP fast path and do not force TDD
- if the task is non-lightweight and executable Python behavior is changing, the TDD rules below apply
- if the task is non-executable plugin, skill, manifest, or docs work, verify via schema, JSON, path, and integration checks instead of forcing TDD

### 2. TDD applicability

For non-lightweight executable Python changes, TDD is required.

A viable test surface means one of:

- existing targeted coverage can be extended
- a targeted test can be added using the repo's current test framework without introducing a new framework

Existing failing tests count as the red phase only if they directly cover the requested behavior. Unrelated failing tests do not count.

If there is no viable test surface for a non-lightweight executable change, raise that as a planning blocker rather than silently skipping TDD.

### 3. Validation command order

Use this deterministic discovery order for validation commands:

1. explicit documented or package-local test command
2. repo runner files such as `Makefile`, `justfile`, `tox.ini`, or `noxfile.py`
3. framework-native runner inferred from config
4. in current AIWS, fall back to targeted `python -m unittest`

Run lint only when a configured linter exists. Do not invent a lint step.

## Support Agents

Use these plugin agents for the supported v1 code path:

- `backend-python-engineer`
- `code-debugger`
- `code-tester`
- `code-reviewer`
- `code-simplifier`
- `architecture-simplifier`
- `technical-writer`

Keep their use aligned with the role taxonomy already defined in the SOP.

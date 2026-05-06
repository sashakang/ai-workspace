---
name: writing-documentation
description: Write, edit, audit, and review AIWS-aware technical documentation, including READMEs, docs pages, runbooks, how-to guides, reference pages, skill docs, and architecture notes. Use when documentation must be grounded in repository code, AIWS memory, and docs-as-code verification.
---

# Writing Documentation

Use this skill for substantive documentation work: new docs, doc rewrites, docs audits, runbooks, how-to guides, references, skill documentation, architecture notes, and documentation updates tied to code or workflow changes.

Do not use this full workflow for tiny typo fixes, purely conversational explanations, or `.docx`/presentation deliverables that are owned by a file-format skill.

## AIWS Surfaces

This skill uses `core-aiws` for the SOP. When `memory-aiws` or project-memory surfaces are installed, read them before making broad documentation decisions:

- `${CLAUDE_PLUGIN_DATA}/shared-memory/`
- `${CLAUDE_PLUGIN_DATA}/project-memory/current/`
- AIWS MCP skill catalog tools, when the task is about installed, staged, or materialized AIWS skills

For AIWS repository work, validate plugin and skill packaging through the existing release gate rather than manually eyeballing manifests.

## Reference Files

Load only the reference needed for the current task:

- `references/document-types.md` - choose tutorial, how-to, reference, explanation, README, runbook, ADR, or skill documentation.
- `references/style-and-quality.md` - apply voice, structure, linking, examples, and docs-health standards.
- `references/aiws-documentation.md` - document AIWS plugins, skills, contracts, MCP behavior, and memory boundaries.
- `references/review-checklist.md` - audit or review docs before handoff.

## Workflow

### 1. Classify the work

Use the core SOP complexity rules, then classify the documentation intent:

- create: new documentation surface
- update: existing docs need to reflect changed behavior
- audit: find gaps, stale content, duplication, or broken structure
- review: inspect proposed documentation changes
- migrate: reorganize docs without changing the product behavior

For unclear requests such as "fix the docs," inspect the likely target files first. Ask one focused question only if the target, audience, or intended artifact is still ambiguous.

### 2. Ground the content

Before writing, gather evidence from the repository and AIWS context:

- read nearby docs and navigation files
- inspect the code, configs, schemas, contracts, tests, or skill files being documented
- check existing terminology and avoid inventing a parallel vocabulary
- identify the reader: new user, contributor, maintainer, operator, stakeholder, or future agent
- note freshness limits when behavior depends on external services, current versions, or deployment state

Never document intended behavior as current behavior unless the implementation already supports it. If the docs describe a planned design, label it as target state, proposal, or future work.

### 3. Choose the document type

Use `references/document-types.md` when the document shape is not obvious.

Keep each page centered on one reader need. Avoid mixing task steps, API reference, and architecture rationale in the same section unless the existing doc intentionally uses a compact hybrid format.

### 4. Write or edit

Prefer updating the nearest authoritative doc over creating a new surface. Delete or consolidate stale duplicate text when it is safer than preserving it.

Write in direct, practical English:

- put the main point before details
- use active voice and present tense
- use `you` for task instructions when it fits the existing style
- use numbered lists for ordered procedures and bullets for unordered facts
- include examples for commands, APIs, config, or workflows that readers may copy
- explain why only when it changes the reader's decision or prevents misuse

For skill docs, keep `SKILL.md` concise and move detailed patterns into one-level-deep reference files. Do not add clutter files inside a skill folder.

### 5. Verify

Run the cheapest useful validation available:

- check changed links and anchors
- check commands, paths, and filenames
- run the repo's formatter or docs check when one exists
- for AIWS plugin changes, run the skill-management release validation or targeted unit tests
- compare the final text against the code or contract it describes

If verification is impossible or disproportionate, say exactly what was not verified and why.

### 6. Handoff

Summarize what changed, where, and how it was verified. For audits and reviews, lead with findings ordered by severity and include file references.

## Gates

Use the lightest gate model that still protects accuracy.

Lightweight typo fixes, formatting-only edits, and small wording clarifications use the SOP fast path and do not need gates.

Standard documentation work uses Gate 2 only. This covers ordinary README updates, how-to pages, runbooks, reference edits, skill docs, and docs updates tied to already-understood code or workflow changes.

Use Gate 1 only when the documentation plan itself is risky:

- reorganizing a documentation set
- creating a new canonical documentation structure
- replacing or deleting large documentation surfaces
- documenting architecture, target-state behavior, or operational guidance that could mislead future implementers
- changing AIWS skill, prompt, protocol, contract, or install documentation in a way that affects agent or user behavior

When Gate 1 applies, validate the plan before writing:

- the target audience and document type are clear
- the proposed source of truth is identified
- the scope avoids unnecessary new documentation surfaces
- the validation path is realistic

Gate 2 validates non-lightweight output before delivery:

- the documentation matches current code, contracts, schemas, configs, or skill files
- target-state or proposed behavior is labeled clearly
- links, paths, commands, and examples are checked where practical
- structure and language fit the intended reader
- duplicate or stale docs are removed, linked, or explicitly left out of scope

Use the default SOP documentation reviewer unless the subject needs a second lens. For AIWS skill or protocol docs, include a prompt/protocol review lens. For architecture or contract docs, include an architecture/contract review lens.

## Self-Improvement

For every non-lightweight documentation task, run core SOP Phase 10 in realtime mode and then the Auto-Capture Protocol.

During that pass, look specifically for:

- recurring stale-doc patterns
- missing document-type guidance
- unclear AIWS infrastructure boundaries
- user corrections about tone, audience, or depth
- validation steps that should become reusable documentation workflow rules

Do not directly mutate shared memory or sibling plugin files as a shortcut. Stage reusable learnings through the AIWS memory outbox or route workflow changes through `/aiws-improve` and the SOP review path.

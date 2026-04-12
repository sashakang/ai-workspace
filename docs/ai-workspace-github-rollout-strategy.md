# AI Workspace GitHub And Rollout Strategy

Updated: 2026-03-26

## Purpose

This document defines how the AI workspace should move from the current local `.claude` design work into a durable GitHub-backed implementation workflow.

The goal is to preserve the current architectural vision before code begins, then implement against a real repository instead of treating the live local `.claude` tree as the product source of truth.

## Recommended Strategy

### Principle

Push the plans first. Implement second.

Reason:

- the current architecture and implementation plans are now the baseline vision
- `.claude` is a live runtime workspace, not a clean product repository
- starting implementation only in the live local tree would blur personal runtime state with product code
- a docs-first initial commit gives a stable reference point for later architectural drift

### Source of truth

Use a dedicated GitHub monorepo as the product source of truth.

Recommended local path:

`~/Documents/ai-workspace/`

Recommended remote:

`https://github.com/sashakang/ai-workspace.git`

Use the local `.claude` environment only for:

- runtime testing
- plugin behavior validation
- migration experiments
- comparing product behavior against the current personal setup

Do not use the live `.claude` tree as the canonical product implementation surface.

Use `~/.claude/plugins/` only as the runtime install and validation surface.

Bootstrap the local repo by cloning the remote:

```bash
git clone https://github.com/sashakang/ai-workspace.git \
  ~/Documents/ai-workspace/
```

## Repository Model

### Recommended repo

Create one monorepo for the platform.

Recommended shape:

```text
~/Documents/ai-workspace/
├── core-aiws/
├── memory-aiws/
├── data-analysis-aiws/
├── docs/
│   ├── ai-workspace-architecture.md
│   └── ai-workspace-github-rollout-strategy.md
├── scripts/
└── README.md
```

### Why monorepo

Use one repo because:

- plugin boundaries are tightly related
- `core-aiws`, `memory-aiws`, and domain plugins share contracts
- `/aiws-improve`, SOP, memory, and plugin metadata must evolve together
- cross-plugin review is easier in one place
- release tooling can still package each plugin independently

### Runtime packaging model

Monorepo source does not mean one install artifact.

The release model should be:

- one repo
- one subdirectory per plugin
- one independently packageable plugin artifact per subdirectory
- users install only the plugins they need

Expected user installs:

- `core-aiws`
- `memory-aiws`
- `data-analysis-aiws`

Future users may install:

- `core-aiws`
- `memory-aiws`
- `lawyer-aiws`

without needing unrelated sibling plugins.

### User installation model

End users should install through the marketplace.

They should not:

- clone the repo
- symlink plugin directories
- copy plugin files manually into `~/.claude/plugins/`

## First GitHub Push

### Commit 1: Vision baseline

The first commit should be docs-only.

Contents:

- `docs/ai-workspace-architecture.md`
- `docs/ai-workspace-github-rollout-strategy.md`
- `README.md`
- optional empty top-level plugin directories:
  - `core-aiws/`
  - `memory-aiws/`
  - `data-analysis-aiws/`

Purpose:

- preserve the initial architecture before implementation drift begins
- create a stable reviewable reference point
- make later deviations intentional and visible

### Commit 2: Repo scaffolding

After the docs-only baseline is pushed, create the repo scaffolding:

- plugin directory skeletons
- shared packaging conventions
- basic manifest layout
- build or packaging scripts
- developer README for local testing

This is still infrastructure, not feature implementation.

## Implementation Order

### Phase 1: `core-aiws`

Implement `core-aiws` first because it defines the shared process contract.

Scope:

- SOP
- shared `/aiws-improve`
- shared protocol set
- plugin metadata expectations
- future host-side bridge contract surfaces

Acceptance focus:

- `core-aiws` is self-contained
- no domain-specific logic leaks into `core-aiws`
- shared `/aiws-improve` can target declared plugin contracts

### Phase 2: `memory-aiws`

Implement `memory-aiws` second because domain plugins depend on its shared-memory contract.

Scope:

- shared memory structure
- export/import snapshot format
- automatic candidate outbox plus bridge-driven consolidation model
- metadata for read/write scope

Acceptance focus:

- no direct sibling-root runtime reads
- shared-memory snapshot import contract is explicit
- memory ownership is separated from process ownership

### Phase 3: `data-analysis-aiws`

Implement `data-analysis-aiws` third.

Scope:

- namespaced analyst skills
- analyst agents
- analyst references
- `.mcp.json`
- bootstrap assets
- project-memory and shared-memory consumption through the platform contracts

Acceptance focus:

- no local `data-analyst-improve`
- depends on `core-aiws` and `memory-aiws`
- writes project knowledge through the project-memory bridge model
- does not create a second project-memory platform

## Branching And PR Strategy

### Branch strategy

Use short-lived feature branches off `master`.

Recommended sequence:

1. `docs/initial-platform-vision`
2. `scaffold/core-memory-analyst-layout`
3. `feat/core-aiws-v1`
4. `feat/memory-aiws-v1`
5. `feat/data-analysis-aiws-v1`

### Pull request shape

Keep PRs boundary-aligned:

- one PR for docs baseline
- one PR for repo scaffolding
- one PR per plugin implementation phase

Do not mix:

- architecture refactors
- packaging conventions
- plugin behavior implementation

in the same PR unless the change is impossible to separate cleanly.

## Local Development And Testing

### Where to implement

Implement in the GitHub repo.

Do not implement primarily in the live `.claude` tree.

### Where to test

Test against the local `.claude` environment.

Recommended workflow:

1. implement plugin code in the repo
2. run Claude with explicit `--plugin-dir` arguments for the plugin roots under development
3. validate behavior against real Claude Code runtime behavior
4. fix in the repo
5. repeat

### Local `--plugin-dir` pattern

Use explicit plugin dirs for local developer iteration.

Examples:

```bash
claude \
  --plugin-dir ~/Documents/ai-workspace/core-aiws \
  --plugin-dir ~/Documents/ai-workspace/memory-aiws \
  --plugin-dir ~/Documents/ai-workspace/data-analysis-aiws
```

This is a developer workflow, not a user install workflow.

### Repo hygiene during local repo-based development

Local testing with `--plugin-dir` must not pollute the source repo with runtime-mutated state.

Rules:

- runtime-mutated `state/`, `cache/`, `logs/`, and similar paths must resolve to `${CLAUDE_PLUGIN_DATA}` when possible
- if any runtime-mutated paths remain inside the repo during development, they must be gitignored
- generated artifacts from local validation must not be committed unless they are intentional source artifacts

### Role of current `.claude`

The current `.claude` tree should remain:

- a reference implementation
- a migration source
- a behavior comparison baseline

It should not become the product repo.

## Migration Of Existing Local Assets

### Migrate first

Migrate into the repo first:

- architecture docs
- implementation plans
- canonical plugin-owned protocol files
- shared skill definitions intended for publication

### Leave local for now

Do not immediately migrate every existing local asset.

Keep local-only until needed:

- personal runtime hooks
- personal memory files
- user-specific MCP credentials
- personal experimentation artifacts
- compatibility copies needed by the live local setup

## Release Strategy

### V0

The initial public state should be:

- docs committed
- repo structure visible
- plugin boundaries frozen

### V1 target

The first implementation milestone should be:

- `core-aiws` usable
- `memory-aiws` usable
- `data-analysis-aiws` usable
- local Claude validation completed

### Publishing rule

Do not publish marketplace artifacts until:

- plugin contracts are stable
- bootstrap is tested on a second-user setup
- `core-aiws` and `memory-aiws` contracts are not changing every day

### Marketplace handoff

The release path from monorepo to users is:

1. implement and validate locally through `--plugin-dir` runtime testing
2. prepare the plugin artifact from the monorepo subdirectory
3. publish or update the marketplace entry for that plugin
4. install and verify from the marketplace as a non-developer user
5. only then treat the plugin as ready for broader use

## Working Rules

- treat GitHub as the product source of truth
- treat `.claude` as the runtime lab
- land docs before code
- implement shared infrastructure before domain plugins
- keep each plugin installable independently
- preserve the initial docs commit as the architectural baseline for future comparison

## Current Next Steps

1. clean and merge the current plugin PR stack into `master`
2. keep local runtime validation on `--plugin-dir`, not symlinks
3. publish early alpha with `core-aiws`, `memory-aiws`, and `data-analysis-aiws`
4. collect install and usage feedback before adding new plugins

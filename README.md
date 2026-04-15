# AI Workspace

This repository is a small AI workspace for Claude Code.

It is built around one idea: useful Claude workflows should be packaged as installable plugins, not left as personal setup, scattered prompts, or one-off local habits.

The platform currently gives teams three reusable layers:

- `core-aiws` for shared process and improvement workflows
- `memory-aiws` for shared cross-project memory contracts
- `data-analysis-aiws` for analyst-specific workflows

## What It Is For

Use this platform when you want Claude Code to behave less like a blank assistant and more like a reusable working system.

It is meant for teams that want:

- shared operating procedures across Claude sessions
- reusable domain workflows instead of ad hoc prompting
- memory boundaries between project memory, shared memory, and runtime state
- a path to ship more domain plugins over time

In practice, this means you can install a common foundation once, then add domain plugins on top of it.

## How The Platform Is Structured

The platform is intentionally split into composable plugins rather than one large monolith.

### `core-aiws`

The shared process layer.

It provides:

- the platform SOP
- the public `/aiws-improve` workflow
- shared protocols that other plugins can depend on

### `memory-aiws`

The shared memory layer.

It defines:

- the cross-plugin shared-memory model
- import and export contracts
- automatic candidate capture and consolidation rules
- the boundary between authoritative docs and advisory shared memory

### `data-analysis-aiws`

The first real domain plugin.

It currently provides:

- `data-analyst-forecast` (time-series forecasting)
- `analytical-research` (hypothesis-driven research with dual-gate review)

This plugin is intentionally **primed**, not blank-slate: it ships domain references and workflow structure so users get useful behavior on day one.

## Why This Is Extensible

This repository is not only an analyst plugin repo. It is a platform for adding more plugins with the same architecture.

The extensibility model is:

- `core-aiws` stays the shared process foundation
- `memory-aiws` stays the shared memory foundation
- each new domain plugin adds its own skills, agents, references, and bootstrap docs

That means future plugins can follow the same pattern without reinventing the platform:

- `lawyer-aiws`
- `marketologist-aiws`
- `product-manager-aiws`
- other domain-specific plugins

A new plugin should not need to reimplement:

- SOP
- self-improvement workflow
- shared memory contracts
- project-memory boundaries

It should only contribute:

- domain workflows
- domain agents
- domain references
- domain-specific bootstrap and integration guidance

## Install

In Claude Code:

```text
/plugin marketplace add sashakang/ai-workspace
/plugin install core-aiws@ai-workspace
/plugin install memory-aiws@ai-workspace
/plugin install data-analysis-aiws@ai-workspace
```

Then install the host helper once:

```bash
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
aiws-host-memory doctor
```

Then restart Claude Code if prompted.
If you already installed an older helper build, reinstall it and rerun `bootstrap` so the managed hook is migrated from `Stop` to `SessionEnd`.

If you already installed the marketplace earlier and want the latest plugin state, refresh and reinstall the relevant plugin.

## Current State

This platform is installable now as an early alpha.

What is real today:

- shared process foundation
- shared memory contract layer
- one example domain plugin for data analysts
- one host-side helper for registry bootstrap, `SessionEnd` hook setup, and shared-memory refresh

What that means in practice:

- the architecture is real
- the install path is real
- the analyst workflows are real
- the platform is still early and intended to expand with more plugins over time

## Repository Layout

```text
ai-workspace/
├── aiws-host-memory/
├── core-aiws/
├── memory-aiws/
├── data-analysis-aiws/
└── docs/
```

Each plugin is independently installable from the marketplace, but they are developed together because they share contracts and architecture.

## Development

Repository path:

`~/Documents/ai-workspace/`

Local runtime testing:

```bash
claude \
  --plugin-dir ~/Documents/ai-workspace/core-aiws \
  --plugin-dir ~/Documents/ai-workspace/memory-aiws \
  --plugin-dir ~/Documents/ai-workspace/data-analysis-aiws
```

The helper can be tested locally from this repo with:

```bash
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
```

End users should install through the marketplace, not by cloning or symlinking the repo.

## Read More

- [Platform architecture](./docs/ai-workspace-architecture.md)
- [GitHub and rollout strategy](./docs/ai-workspace-github-rollout-strategy.md)

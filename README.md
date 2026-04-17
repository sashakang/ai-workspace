# AI Workspace

This repository is a small AI workspace for Claude Code.

It is built around one idea: useful Claude workflows should be packaged as installable plugins, not left as personal setup, scattered prompts, or one-off local habits.

The platform currently gives teams:

- `core-aiws` for shared process and improvement workflows
- `memory-aiws` for shared cross-project memory contracts
- `data-analysis-aiws` for analyst workflows
- `software-engineer-aiws` for SOP-governed Python engineering work

## What It Is For

Use this platform when you want Claude Code to behave less like a blank assistant and more like a reusable working system.

It is meant for teams that want:

- shared operating procedures across Claude sessions
- reusable domain workflows instead of ad hoc prompting
- memory boundaries between project memory, shared memory, and runtime state
- a path to ship more domain plugins over time

In practice, this means you install the shared foundation once, then add only the domain plugins you actually want.

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

### Domain plugins

The domain plugins today are `data-analysis-aiws` and `software-engineer-aiws`.

They currently provide:

- `data-analyst-forecast` (time-series forecasting)
- `analytical-research` (hypothesis-driven research with dual-gate review)
- `/dev` (thin SOP adapter for Python engineering work)

Some domain plugins are intentionally primed with references and bootstrap guidance. Others, like `software-engineer-aiws`, stay deliberately thin and rely on the shared SOP plus a small agent surface.

## Why This Is Extensible

This repository is not only an analyst plugin repo. It is a platform for adding more plugins with the same architecture.

The extensibility model is:

- `core-aiws` stays the shared process foundation
- `memory-aiws` stays the shared memory foundation
- each new domain plugin adds only the domain surfaces it actually needs

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
- domain references when needed
- domain-specific bootstrap and integration guidance when needed

## Install

In Claude Code, install the infrastructure plugins first:

```text
/plugin marketplace add sashakang/ai-workspace
/plugin install core-aiws@ai-workspace
/plugin install memory-aiws@ai-workspace
```

Then install whichever domain plugins you want:

```text
/plugin install data-analysis-aiws@ai-workspace
/plugin install software-engineer-aiws@ai-workspace
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
The helper now bootstraps with only `core-aiws` and `memory-aiws`; optional domain plugins are discovered dynamically when they are installed.

## Current State

This platform is installable now as an early alpha.

What is real today:

- shared process foundation
- shared memory contract layer
- opt-in analyst and software-engineering domain plugins
- one host-side helper for Claude bootstrap, `SessionEnd` hook setup, shared-memory refresh, and Cowork same-machine imports

What that means in practice:

- the architecture is real
- the install path is real
- the analyst and engineering workflows are real
- the platform is still early and intended to expand with more opt-in domain plugins over time

## Repository Layout

```text
ai-workspace/
├── aiws-host-memory/
├── core-aiws/
├── memory-aiws/
├── data-analysis-aiws/
├── software-engineer-aiws/
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
  --plugin-dir ~/Documents/ai-workspace/data-analysis-aiws \
  --plugin-dir ~/Documents/ai-workspace/software-engineer-aiws
```

The helper can be tested locally from this repo with:

```bash
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
```

Cowork v1 uses the same canonical shared memory that Claude owns under `memory-aiws`. It does not create a second canonical store. `bootstrap-cowork` and `refresh-cowork` attach a Cowork runtime to that Claude-owned memory on the same machine, and `refresh-cowork` rebuilds Cowork imports only.

End users should install through the marketplace, not by cloning or symlinking the repo.

## Read More

- [Platform architecture](./docs/ai-workspace-architecture.md)
- [GitHub and rollout strategy](./docs/ai-workspace-github-rollout-strategy.md)

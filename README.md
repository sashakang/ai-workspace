# AI Workspace

AI Workspace is a learning facilitation mechanism for teams using AI coding and productivity hosts.

Every skill is a piece of crystallized know-how about a recurring task. When a user discovers a better way to do that task, they propose it back to the skill's source repository. The maintainer curates incoming proposals into a single canonical SKILL.md, and that curated version flows back to every user through install or refresh. One person's discovery becomes the team's working knowledge — without forking, vendoring, or manual sync.

To make this possible, AIWS is provider-agnostic and treats every skill as a repo-backed artifact that can be discovered, validated, installed, materialized, edited locally, and proposed back through a pull request. The same skill source works across supported hosts (Claude Code, Codex, Cowork) because AIWS generates the host-specific output each app needs.

The system is built around three ideas:

- skills live in repositories
- access to skills is controlled by repository visibility and permissions
- shared infrastructure, such as self-improvement workflows and memory contracts, should be reused across all skill levels

AI Workspace currently has real support for Claude Code and early support paths for Codex and Cowork. The target compatibility set is:

- Codex app
- Codex CLI
- Claude Code CLI
- Claude Code Desktop
- Claude Cowork Desktop

The intended local shape is a single workspace folder containing all relevant skill and infrastructure repositories. All supported hosts can read from that shared workspace, while AI Workspace generates the host-specific files each app needs.

This repository currently includes:

- `core-aiws` for shared process and improvement workflows
- `memory-aiws` for shared cross-project memory contracts
- `aiws-productivity` as a small demo domain plugin
- `data-analysis-aiws` for analyst workflows
- `software-engineer-aiws` for SOP-governed Python engineering and technical documentation work

## What It Is For

Use this platform when you want AI hosts to work from a structured skill system instead of ad hoc prompting.

It is meant for people and teams that want:

- shared operating procedures across host sessions
- reusable domain workflows instead of ad hoc prompting
- memory boundaries between project memory, shared memory, and runtime state
- a path to ship more skills and domain plugins over time
- a local contribution loop for improving skills and proposing changes back to their source repositories

AI Workspace does not force every AI provider to use the same native plugin format. Different hosts expect different shapes: Claude Code may need one plugin or skill layout, Codex may need another local skill layout, and Cowork may need a packaged plugin-style output. AI Workspace keeps the skill source model consistent, then creates the right host-specific output for each app.

## How The Platform Is Structured

The platform is intentionally split into shared infrastructure and repo-backed skill layers rather than one large monolith.

This repository contains two kinds of plugins:

- infrastructure plugins, which provide shared behavior needed by the skill system itself
- domain plugins, which provide example skill sets for specific kinds of work

Users should install the infrastructure plugins plus only the domain plugins that are relevant to their work. A data analyst should not need to install a software-engineering plugin unless they want those workflows, and a software engineer should not need analyst workflows unless they are useful.

This repository is not the whole ecosystem. Other repositories can provide additional infrastructure or domain plugins for a person, project team, unit, company, or open-source community. Those external plugins still participate in the same shared architecture: they can live alongside this repository inside the same local AI Workspace folder, use the same infrastructure plugins, follow the same contracts, and produce host-specific output for the same supported apps.

This keeps the system modular: shared infrastructure is reused across all skill levels, while domain capabilities remain opt-in.

### `core-aiws`

The shared process layer.

It provides:

- the platform SOP
- the public `aiws-improve` workflow
- shared protocols that other plugins can depend on

### `memory-aiws`

The shared memory layer.

It defines:

- the cross-plugin shared-memory model
- import and export contracts
- automatic candidate capture and consolidation rules
- the boundary between authoritative docs and advisory shared memory

### Domain plugins

The example domain plugins today are `aiws-productivity`, `data-analysis-aiws`, and `software-engineer-aiws`.

They currently provide:

- `meeting-followup` (meeting notes to minutes, decisions, action items, and follow-up drafts)
- `data-analyst-forecast` (time-series forecasting)
- `analytical-research` (hypothesis-driven research with dual-gate review)
- `/dev` (thin SOP adapter for Python engineering work)
- `writing-documentation` (AIWS-aware technical documentation, docs audits, and docs-as-code maintenance)

Some domain plugins are intentionally primed with references and bootstrap guidance. Others, like `software-engineer-aiws`, stay deliberately thin and rely on the shared SOP plus a small agent surface.

## Skill Levels And Access

AI Workspace assumes that skills and plugins are distributed through repositories. Repository access defines who can see and use them, while the local AI Workspace folder gives supported hosts one shared place to discover, edit, test, and materialize them.

For example:

- a public GitHub repository can provide open-source skills
- a personal private repository can provide one user's private skills
- a company repository can provide company-wide skills
- a unit repository can provide skills for a department, function, or operating group
- a project repository can provide skills for the project team

The system should not need a separate permission model for skills if the repository host already controls access. AIWS focuses on discovery, validation, installation, materialization, local editing, host compatibility, and shared infrastructure.

## Local Skill Editing And Review

AI Workspace also supports a contribution loop for skills.

A skill can be installed or materialized locally, edited in the workspace, tested against a supported host, and staged as a proposal for a specific target repository. A later explicit submit-for-review action can create or update a pull request. The source repository remains the canonical home of the skill.

The review and merge process stays with the repository owner:

- personal skills can be reviewed and merged by the user
- company skills can be reviewed by the appropriate skill owner or team
- open-source skills can follow the public repository's normal contribution process
- unit skills can be reviewed by the owning unit or delegated maintainers
- project-team skills can be reviewed by the project maintainers

This keeps local iteration fast while preserving ownership, review, and canonical versioning in the source repo. AI Workspace should help with the mechanics of editing, validating, packaging, and proposing changes, but it should not bypass the repo's normal review process.

For private and non-public skills, the near-term maintainer workflow is a Claude Code "skill workshop": maintainers use Claude Code skills, workflows, and commands to update source, validate contracts, build Cowork packages, push through the maintainer or bot identity, and prepare marketplace artifacts on demand. That workflow is for maintainers, not normal Cowork users. Cowork remains the user-facing place to install and use skills, and the richer Cowork edit UX is deferred until the runtime and security model are clean.

## Why This Is Extensible

This repository is not only an analyst plugin repo. It is a platform for adding more repo-backed skills and plugins with the same architecture.

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
/plugin install aiws-productivity@ai-workspace
/plugin install data-analysis-aiws@ai-workspace
/plugin install software-engineer-aiws@ai-workspace
```

For skills-only Cowork testing, install only:

```text
core-aiws
aiws-productivity
```

Do not install `memory-aiws` for that flow. Skill install, update, edit, test, and staged proposal creation are owned by the internal `core-aiws` skill-management bridge, with editable drafts under `~/.aiws/plugins/` and draft state under `~/.aiws/state/skill-drafts/`. Users stage proposals in Cowork first; a later explicit submit-for-review step can create the maintainer-facing PR.

You can also add additional Claude marketplaces for company, unit, or personal plugin repos. In v1, AIWS trusts marketplaces by the exact identifier Claude records for them. Installed plugins stay in the same local AIWS ecosystem, and plugins that declare shared-memory scopes read from or write to the same canonical `memory-aiws` store.

## Memory Helper Setup

This section is not part of the skills-only Cowork flow.

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
If you use additional marketplaces, pass them to the helper with repeated `--trusted-marketplace <identifier>` flags so those installed plugins are included in registry bootstrap and any shared-memory imports or outboxes they declare.

## Current State

This platform is installable now as an early alpha.

What is real today:

- shared process foundation
- skills-management validation and draft registry contracts
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
├── aiws-productivity/
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
  --plugin-dir ~/Documents/ai-workspace/aiws-productivity \
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

## Multi-marketplace rules

- `plugin_id` is the logical capability identity inside one local AIWS installation
- the same `plugin_id` may move between marketplaces over time and AIWS will migrate the runtime state it owns for that logical plugin
- if the same `plugin_id` is concurrently installed from more than one trusted marketplace, bootstrap fails until only one active copy remains
- `memory-aiws` remains one canonical local store in v1, and plugins participate in it only through their declared shared-memory scopes

## Read More

- [Platform architecture](./docs/ai-workspace-architecture.md)
- [GitHub and rollout strategy](./docs/ai-workspace-github-rollout-strategy.md)
- [Cowork skills marketplace architecture](./docs/aiws-skills-cowork-marketplace.md)
- [AIWS testing manual](./docs/aiws-testing-manual.md)

# AI Workspace

AI Workspace is a management solution for AI **Skills** and **Memory**.

Skills and memory are the two durable assets that make AI work compound. A skill captures a repeatable way to perform valuable work: a procedure, checklist, domain method, prompt pattern, tool workflow, or review standard. Memory captures reusable context: preferences, project facts, lessons learned, operating constraints, and cross-session knowledge.

Together, they are the main sources of AI productivity. Without managed skills, every session starts from ad hoc prompting. Without managed memory, every session rediscovers context, repeats mistakes, or drifts from the user's real working environment. AI Workspace exists to make both assets reliable, portable, reviewable, and improvable.

## General Requirements

Any serious Skills and Memory management system needs these properties:

1. **Canonical ownership**
   Skills and memory need clear sources of truth. Teams must know where an asset lives, who can change it, how review works, and which copy is authoritative.

2. **Host portability**
   The same skill or memory asset should work across AI hosts even when each host needs a different native format. Source should stay stable; adapters should handle host-specific packaging.

3. **Lifecycle management**
   The system must support discovery, install, refresh, local use, editing, validation, proposal, review, merge, and rollback. A skill is not just a file; it has an operating lifecycle.

4. **Permission alignment**
   Access should follow existing repository, folder, marketplace, or organization permissions. The skill system should not invent a weaker parallel permission model.

5. **Validation and safety**
   Skills and memory need structure, metadata, integrity checks, and boundaries. The system must distinguish source truth, runtime copies, generated artifacts, pending proposals, and advisory memory.

6. **Continuous improvement**
   Every meaningful service procedure should end by asking what the run taught the system. Repeated confusion, bad routing, missing checks, or manual workarounds should feed back into skills, protocols, or memory through an explicit improvement path.

## What This Repository Provides

This repository is the reference AI Workspace implementation.

It contains shared infrastructure for:

- managing repo-backed and Drive-backed skills
- defining portable skill-library conventions
- validating skill and proposal structure
- packaging skills for supported hosts
- managing shared memory contracts
- running SOP-governed service procedures
- capturing self-improvement opportunities

It also contains example domain plugins that show how specialized skill sets can reuse the same infrastructure.

The current compatibility target is:

- Codex app
- Codex CLI
- Claude Code CLI
- Claude Code Desktop
- Claude Cowork Desktop

Different hosts can require different runtime shapes. AI Workspace keeps the source model consistent, then generates or guides the host-specific output each app needs.

## Core Concepts

### Skills

A skill is crystallized know-how for a recurring task. It may describe a process, domain method, prompt workflow, tool interaction, review gate, or expected output format.

AI Workspace treats skills as managed assets:

- they have source locations
- they can be validated
- they can be installed or materialized for a host
- they can be edited locally
- they can be proposed back to their source
- they can be reviewed and promoted by owners

For teams, this means one person's better way of working can become shared working knowledge without copy-paste drift.

### Memory

Memory is reusable context that helps future sessions work with less rediscovery.

AI Workspace separates memory from authoritative documentation. Memory can advise a session, but it should not silently override source files, contracts, runbooks, or explicit user instructions.

The memory layer defines:

- project memory
- shared cross-plugin memory
- import and export contracts
- automatic capture candidates
- consolidation and promotion rules
- boundaries between advisory memory and source truth

### Self-Improvement

Self-improvement is the feedback loop for the system itself.

At the end of a service procedure, the agent checks whether the run exposed a reusable improvement: unclear skill wording, missing validation, bad routing, stale assumptions, artifact mismatch, repeated manual work, or a better procedure. If the evidence is real, the improvement is routed into the appropriate skill, protocol, documentation, or memory path. If nothing actionable was learned, the procedure says so explicitly and stops.

## Architecture

AI Workspace is intentionally modular. Shared infrastructure stays separate from domain skills.

This repository currently includes:

- `core-aiws` - shared process, skill-library workflows, validation, and self-improvement
- `memory-aiws` - shared memory contracts and canonical memory structure
- `aiws-productivity` - a small productivity domain plugin
- `data-analysis-aiws` - analyst and forecasting workflows
- `software-engineer-aiws` - SOP-governed engineering and documentation workflows
- `aiws-host-memory` - host helper for Claude/Cowork memory bootstrap flows

Infrastructure plugins provide capabilities that many domains reuse. Domain plugins stay opt-in and contribute only the workflows, references, and agents needed for their area.

## Skill Distribution Models

AI Workspace supports more than one source model.

### Repo-Backed Skills

Skills and plugins can live in repositories. Repository access controls who can see and use them:

- public repositories for open-source skills
- personal private repositories for individual skills
- company repositories for company-wide skills
- unit repositories for department or function skills
- project repositories for project-team skills

The source repository remains the canonical home. Local edits can be staged as proposals and submitted for review through the owner's normal process.

### Drive Skill Libraries

For Cowork-oriented workflows, AI Workspace also supports a lightweight Google Drive Skill Library shape:

```text
<Library root>/
  skills/
    <skill-id>/
      SKILL.md
  Proposals/
    Submitted/
    Approved/
    Rejected/
```

Cowork can install or refresh the Drive library as a plugin-like container. AI Workspace provides the convention, validation, proposal structure, packaging requirements, and service procedures.

Drive is the review and collaboration surface. AI Workspace does not replace maintainer judgment; it helps keep the folder structure, proposal metadata, and refresh process coherent.

## Service Procedures

The `core-aiws` service skills cover the main Skill Library lifecycle:

- `aiws-validate-skill-library` checks Drive library and proposal structure
- `aiws-check-skill-library` checks Drive source plus installed Cowork plugin status
- `aiws-install-drive-skill-library` packages a Drive library as a Cowork plugin artifact
- `aiws-propose-skill-update` prepares a proposed `SKILL.md` under `Proposals/Submitted/`
- `aiws-update-skill-library` verifies maintainer-applied changes
- `aiws-refresh-skill-library` refreshes a Cowork-installed Drive library from Drive source
- `aiws-improve` routes accumulated improvement evidence through the self-improvement protocol

Every service procedure ends with a self-improvement checkpoint. The checkpoint must not mutate user content or runtime state. It only reports a concrete follow-up improvement when the run produced evidence for one.

## Local Skill Editing And Review

AI Workspace supports a contribution loop for skills.

A skill can be installed or materialized locally, edited in the workspace, tested against a supported host, and staged as a proposal for a target repository or Drive library. A later review step promotes the accepted version into the canonical source.

The review and merge process stays with the owner:

- personal skills can be reviewed and merged by the user
- company skills can be reviewed by the appropriate skill owner or team
- open-source skills can follow the public repository's normal process
- unit skills can be reviewed by the owning unit or delegated maintainers
- project-team skills can be reviewed by project maintainers

AI Workspace helps with mechanics: reading, validating, packaging, comparing, proposing, and refreshing. It should not bypass ownership or review.

## Extensibility

This repository is not the whole ecosystem. Other repositories can provide additional infrastructure or domain plugins for a person, project team, unit, company, or open-source community.

Future domain plugins can follow the same pattern:

- `lawyer-aiws`
- `marketologist-aiws`
- `product-manager-aiws`
- other domain-specific plugins

A new domain plugin should not reimplement the shared foundations:

- SOP
- self-improvement workflow
- shared memory contracts
- project-memory boundaries
- skill-library validation rules

It should contribute only the domain workflows, references, agents, and integration guidance it actually needs.

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

Do not install `memory-aiws` for that flow. Skill install, update, edit, test, and staged proposal creation are owned by the internal `core-aiws` skill-management bridge, with editable drafts under `~/.aiws/plugins/` and draft state under `~/.aiws/state/skill-drafts/`.

You can also add additional Claude marketplaces for company, unit, or personal plugin repos. In v1, AIWS trusts marketplaces by the exact identifier Claude records for them.

## Memory Helper Setup

This section is not part of the skills-only Cowork flow.

Install the host helper once:

```bash
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
aiws-host-memory doctor
```

Restart Claude Code if prompted.

If you already installed an older helper build, reinstall it and rerun `bootstrap` so the managed hook is migrated from `Stop` to `SessionEnd`.

The helper bootstraps with `core-aiws` and `memory-aiws`; optional domain plugins are discovered dynamically when they are installed. If you use additional marketplaces, pass them to the helper with repeated `--trusted-marketplace <identifier>` flags so those installed plugins are included in registry bootstrap and shared-memory imports or outboxes they declare.

Cowork v1 uses the same canonical shared memory that Claude owns under `memory-aiws`. It does not create a second canonical store. `bootstrap-cowork` and `refresh-cowork` attach a Cowork runtime to that Claude-owned memory on the same machine, and `refresh-cowork` rebuilds Cowork imports only.

## Current State

This platform is installable now as an early alpha.

What is real today:

- shared process foundation
- Drive Skill Library service procedures
- skills-management validation and draft registry contracts
- shared memory contract layer
- opt-in analyst, productivity, and software-engineering domain plugins
- one host-side helper for Claude bootstrap, `SessionEnd` hook setup, shared-memory refresh, and Cowork same-machine imports

What that means in practice:

- the architecture is real
- the install path is real
- the service-skill procedures are real
- the domain workflows are real
- the platform is still early and will expand with more opt-in domain plugins and host-specific adapters

## Repository Layout

```text
ai-workspace/
|-- aiws-host-memory/
|-- core-aiws/
|-- memory-aiws/
|-- aiws-productivity/
|-- data-analysis-aiws/
|-- software-engineer-aiws/
`-- docs/
```

Each plugin is independently installable from the marketplace, but they are developed together because they share contracts and architecture.

## Development

Repository path:

```text
/Users/aleksanderkan/projects/ai-workspace
```

Local runtime testing:

```bash
claude \
  --plugin-dir /Users/aleksanderkan/projects/ai-workspace/core-aiws \
  --plugin-dir /Users/aleksanderkan/projects/ai-workspace/memory-aiws \
  --plugin-dir /Users/aleksanderkan/projects/ai-workspace/aiws-productivity \
  --plugin-dir /Users/aleksanderkan/projects/ai-workspace/data-analysis-aiws \
  --plugin-dir /Users/aleksanderkan/projects/ai-workspace/software-engineer-aiws
```

End users should install through the marketplace, not by cloning or symlinking this repository.

## Multi-Marketplace Rules

- `plugin_id` is the logical capability identity inside one local AIWS installation
- the same `plugin_id` may move between marketplaces over time, and AIWS migrates the runtime state it owns for that logical plugin
- if the same `plugin_id` is concurrently installed from more than one trusted marketplace, bootstrap fails until only one active copy remains
- `memory-aiws` remains one canonical local store in v1, and plugins participate in it only through their declared shared-memory scopes

## Read More

- [Platform architecture](./docs/ai-workspace-architecture.md)
- [GitHub and rollout strategy](./docs/ai-workspace-github-rollout-strategy.md)
- [Cowork skills marketplace architecture](./docs/aiws-skills-cowork-marketplace.md)
- [AIWS testing manual](./docs/aiws-testing-manual.md)
- [AIWS Skill Library Phase 1 plan](./docs/aiws-skill-library-phase1-plan.md)

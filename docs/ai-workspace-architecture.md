# AI Workspace Architecture

Updated: 2026-03-26

## Purpose

This document defines the durable architecture for the AI workspace around three facts:

1. Claude Code now has native project memory and Auto memory behavior.
2. Autodream appears to consolidate and organize project memory in the background.
3. Cross-project and cross-domain memory still needs a dedicated shared layer that is not tied to any one domain plugin.

The design goal is to align with Claude-native memory instead of competing with it, while still providing a shared cross-plugin memory system and domain-specific plugins.

## Core Principles

- Use Claude-native project memory as the canonical project memory system.
- Do not build a second project-memory platform that duplicates Autodream.
- Put shared process assets in `core-aiws`, not in domain plugins or the memory plugin.
- Keep shared cross-project memory in a dedicated memory plugin, not in a domain plugin.
- Keep operational runtime state separate from durable memory.
- Make domain plugins consumers and contributors to shared memory, not owners of the entire memory stack.
- Treat plugin and memory changes as SOP-governed work, not ad hoc edits.

## Source vs Runtime

The platform has two different filesystem roles:

- source repo:
  - `~/Documents/ai-workspace/`
- local runtime surface:
  - `~/.claude/plugins/`

During local development, run Claude with explicit `--plugin-dir` arguments pointing at the plugin roots in the source repo.

For users, installation happens through the marketplace, not through git clone or symlinks.

## SOP Governance

This platform architecture is governed by the Universal SOP packaged in [`core-aiws/protocols/sop.md`](../core-aiws/protocols/sop.md).

During migration, a compatibility copy may remain in the live `.claude` workspace. It is not the intended long-term plugin home of the SOP.

Implications for this platform:

- architecture changes are `complex` by default
- plugin plans must go through Gate 1 before implementation
- implementation outputs must go through Gate 2 before delivery
- Phase 9 self-improvement is mandatory after non-lightweight work

### Gate 1 for platform changes

Changes to the shared memory architecture, plugin boundaries, prompt/protocol contracts, or Autodream coexistence assumptions should be reviewed at Gate 1 by:

- `architecture-simplifier`
- `prompt-engineer`
- one domain reviewer relevant to the plugin being changed

For memory-plugin-wide changes that affect multiple domain plugins, include at least one additional reviewer representing execution realism, such as:

- `ai-engineer`
- `backend-python-engineer`

### Gate 2 for platform changes

Prompt, protocol, architecture, and documentation outputs for this platform should be reviewed at Gate 2 by:

- `prompt-engineer`
- `architecture-simplifier`
- a domain reviewer for impacted plugin behavior

If code or runtime mechanics are involved, add:

- `code-reviewer`
- `backend-python-engineer`

### Session logging

Structured plugin-managed session logging is a deferred `core-aiws` capability, not part of v1.

For v1, the evidence base is:

- Claude Code native session history
- observations
- project memory
- approved architecture and implementation documents

If structured session logs are later introduced, they should be centralized in `core-aiws`, not reimplemented in domain plugins.

## Memory Layers

### 1. Raw session history

Claude Code session JSONL files are the raw historical substrate.

Purpose:

- full conversation and tool history
- debugging and auditability
- evidence source for analysis

This layer is not curated memory. It is too large and noisy to be treated as durable working knowledge directly.

### 2. Project memory

Claude-native project memory lives under:

`~/.claude/projects/<project>/memory/`

This is the canonical project memory layer. Local evidence suggests Claude Auto memory and Autodream consolidate and organize this surface.

Purpose:

- project-specific durable knowledge
- daily logs and recent learnings
- stable project conventions and findings
- curated project-level MEMORY.md and topic files

Observed evidence from local inspection:

- Autodream touched only project memory files in the benchmark and AI analyst query processor projects.
- It updated project `MEMORY.md`.
- It touched recent daily logs.
- In at least one case it created or updated a focused topic file (`ops_quirks.md`) from daily-log learnings.
- No evidence was found that it reads or manages plugin-private folders under `~/.claude/plugins/...`.

Conclusion:

- if knowledge should be visible to Claude-native project memory and Autodream, it must be written directly into project memory
- plugin-private folders must not be assumed to be part of Autodream's scan surface

### Project memory access contract

Claude-native project memory remains canonical, but plugins must not treat `~/.claude/projects/<project>/memory/` as a direct runtime dependency.

V1 contract:

- a host-side bridge or bootstrap step imports the active project's relevant memory files into `${CLAUDE_PLUGIN_DATA}/project-memory/current/`
- plugins read project memory only from that imported local snapshot at runtime
- approved durable writes are staged locally, then applied back to Claude-native project memory through the same host-side bridge
- Autodream continues to operate on the native project-memory surface, not on plugin-local snapshots

### 3. Shared cross-plugin memory

Shared cross-plugin memory is owned by a dedicated memory plugin.

Canonical durable store:

`${memory_sk_plugin_data}/shared-memory/`

Where:

- `${memory_sk_plugin_data}` means `${CLAUDE_PLUGIN_DATA}` resolved for `memory-aiws`
- for example, `memory-aiws@ai-workspace` would persist canonical shared memory under `~/.claude/plugins/data/memory-aiws-ai-workspace/shared-memory/`

Recommended runtime layout:

```text
${memory_sk_plugin_data}/
├── shared-memory/
│   ├── MEMORY.md
│   ├── global/
│   │   ├── user-preferences.md
│   │   ├── tool-quirks.md
│   │   ├── workflow-patterns.md
│   │   └── prompt-improvement-patterns.md
│   ├── domains/
│   │   ├── data-analyst/
│   │   ├── lawyer/
│   │   ├── marketologist/
│   │   └── product-manager/
│   └── indexes/
├── state/
├── cache/
└── logs/
```

Purpose:

- cross-project durable memory
- cross-domain reusable patterns
- shared user preferences and tool quirks
- memory contracts and utilities used by multiple domain plugins

This memory is not owned by the analyst plugin. It is shared infrastructure for all plugins.

Important distinction:

- in `memory-aiws`, `${CLAUDE_PLUGIN_DATA}/shared-memory/` is the canonical durable store
- in dependent plugins, `${CLAUDE_PLUGIN_DATA}/shared-memory/` is only an imported local snapshot for reads
- marketplace checkout paths and plugin cache paths are code-distribution surfaces, not the durable shared-memory home

## Shared Process Layer

Shared process behavior is owned by `core-aiws`.

Recommended root:

`~/.claude/plugins/core-aiws/`

Owned surfaces:

- `core-aiws/protocols/sop.md`
- `core-aiws/skills/improve/SKILL.md` implementing the public `/aiws-improve` surface
- future shared process conventions that apply across plugins

`core-aiws` does not own:

- shared durable memory
- project memory organization
- domain workflows

## `/aiws-improve` and Self-Improvement

`/aiws-improve` is governed by [`core-aiws/skills/improve/SKILL.md`](../core-aiws/skills/improve/SKILL.md) and the self-improvement protocol it invokes.

For this platform, `/aiws-improve` has a specific role:

- gather evidence from observations, daily logs, session logs, and current context
- synthesize recurring process and prompt failures
- propose changes to skills, agents, hooks, prompts, and protocols

It does not replace the memory layer or act as the routine shared-memory refresh trigger.

### Evidence sources relevant to this platform

When reviewing platform issues, `/aiws-improve` should use:

- `${CLAUDE_PLUGIN_DATA}/improve/observations.jsonl`
- the current project's imported daily logs from `${CLAUDE_PLUGIN_DATA}/project-memory/current/`
- Claude Code native session history when available through the host environment
- current architecture and implementation documents
- installed plugin contracts from `${CLAUDE_PLUGIN_DATA}/registry/plugins/*.json`

### What `/aiws-improve` may change

Appropriate targets:

- skill instructions
- agent prompts
- hook logic
- bootstrap docs
- protocol files
- architecture and implementation plan documents when they are stale or contradictory

### What `/aiws-improve` must not be treated as

- not the shared memory platform
- not the project-memory organizer
- not a substitute for Autodream
- not the owner of durable knowledge taxonomy

## Plugin Types

### Core plugin

The core plugin owns:

- shared SOP and process conventions
- shared `/aiws-improve`
- any shared process-control assets reused by multiple plugins

The core plugin does not own:

- project memory
- shared durable memory
- domain workflows

### Memory plugin

The memory plugin owns:

- shared memory structure
- memory taxonomy and write rules
- shared indexes and retrieval helpers
- any shared-memory maintenance that is not Claude-native

The memory plugin does not replace project memory. It complements it.

The memory plugin has a hard dependency on `core-aiws` for shared SOP and process behavior.

### Shared memory access contract

V1 must not rely on dependent plugins reading files directly from another plugin's runtime root.

V1 contract:

- `memory-aiws` owns the canonical shared-memory layout, consolidation rules, and export format under `${memory_sk_plugin_data}/shared-memory/`
- a host-side shared-memory bridge executes automatic post-response refresh
- producer plugins do not write canonical shared memory directly
- instead, each producer plugin stages reusable candidates in its own `${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/`
- "staging" means writing a local candidate event for later consolidation by the bridge
- the bridge consolidates staged candidates into canonical shared memory, then imports the needed snapshot into each dependent plugin's own `${CLAUDE_PLUGIN_DATA}/shared-memory/`
- runtime reads happen only against the dependent plugin's local imported snapshot
- direct sibling-plugin filesystem reads are not part of the supported runtime contract

### Plugin metadata contract

Every plugin must publish a machine-readable contract in addition to its normal plugin manifest.

Required fields:

- `plugin_id`
- `version`
- `public_skills`
- `public_agents`
- `dependencies`
- `project_memory_read_scope`
- `project_memory_write_scope`
- `shared_memory_read_scope`
- `shared_memory_write_scope`
- `improve_targets`

`core-aiws` uses these contracts to reason about installed plugins and target `/aiws-improve` proposals without ad hoc filesystem spelunking.

### Domain plugins

Examples:

- `data-analyst-aiws`
- `lawyer-aiws`
- `marketologist-aiws`
- `product-manager-aiws`

Domain plugins own:

- skills
- agents
- references
- MCP integration and bootstrap docs
- domain-specific operational state
- dependency on `core-aiws`

Domain plugins do not own:

- the shared memory layer
- Autodream behavior
- the project-memory consolidation process
- shared `/aiws-improve`

## Memory Ownership Rules

### Write to project memory when

- the knowledge is specific to one project
- the knowledge should be part of Claude-native project recall
- the knowledge should be eligible for Autodream promotion or consolidation
- the knowledge belongs in project daily logs, project `MEMORY.md`, or project topic files

Examples:

- benchmark campaign status
- project-specific deployment quirks
- a daily analyst finding tied to one codebase or dataset
- project-local operating conventions

### Write to shared memory when

- the knowledge is useful across multiple projects
- the knowledge is useful across multiple plugins
- the knowledge is not owned by a single project
- the knowledge should persist independently of any one project's history

Examples:

- user communication preferences
- shared tool quirks
- reusable query patterns
- cross-project notebook conventions
- prompt-improvement patterns that apply to multiple plugins

### Keep as plugin-local runtime state when

- the data exists to make the plugin work correctly
- the data is operational, transient, or recoverability-focused
- the data should not be treated as durable knowledge

Examples:

- bootstrap markers
- schema caches
- journals and locks
- plugin debug logs
- transient carryover records

## Domain Plugin Runtime Structure

Each domain plugin keeps its operational state under its own root.

Example:

```text
${CLAUDE_PLUGIN_DATA}/
├── state/
├── cache/
├── shared-memory/
├── project-memory/
├── logs/
└── sessions/
```

This is not memory in the durable-knowledge sense. It is the plugin's control plane.

During local repo-based development with `--plugin-dir`, runtime-mutated state must not be treated as tracked source:

- prefer `${CLAUDE_PLUGIN_DATA}` for mutable runtime state
- if repo-local runtime artifacts are unavoidable during development, they must be gitignored

### What goes there

`state/`

- bootstrap completion markers
- journals for multi-step plugin operations
- carryover or handoff state if the plugin needs it
- plugin-local metadata required for correctness

`cache/`

- fetched schema caches
- derived artifact caches
- retrieval helper caches

`logs/`

- plugin operational logs
- background task logs
- recovery/debug logs

`sessions/`

- small plugin-scoped session summaries if needed
- not full Claude transcript history

### How this differs from Claude native JSONL logs

Claude JSONL sessions are raw event history:

- full transcript
- tool calls
- user/assistant messages
- large and noisy

Plugin runtime state is structured control data:

- small
- purpose-built
- operational
- not intended as long-term knowledge

## Autodream Implications

Autodream changes the architecture in an important way:

- project memory should be treated as a first-class Claude-native platform capability
- custom project-memory consolidation logic should be minimized
- domain plugins should produce good memory inputs rather than replacing Autodream

Practical consequence:

- if a domain plugin wants Claude-native memory to pick up a durable project learning, it should write it directly into project memory
- domain plugins should not expect Autodream to discover plugin-private artifacts automatically

## Data Flow

### Project-specific knowledge flow

1. Work happens in Claude Code sessions.
2. High-signal learnings are written into project memory.
3. Autodream consolidates and reorganizes project memory.
4. Future project sessions read Claude-native project memory.

### Cross-project knowledge flow

1. A domain plugin finishes non-lightweight work and stages reusable candidates in its local outbox.
2. The host-side shared-memory bridge runs after the response and invokes the `memory-aiws` consolidator/exporter.
3. `memory-aiws` updates canonical shared memory under `${memory_sk_plugin_data}/shared-memory/` and publishes a versioned snapshot.
4. Consumer plugins read the imported local shared-memory snapshot alongside project memory.

This is an explicit write path. It must not rely on Autodream to bridge from project memory into shared memory automatically.

### Process-improvement flow

1. Work sessions generate observations and daily logs.
2. `/aiws-improve` synthesizes those signals.
3. Approved changes update skills, agents, protocols, hooks, or docs.
4. Resulting architectural or workflow changes re-enter the SOP and receive Gate 1 / Gate 2 review as needed.

## Naming

Package ids:

- `core-aiws`
- `memory-aiws`
- `data-analyst-aiws`
- future examples: `lawyer-aiws`, `marketologist-aiws`, `product-manager-aiws`

Public analyst skill prefix:

- `data-analyst-*`

Examples:

- `data-analyst-forecast`

## Final Architecture Summary

The platform has three memory-related scopes:

1. Claude session history
   - raw, uncurated, transcript-level
2. Claude-native project memory
   - project-specific, Claude-native; local evidence suggests Autodream consolidates it
3. shared plugin memory
   - cross-project, cross-plugin, memory-plugin-managed

And two separate non-memory scopes:

4. shared process layer
   - `core-aiws`, SOP, and `/aiws-improve`
5. plugin-local runtime state
   - correctness, recovery, caching, logs

This is the intended long-term architecture.

## Architecture Maintenance Rules

- If Autodream behavior changes and local evidence contradicts this document, update this document through SOP-governed review.
- If a domain plugin starts depending on plugin-private memory being visible to Claude-native memory, that assumption must be proven with local evidence before adoption.
- If shared memory and project memory begin to drift semantically, resolve the taxonomy at the memory-plugin level rather than inside a domain plugin.

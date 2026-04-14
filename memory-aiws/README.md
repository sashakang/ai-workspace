# memory-aiws

`memory-aiws` is the shared durable memory plugin for the AI workspace.

It owns:

- shared cross-project memory structure
- shared memory taxonomy and write rules
- shared memory export and import contracts
- automatic candidate consolidation guidance for reusable cross-plugin learnings

It does not own:

- project memory managed by Claude-native memory and Autodream
- shared process behavior such as SOP and `/aiws-improve`
- domain-specific workflows

Current scaffold:

- `.claude-plugin/plugin.json`
- `contracts/`
- `memory/`
- `aiws_memory/`
- `scripts/`

Runtime note:

- mutable runtime state should resolve to `${CLAUDE_PLUGIN_DATA}` rather than being written into the source tree during development
- canonical durable shared memory lives under `${CLAUDE_PLUGIN_DATA}/shared-memory/` when `memory-aiws` is running
- for `memory-aiws@ai-workspace`, that would resolve to `~/.claude/plugins/data/memory-aiws-ai-workspace/shared-memory/`
- `memory-aiws` defines the consolidation and export logic, but a host-side shared-memory bridge executes refresh and consumer import updates

## Reference Runtime

This repository now includes a file-based Python reference implementation for the v1 shared-memory path.

`memory-aiws` owns only canonical shared-memory work:

- bootstrap canonical runtime state
- consolidate validated candidate events
- regenerate rendered shared-memory files
- publish export snapshots

It does not own:

- producer outbox writes
- registry population
- consumer import fan-out
- post-response hook wiring

### Canonical commands

Run these from the repo root:

```bash
python memory-aiws/scripts/aiws_memory_canonical.py bootstrap-canonical \
  --plugin-data .aiws-runtime/memory-aiws \
  --seed-root memory-aiws/memory

python memory-aiws/scripts/aiws_memory_canonical.py inspect \
  --plugin-data .aiws-runtime/memory-aiws --json
```

### Host helper

The host-side bridge is now packaged as the separate `aiws-host-memory` helper.

It provides:

- `bootstrap` — write helper config, populate the plugin-contract registry, bootstrap canonical memory, and install the managed global `Stop` hook
- `refresh-shared` — process producer outboxes, publish canonical shared memory, and refresh consumer imports
- `doctor` / `status` — show setup health and repair guidance

Example:

```bash
pipx install aiws-host-memory
aiws-host-memory bootstrap
aiws-host-memory doctor
```

Run `aiws-host-memory bootstrap` before the first `refresh-shared`. The refresh command depends on the helper config, the registry snapshot, and the canonical runtime all being in place.

Producer-side candidate staging stays inside the producer plugin. For `data-analysis-aiws`, use [stage_shared_memory_candidate.py](../data-analysis-aiws/scripts/stage_shared_memory_candidate.py) through the plugin-local wrapper, not through repo-root bridge code.

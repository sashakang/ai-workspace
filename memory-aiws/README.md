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

Runtime note:

- mutable runtime state should resolve to `${CLAUDE_PLUGIN_DATA}` rather than being written into the source tree during development
- canonical durable shared memory lives under `${CLAUDE_PLUGIN_DATA}/shared-memory/` when `memory-aiws` is running
- for `memory-aiws@ai-workspace`, that would resolve to `~/.claude/plugins/data/memory-aiws-ai-workspace/shared-memory/`
- `memory-aiws` defines the consolidation and export logic, but a host-side shared-memory bridge executes refresh and consumer import updates

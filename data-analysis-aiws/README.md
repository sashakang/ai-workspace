# data-analysis-aiws

`data-analysis-aiws` is the domain plugin for analyst workflows in the AI workspace.

It owns:

- time-series forecasting workflows
- analyst-specific agents, references, and bootstrap docs

It depends on:

- `core-aiws`
- `memory-aiws`
- `aiws-host-memory` for shared-memory refresh, registry bootstrap, and automatic hook setup

It does not own:

- shared process behavior such as SOP and `/aiws-improve`
- shared cross-plugin memory
- Claude-native project memory

Current useful slice:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `contracts/`
- `skills/`
- `agents/`
- `references/`
- `bootstrap/`

Implemented now:

- `data-analyst-forecast` skill (time-series forecasting)
- `analytical-research` skill (hypothesis-driven research with dual-gate review)
- one reusable `data-analyst` agent
- generic domain, analytical, and statistical reference notes
- bootstrap guidance for local runtime testing

Runtime note:

- mutable runtime state should resolve to `${CLAUDE_PLUGIN_DATA}` rather than being written into the source tree during development
- without `aiws-host-memory bootstrap`, analyst workflows still run, but shared-memory capture/import is disabled

# data-analyst-aiws

`data-analyst-aiws` is the domain plugin for analyst workflows in the AI workspace.

It owns:

- time-series forecasting workflows
- analyst-specific agents, references, and bootstrap docs

It depends on:

- `core-aiws`
- `memory-aiws`

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

- a usable `data-analyst-forecast` skill
- one reusable `data-analyst` agent
- generic domain, analytical, and statistical reference notes
- bootstrap guidance for local runtime testing

Runtime note:

- mutable runtime state should resolve to `${CLAUDE_PLUGIN_DATA}` rather than being written into the source tree during development

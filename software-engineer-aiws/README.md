# software-engineer-aiws

`software-engineer-aiws` is the optional domain plugin for SOP-governed software engineering work in the AI workspace.

It owns:

- the `/dev` skill as a thin engineering entrypoint
- Python-first support agents for implementation, debugging, TDD, review, and documentation

It depends on:

- `core-aiws`

This is an optional domain plugin. Users should install it only if they want software-engineering workflows on top of the shared process layer.

It does not own:

- the SOP or `/aiws-improve`
- shared cross-plugin memory
- Claude-native project memory
- infrastructure, deployment, SQL, or prompt/protocol workflows in v1

Current useful slice:

- `.claude-plugin/plugin.json`
- `contracts/`
- `skills/`
- `agents/`

Runtime note:

- this plugin is intentionally thin and defers default workflow behavior to `core-aiws/protocols/sop.md`
- in v1 it does not define shared-memory scopes or bootstrap-specific assets

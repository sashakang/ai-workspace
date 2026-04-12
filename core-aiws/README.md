# core-aiws

`core-aiws` is the shared process plugin for the AI workspace.

It owns:

- the platform SOP
- the shared `/aiws-improve` skill
- shared process protocols reused by other plugins

It does not own:

- shared durable memory
- project memory organization
- domain-specific workflows

Current scaffold:

- `.claude-plugin/plugin.json`
- `contracts/`
- `protocols/`
- `skills/improve/` implementing the public `/aiws-improve` surface

Contract files:

- `contracts/plugin-contract.schema.json`
- `contracts/core-aiws.contract.json`
- `contracts/plugin-registry.md`
- `contracts/project-memory-bridge.md`
- `contracts/shared-memory-import.md`
- `contracts/shared-memory-bridge.md`

Planned consumers:

- `memory-aiws`
- `data-analysis-aiws`
- future domain plugins such as `lawyer-aiws`, `marketologist-aiws`, and `product-manager-aiws`

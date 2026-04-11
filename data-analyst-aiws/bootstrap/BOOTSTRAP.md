# Bootstrap

Use this plugin with:
- `core-aiws`
- `memory-aiws`

## Local development

Run Claude with explicit plugin roots:

```bash
claude \
  --plugin-dir ~/Documents/ai-workspace/core-aiws \
  --plugin-dir ~/Documents/ai-workspace/memory-aiws \
  --plugin-dir ~/Documents/ai-workspace/data-analyst-aiws
```

## Required user setup

- provide user-specific access to the warehouse or analyst MCP
- set any required environment variables for the local MCP launcher
- confirm Claude can validate all three plugin manifests

## First smoke test

Verify that:
- `core-aiws@inline` loads
- `memory-aiws@inline` loads
- `data-analyst-aiws@inline` loads
- the `data-analyst-forecast` skill is visible in a session

## Security rule

Do not put live credentials in `.mcp.json`.
Use environment variables or user-local config paths instead.

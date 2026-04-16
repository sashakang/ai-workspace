# Bootstrap

Use this plugin with:
- `core-aiws`
- `memory-aiws`
- `aiws-host-memory`

## Marketplace install

Install the infrastructure plugins first, then add this domain plugin and run the helper:

```bash
/plugin marketplace add sashakang/ai-workspace
/plugin install core-aiws@ai-workspace
/plugin install memory-aiws@ai-workspace
/plugin install data-analysis-aiws@ai-workspace
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
aiws-host-memory doctor
```

If `aiws-host-memory` is not configured yet, the analyst skills still work, but shared-memory capture and imported shared-memory reads are unavailable.

## Local development

Run Claude with explicit plugin roots:

```bash
claude \
  --plugin-dir ~/Documents/ai-workspace/core-aiws \
  --plugin-dir ~/Documents/ai-workspace/memory-aiws \
  --plugin-dir ~/Documents/ai-workspace/data-analysis-aiws
```

## Required user setup

- provide user-specific access to the warehouse or analyst MCP
- set any required environment variables for the local MCP launcher
- confirm Claude can validate all three plugin manifests

## First smoke test

Verify that:
- `core-aiws@inline` loads
- `memory-aiws@inline` loads
- `data-analysis-aiws@inline` loads
- the `data-analyst-forecast` skill is visible in a session
- `aiws-host-memory bootstrap` completes successfully for the local plugin/data paths you are using

## Security rule

Do not put live credentials in `.mcp.json`.
Use environment variables or user-local config paths instead.

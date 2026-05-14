# Cowork MCP Smoke Plugin

This is a test-only proof package for AIWS Slice 2B.1. It exists to validate that Cowork can install a plugin ZIP and launch a bundled executable MCP server directly from `.mcp.json`, without relying on Python, `uv`, `uvx`, `gh`, Git, or shell commands at runtime.

The source plugin contains a tiny C stdio MCP server. Maintainers build a platform-specific ZIP with:

```bash
python -m scripts.build_cowork_mcp_smoke
```

The generated ZIP is written to `dist/cowork-smoke/` and should stay untracked. The installed package contains:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `README.md`
- `skills/smoke-check/SKILL.md`
- `bin/aiws-mcp-smoke`

At Cowork runtime, `.mcp.json` points directly to `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-smoke`. A normal installer should not compile anything and should not need terminal commands.

Version `0.1.1` adds a minimal visible skill so Cowork can enable the plugin through the normal skill path before checking MCP tool exposure.

## Cowork Runtime Result

Slice 2B.1 v0.1.1 is **blocked** for bundled stdio executable MCP server registration in the Cowork uploaded-plugin path.

Cowork evidence:

- The v0.1.1 plugin uploaded successfully.
- The `aiws-cowork-mcp-smoke:smoke-check` skill is visible.
- `skills/smoke-check/SKILL.md` is readable at the expected installed-plugin path.
- ToolSearch for `aiws smoke ping` returns no matching tool.
- No MCP server launch error surfaced.
- `aiws.smoke.ping` is absent.

The visible skill removes the earlier `MCP-only/no skills` variable. Cowork loaded the plugin through the skill surface, but did not register the MCP tool declared through this `.mcp.json` bundled stdio executable shape. This does not prove all executable approaches are impossible; it only records that this specific uploaded-plugin command/stdio runtime shape was not registered by Cowork.

Keep this smoke package as a reusable diagnostic. The next research direction is a Cowork-supported MCP transport shape, likely `type: "http"`, or a host/connector-owned runtime before packaging the real `aiws-mcp`.

The smoke server exposes one harmless tool:

- `aiws.smoke.ping`

For local maintainer validation, the executable also supports:

```bash
bin/aiws-mcp-smoke --self-test
```

That mode prints `aiws-cowork-mcp-smoke self-test ok` and exits with status 0. The actual Slice 2B.1 proof is Cowork showing and calling `aiws.smoke.ping` from the installed ZIP.

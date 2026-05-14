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
- `bin/aiws-mcp-smoke`

At Cowork runtime, `.mcp.json` points directly to `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-smoke`. A normal installer should not compile anything and should not need terminal commands.

The smoke server exposes one harmless tool:

- `aiws.smoke.ping`

For local maintainer validation, the executable also supports:

```bash
bin/aiws-mcp-smoke --self-test
```

That mode prints `aiws-cowork-mcp-smoke self-test ok` and exits with status 0. The actual Slice 2B.1 proof is Cowork showing and calling `aiws.smoke.ping` from the installed ZIP.

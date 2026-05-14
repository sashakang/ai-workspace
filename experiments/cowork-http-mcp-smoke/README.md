# Cowork HTTP MCP Smoke Plugins

This experiment builds two test-only Cowork upload packages to check whether uploaded plugins can register a remote HTTP MCP connector. It does not test the AIWS production runtime and does not package `aiws-mcp`.

Both variants point to the official public Claude docs MCP endpoint:

```text
https://code.claude.com/docs/mcp
```

Neither package includes bundled executables, stdio commands, Python, `uv`, `uvx`, `gh`, Git, shell runtime dependencies, secrets, auth headers, or source server code. The only runtime question is whether Cowork registers the remote HTTP MCP server declared by the uploaded plugin.

Build both ZIPs with:

```bash
python -m scripts.build_cowork_http_mcp_smoke
```

The generated ZIPs are written to `dist/cowork-http-smoke/` and should stay untracked.

## Variant A: Claude Documented Shape

Source: `variants/claude-documented-shape/`

Package name: `aiws-cowork-http-mcp-smoke-claude-shape`

MCP server name: `aiws-cowork-http-smoke-claude-docs`

`.mcp.json` uses the Claude Code documented top-level `mcpServers` object shape:

```json
{
  "mcpServers": {
    "aiws-cowork-http-smoke-claude-docs": {
      "type": "http",
      "url": "https://code.claude.com/docs/mcp"
    }
  }
}
```

Cowork test prompt:

```text
Use the aiws-cowork-http-mcp-smoke-claude-shape smoke-check skill. Check whether Cowork registered the remote Claude docs HTTP MCP server named aiws-cowork-http-smoke-claude-docs from this uploaded plugin. Look for Claude docs MCP tools, especially docs search/read tools. Do not look for aiws.smoke.ping. Report which Claude docs tools are visible and call one harmless docs search/read tool if available.
```

Acceptance condition: the uploaded plugin installs, the `smoke-check` skill is visible, Cowork exposes Claude docs MCP search/read tools from `aiws-cowork-http-smoke-claude-docs`, and a harmless docs search/read call succeeds. If the skill is visible but no Claude docs tools appear, this variant does not prove HTTP MCP registration through the uploaded-plugin path.

## Variant B: Cowork Top-Level Array Shape

Source: `variants/cowork-array-hypothesis/`

Package name: `aiws-cowork-http-mcp-smoke-cowork-array`

MCP server name: `aiws-cowork-http-smoke-cowork-array-docs`

This variant follows the Cowork server-object array shape from the Cowork 3P docs. `.mcp.json` is a top-level array of server objects with `name`, `url`, and `transport: "http"`:

```json
[
  {
    "name": "aiws-cowork-http-smoke-cowork-array-docs",
    "url": "https://code.claude.com/docs/mcp",
    "transport": "http"
  }
]
```

Cowork test prompt:

```text
Use the aiws-cowork-http-mcp-smoke-cowork-array smoke-check skill. Check whether Cowork registered the remote Claude docs HTTP MCP server named aiws-cowork-http-smoke-cowork-array-docs from this uploaded plugin. This plugin uses the Cowork top-level array HTTP MCP shape. Look for Claude docs MCP tools, especially docs search/read tools. Do not look for aiws.smoke.ping. Report which Claude docs tools are visible and call one harmless docs search/read tool if available.
```

Acceptance condition: the uploaded plugin installs, the `smoke-check` skill is visible, Cowork exposes Claude docs MCP search/read tools from `aiws-cowork-http-smoke-cowork-array-docs`, and a harmless docs search/read call succeeds. If the skill is visible but no Claude docs tools appear, this hypothesis is not supported by the uploaded-plugin path.

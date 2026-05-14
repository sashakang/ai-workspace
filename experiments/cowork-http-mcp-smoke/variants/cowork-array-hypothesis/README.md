# Cowork HTTP MCP Smoke: Cowork Top-Level Array Shape

This is a test-only Cowork upload package. It checks whether Cowork registers a remote HTTP MCP server from an uploaded plugin using a top-level server-object array shape.

This shape follows the Cowork 3P docs pattern where `managedMcpServers` is an array of server objects and plugin `.mcp.json` uses the same object format.

It points to the official public Claude docs MCP endpoint:

```text
https://code.claude.com/docs/mcp
```

This package includes no bundled executables, stdio commands, Python, `uv`, `uvx`, `gh`, Git, shell runtime dependencies, secrets, auth headers, or source server code. It tests remote HTTP MCP registration only, not AIWS production runtime readiness.

Cowork test prompt:

```text
Use the aiws-cowork-http-mcp-smoke-cowork-array smoke-check skill. Check whether Cowork registered the remote Claude docs HTTP MCP server named aiws-cowork-http-smoke-cowork-array-docs from this uploaded plugin. This plugin uses the Cowork top-level array HTTP MCP shape. Look for Claude docs MCP tools, especially docs search/read tools. Do not look for aiws.smoke.ping. Report which Claude docs tools are visible and call one harmless docs search/read tool if available.
```

Acceptance condition: the uploaded plugin installs, the `smoke-check` skill is visible, Cowork exposes Claude docs MCP search/read tools from `aiws-cowork-http-smoke-cowork-array-docs`, and a harmless docs search/read call succeeds.

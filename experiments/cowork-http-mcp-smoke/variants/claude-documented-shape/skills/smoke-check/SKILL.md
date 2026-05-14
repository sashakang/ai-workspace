---
name: smoke-check
description: Test-only skill for checking whether Cowork registered this variant's remote Claude docs HTTP MCP server.
---

This skill tests remote HTTP MCP registration only. It does not test AIWS production runtime readiness.

Check whether Cowork registered the remote Claude docs HTTP MCP server named `aiws-cowork-http-smoke-claude-docs` from the `aiws-cowork-http-mcp-smoke-claude-shape` uploaded plugin. Look for Claude docs MCP tools, especially docs search/read tools. Do not look for or call `aiws.smoke.ping`; this package does not include that stdio smoke server.

If Claude docs search/read tools are visible, call one harmless docs search/read tool and report the result. If no Claude docs tools are visible, report that the skill loaded but the remote HTTP MCP server was not exposed.

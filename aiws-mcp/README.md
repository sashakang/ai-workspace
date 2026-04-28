# aiws-mcp

`aiws-mcp` is the local MCP control plane for AIWS skills.

The MVP is local-only. It discovers personal and bundled skills, validates Agent Skills-compatible `SKILL.md` bundles, materializes verified copies under `~/.aiws`, and generates host adapter outputs for Claude Code, Cowork, and Codex.

# AIWS Cowork Phase 2B Runtime Plan

Updated: 2026-05-14

## Status

Phase 2A is validated as a technical pilot. Cowork can install the AIWS marketplace plugins, expose the AIWS draft-management tools from `core-aiws`, create and edit a draft, validate it, stage a proposal, submit it for review with authenticated host `gh`, create a GitHub PR, and complete maintainer review. That proves the lifecycle semantics.

Phase 2B is the end-user runtime gap. The current `core-aiws` package still starts the AIWS MCP bridge through:

```text
core-aiws/.mcp.json -> sh -> core-aiws/bin/aiws-mcp-launcher -> uvx -> aiws-mcp serve
```

That is acceptable for maintainers and technical testers, but not for normal Cowork users. A normal Cowork user must not need Python, `uv`, `uvx`, GitHub CLI, terminal commands, or manual MCP setup.

## Evidence

Local repo evidence:

- `core-aiws/.mcp.json` starts the `aiws` MCP server with `sh` and `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-launcher`.
- `core-aiws/bin/aiws-mcp-launcher` exits if `CLAUDE_PLUGIN_ROOT` is missing, then requires `uvx`, then runs `uvx --from "${CLAUDE_PLUGIN_ROOT}/servers/aiws-mcp" aiws-mcp serve`.
- `scripts/build_cowork_import.py` currently reports `missing_uvx` when `uvx` is unavailable.
- `tests/test_cowork_packaging.py` currently asserts that the packaged launcher invokes the bundled server source with `uvx`.
- `aiws-mcp/pyproject.toml` defines a Python package requiring Python `>=3.11` and dependency `mcp>=1.0.0`.
- `aiws-mcp/aiws_mcp/runtime.py` selects `GhCliProposalSubmitter` when `gh` is present and `GithubHandoffProposalSubmitter` otherwise.

External evidence:

- Claude plugin MCP servers can be bundled in a plugin and started automatically from `.mcp.json` or inline `plugin.json`; plugin MCP servers use `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` for bundled files and persistent state. Source: <https://code.claude.com/docs/en/mcp>
- Local stdio MCP servers are local commands started by the host. Source: <https://code.claude.com/docs/en/mcp>
- `uvx` is an alias for `uv tool run`, which runs Python-package tools in isolated environments. Source: <https://docs.astral.sh/uv/concepts/tools/>
- PyInstaller can bundle a Python program and dependencies into a one-folder or one-file executable, but builds are platform-specific. Source: <https://pyinstaller.org/en/stable/operating-mode.html>

## Product Goal

Install through Cowork, operate through Cowork.

The user should install `core-aiws` and a skill plugin from the Cowork marketplace, then use draft/edit/validate/stage/submit behavior without knowing that a local MCP bridge exists. If something cannot be completed from Cowork yet, the product must return a clear non-terminal status, not ask the user to install developer tooling.

## Recommended Architecture

Use a bundled local runtime bridge for Phase 2B.

The draft-management workflow is local by design: it reads installed plugin packages, writes editable drafts under `~/.aiws/plugins/`, writes proposal state under `~/.aiws/state/skill-proposals/`, validates local files, and builds local Cowork package artifacts. A remote connector alone cannot replace that without changing the trust and storage model of the product.

The target package should include a self-contained `aiws-mcp` executable built from the existing Python bridge. The launcher should prefer that bundled executable and keep the `uvx` path only as an explicit technical-pilot fallback.

Recommended launcher order:

1. If `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp` exists and is executable, run it with `serve`.
2. If explicit technical-pilot fallback is enabled and `uvx` exists, run the current `uvx --from ... aiws-mcp serve` path.
3. Otherwise exit with a clear dependency-free-runtime error that tells the tester the installed package is not Phase 2B-ready.

GitHub submission should move separately from host `gh` toward a Cowork-compatible GitHub adapter, GitHub App, or bot-backed API path. Local `gh` is acceptable for Phase 2A and maintainer testing, but it should not be a normal-user dependency.

## Implementation Slices

### Slice 2B.1: Bundled Executable Smoke Test

Build the smallest possible plugin-bundled executable MCP server and prove Cowork can launch it from `.mcp.json`.

Acceptance:

- The executable lives inside the installed plugin package.
- Cowork starts it from `.mcp.json` without `python`, `uv`, `uvx`, or `gh` on the AIWS runtime path.
- Cowork exposes one harmless smoke-test MCP tool.
- The launcher receives or can infer `CLAUDE_PLUGIN_ROOT`.
- Executable permissions survive marketplace install or Cowork ZIP upload.
- No `~/.claude` memory, managed marketplace plugin files, or Cowork runtime files are edited manually.

This slice is a proof step. It should not touch the production skill manager until Cowork proves it can run a bundled executable.

### Slice 2B.2: Package `aiws-mcp` As A Self-Contained Runtime

Package the existing `aiws-mcp serve` bridge into a platform-specific executable, starting with macOS because the current testing path is on macOS.

Acceptance:

- The executable starts the same MCP server surface as the current `uvx` bridge.
- Startup does not require user-installed Python, `uv`, or `uvx`.
- The package builder includes the executable in `core-aiws`.
- The build output records platform, architecture, build command, binary size, and cold-start result.
- The existing source-bundled `servers/aiws-mcp` path remains available for maintainers until the binary path is proven stable.

### Slice 2B.3: Update Launcher And Packaging Tests

Update the launcher, import builder, and tests so dependency-free runtime is the default expectation.

Acceptance:

- `core-aiws/bin/aiws-mcp-launcher` prefers the bundled executable.
- The `uvx` path is only a named technical-pilot fallback, not the default normal-user path.
- Packaging tests assert that the package includes the bundled executable when Phase 2B mode is selected.
- Packaging tests assert that missing bundled executable plus no explicit fallback returns a clear error.
- Existing Phase 2A behavior can still be tested intentionally.

Likely files:

- `core-aiws/bin/aiws-mcp-launcher`
- `core-aiws/.mcp.json`
- `scripts/build_cowork_import.py`
- `tests/test_cowork_packaging.py`
- `docs/cowork-skills-management-phase2-test-plan.md`

### Slice 2B.4: Cowork Runtime Validation On A Clean User Machine

Run the A-H lifecycle again on a machine where AIWS does not rely on user-installed Python, `uv`, `uvx`, or `gh`.

Acceptance:

- Marketplace install is still the primary install path.
- `core-aiws` tools appear in Cowork after install.
- Draft create/open, edit, validate, stage proposal, and submit or handoff all work through Cowork.
- Submit with no `gh` returns a truthful non-terminal handoff or uses the new non-CLI adapter if available.
- The report explicitly records that Python, `uv`, `uvx`, and `gh` were not used by AIWS.

### Slice 2B.5: Non-CLI GitHub Submitter

Replace normal-user reliance on host `gh` with a GitHub App, bot, or Cowork-compatible GitHub connection.

Acceptance:

- Submission still uses deterministic branch identity `aiws/skill-proposals/<proposal_id>`.
- Required reviewer roles include `AI engineer`.
- The adapter creates or updates one review item for retry safety.
- Users do not paste tokens into chat.
- If the adapter is unavailable, `submit_handoff_required` remains non-terminal and does not mark the proposal submitted.

This can follow the runtime package work. Local `gh` is acceptable until the dependency-free bridge is proven because the bigger immediate blocker is `uvx`.

## Gate 1 Questions

Reviewers should approve this plan only if these statements are true:

- The plan does not pretend Phase 2A is end-user ready.
- The first proof is Cowork launching a bundled executable, not a speculative full packaging rewrite.
- The plan preserves local draft and proposal state under `~/.aiws/`.
- The plan keeps managed marketplace and organization plugin files read-only.
- The plan includes AI engineer reviewer routing for submit-for-review.
- The plan keeps `uvx` and `gh` as technical-pilot paths until replaced, not as normal-user requirements.

## Phase 2B Exit Criteria

Phase 2B is complete only when a normal Cowork user can install and use the skill-management workflow without Python, `uv`, `uvx`, GitHub CLI, terminal commands, manual plugin-file edits, or manual MCP setup.

If Cowork cannot launch a bundled executable or provide a guaranteed runtime, Phase 2B is blocked. In that case, Phase 2A remains the honest technical-pilot path and the project should not call the Cowork skills-management workflow end-user ready.

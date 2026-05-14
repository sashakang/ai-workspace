# AIWS Cowork Phase 2B Runtime Plan

Updated: 2026-05-14

## Status

Phase 2A is validated as a technical pilot. Cowork can install the AIWS marketplace plugins, expose the AIWS draft-management tools from `core-aiws`, create and edit a draft, validate it, stage a proposal, submit it for review with authenticated host `gh`, create a GitHub PR, and complete maintainer review. That proves the lifecycle semantics.

Phase 2B is the end-user runtime gap. The current `core-aiws` package still starts the AIWS MCP bridge through:

```text
core-aiws/.mcp.json -> sh -> core-aiws/bin/aiws-mcp-launcher -> uvx -> aiws-mcp serve
```

That is acceptable for maintainers and technical testers, but not for normal Cowork users. A normal Cowork user must not need Python, `uv`, `uvx`, GitHub CLI, terminal commands, or manual MCP setup.

The Gate-1 architecture direction has changed: the primary Phase 2B proof path is now a hosted FastMCP or official MCP Python SDK AIWS control-plane server registered through Cowork's supported managed/custom connector path. Cowork marketplace/upload plugins remain the skills distribution and user-facing UX surface. The AIWS MCP/control-plane runtime is a separate deployable surface.

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

Closed Cowork runtime evidence:

- Uploaded-plugin `.mcp.json` stdio experiments loaded the visible smoke skill, but Cowork did not expose the bundled `aiws.smoke.ping` MCP tool.
- Uploaded-plugin HTTP MCP experiments are treated as evidence about uploaded-plugin runtime registration, not the forward path for AIWS Phase 2B.
- Executable packaging and uploaded-plugin runtime experiments are paused unless Cowork documents or proves a supported local runtime path.

## Product Goal

Install through Cowork, operate through Cowork.

The user should install `core-aiws` and a skill plugin from the Cowork marketplace, then use draft/edit/validate/stage/submit behavior without knowing that an AIWS control-plane runtime exists. If something cannot be completed from Cowork yet, the product must return a clear non-terminal status, not ask the user to install developer tooling.

## Recommended Architecture

Prove the Cowork supported connector path before investing further in bundled local runtime work.

The next proof is a hosted FastMCP or official MCP Python SDK AIWS control-plane service registered through Cowork's supported managed/custom connector path. FastMCP/Python is preferred now because the existing AIWS control-plane code is already Python. The TypeScript SDK is a possible later choice only if AIWS builds a new hosted service from scratch.

This proof should start with harmless tools only:

```text
aiws.health.ping
aiws.runtime.info
```

The first proof must not expose memory tools, mutate managed marketplace or organization plugin files, or write into Cowork's installed plugin packages.

The draft-management workflow still depends on local state: editable drafts under `~/.aiws/plugins/`, proposal state under `~/.aiws/state/skill-proposals/`, validation of local files, and later package/artifact generation. The hosted proof therefore validates Cowork's supported connector path first. It does not yet prove the full production local-state model.

Cowork marketplace/upload plugins remain the skills and user-facing UX surface. They should carry skills, prompts, and Cowork-facing guidance. The AIWS MCP/control-plane runtime is a separate deployable surface registered through the supported connector path.

GitHub submission should move separately from host `gh` toward a GitHub App, bot, API, or Cowork-compatible adapter path. Local `gh` is acceptable for Phase 2A and maintainer testing, but it must not be a normal-user dependency.

## Implementation Slices

### Slice 2B.1: Hosted FastMCP Connector Proof

Build the smallest hosted AIWS control-plane proof with FastMCP or the official MCP Python SDK, then register it through Cowork's supported managed/custom connector path.

Local proof artifact:

- Module: `aiws-mcp/aiws_mcp/phase2b_proof.py`
- Local run command, after installing the package dependencies in the active environment: `python -m aiws_mcp.phase2b_proof --transport streamable-http`
- Expected local MCP endpoint for the SDK default streamable HTTP server: `http://localhost:8000/mcp`
- The module intentionally exposes only `aiws.health.ping` and `aiws.runtime.info`.
- The pure payload functions can be tested without a live MCP client or installed MCP SDK.

Cowork connector test:

1. Deploy or run the proof server through a hosted/remote HTTP path that Cowork can register.
2. Register that URL through Cowork's supported managed/custom MCP connector path.
3. Confirm Cowork exposes exactly `aiws.health.ping` and `aiws.runtime.info`.
4. Call both tools and verify their payloads report `memory_tools_exposed: false` and `managed_plugin_mutation: false`.
5. Confirm no `aiws.skills.*`, memory, lifecycle, draft, proposal, submit, GitHub, or host-local mutation tools appear.

Acceptance:

- Cowork registers the hosted AIWS proof through a supported managed/custom connector path.
- Cowork exposes `aiws.health.ping` and `aiws.runtime.info`.
- A harmless ping/info call succeeds from Cowork.
- The proof does not expose memory tools.
- The proof does not mutate managed marketplace, organization, or uploaded plugin files.
- The proof does not require user-installed Python, `uv`, `uvx`, `gh`, Git, shell commands, uploaded-plugin runtime setup, or manual MCP configuration.
- The implementation is clearly labeled as the next proof path, not a completed production runtime.

This slice should not implement the full draft/edit/validate/stage/submit surface until the connector path is proven.

### Slice 2B.2: Connector-Backed Draft Lifecycle Design

Design how the hosted control plane will safely reach the required AIWS local state or equivalent managed state for draft/edit/validate/stage/submit.

Acceptance:

- The design preserves editable drafts under `~/.aiws/plugins/` or names an equivalent Cowork-supported state path.
- Proposal records remain distinct from PR submission and retain provenance under `~/.aiws/state/skill-proposals/` or an equivalent managed state path.
- Managed marketplace and organization plugin files remain read-only.
- Duplicate visible skill identities fail closed.
- The design explains how a normal Cowork user gets access without Python, `uvx`, `gh`, shell commands, or manual MCP setup.

### Slice 2B.3: Paused Uploaded-Plugin Stdio Evidence

Result: **BLOCKED** for bundled stdio executable MCP server registration in the Cowork uploaded-plugin path.

Observed Cowork evidence:

- The v0.1.1 plugin ZIP uploaded successfully.
- The `aiws-cowork-mcp-smoke:smoke-check` skill is visible in Cowork.
- Cowork can read `skills/smoke-check/SKILL.md` at the expected installed-plugin path.
- ToolSearch for `aiws smoke ping` returns no matching tool.
- No MCP server launch error surfaced to the user.
- `aiws.smoke.ping` is absent.

This removes the earlier `MCP-only/no skills` variable: adding a visible skill made the plugin load through Cowork's normal skill surface, but the bundled MCP tool still did not appear. The result should not be read as proof that every executable runtime approach is impossible. It only shows that this specific uploaded-plugin shape, where `.mcp.json` starts a bundled stdio executable command at `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-smoke`, was not registered by the Cowork upload runtime.

Keep `experiments/cowork-mcp-smoke/` as a reusable diagnostic artifact only. Do not continue executable packaging from this path unless Cowork documents or proves a supported local runtime path.

### Slice 2B.4: Closed Uploaded-Plugin HTTP Evidence

The static upload-only HTTP plugin variants are closed evidence for uploaded-plugin runtime registration. They are not the Phase 2B path forward.

Local diagnostic packages:

- Source: `experiments/cowork-http-mcp-smoke/`
- Builder: `python -m scripts.build_cowork_http_mcp_smoke`
- Output: `dist/cowork-http-smoke/`
- Variant A package: `aiws-cowork-http-mcp-smoke-claude-shape-0.1.0.zip`
- Variant A MCP server: `aiws-cowork-http-smoke-claude-docs`
- Variant B package: `aiws-cowork-http-mcp-smoke-cowork-array-0.1.0.zip`
- Variant B MCP server: `aiws-cowork-http-smoke-cowork-array-docs`

This evidence does not claim AIWS production runtime readiness. Future HTTP work should use Cowork's supported managed/custom connector path directly, not uploaded-plugin `.mcp.json` experiments.

### Slice 2B.5: Paused Executable Packaging

Package the existing `aiws-mcp serve` bridge into a platform-specific executable, starting with macOS because the current testing path is on macOS.

This is paused. Resume it only if Cowork documents or demonstrates a supported local runtime path that can actually register the packaged server.

Acceptance:

- The executable starts the same MCP server surface as the current `uvx` bridge.
- Startup does not require user-installed Python, `uv`, or `uvx`.
- The package builder includes the executable in `core-aiws`.
- The build output records platform, architecture, build command, binary size, and cold-start result.
- The existing source-bundled `servers/aiws-mcp` path remains available for maintainers until the binary path is proven stable.

### Slice 2B.6: Update Launcher And Packaging Tests

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

This slice is also paused until a supported local runtime path exists. The FastMCP connector proof should not require changes to the uploaded-plugin launcher.

### Slice 2B.7: Cowork Runtime Validation For Normal Users

Run the lifecycle again from a normal Cowork user path where AIWS does not rely on user-installed Python, `uv`, `uvx`, or `gh`.

Acceptance:

- Marketplace install is still the primary install path.
- The AIWS control-plane tools appear through the supported Cowork connector path.
- Draft create/open, edit, validate, stage proposal, and submit or handoff all work through Cowork.
- Submit with no `gh` returns a truthful non-terminal handoff or uses the new non-CLI adapter if available.
- The report explicitly records that Python, `uv`, `uvx`, and `gh` were not used by AIWS.

### Slice 2B.8: Non-CLI GitHub Submitter

Replace normal-user reliance on host `gh` with a GitHub App, bot, API, or Cowork-compatible GitHub connection.

Acceptance:

- Submission still uses deterministic branch identity `aiws/skill-proposals/<proposal_id>`.
- Required reviewer roles include `AI engineer`.
- The adapter creates or updates one review item for retry safety.
- Users do not paste tokens into chat.
- If the adapter is unavailable, `submit_handoff_required` remains non-terminal and does not mark the proposal submitted.

Keep this separate from the FastMCP proof. Local `gh` remains Phase 2A technical-pilot evidence only and is not a normal-user submission path.

## Gate 1 Questions

Reviewers should approve this plan only if these statements are true:

- The plan does not pretend Phase 2A is end-user ready.
- The next proof is a hosted FastMCP or official MCP Python SDK AIWS control-plane server through Cowork's supported managed/custom connector path.
- Cowork marketplace/upload plugins remain the skills and user-facing UX surface.
- The AIWS MCP/control-plane runtime is a separate deployable surface.
- Uploaded-plugin `.mcp.json` stdio/HTTP experiments are closed evidence, not the path forward.
- Executable packaging and uploaded-plugin runtime experiments are paused unless Cowork documents or proves a supported local runtime path.
- The plan preserves local draft and proposal state under `~/.aiws/`.
- The plan keeps managed marketplace and organization plugin files read-only.
- The plan includes AI engineer reviewer routing for submit-for-review.
- The plan keeps `uvx` and `gh` as technical-pilot paths until replaced, not as normal-user requirements.

## Phase 2B Exit Criteria

Phase 2B is complete only when a normal Cowork user can install skills and access AIWS draft/edit/validate/stage/submit through Cowork without Python, `uv`, `uvx`, GitHub CLI, terminal commands, manual plugin-file edits, or manual MCP setup.

If Cowork cannot support a managed/custom connector path or document a supported local runtime path, Phase 2B is blocked. In that case, Phase 2A remains the honest technical-pilot path and the project should not call the Cowork skills-management workflow end-user ready.

# AIWS Cowork Phase 2B Runtime Plan

Updated: 2026-05-15

## Status

Phase 2A is validated as a technical pilot. Cowork can install the AIWS marketplace plugins, expose the AIWS draft-management tools from `core-aiws`, create and edit a draft, validate it, stage a proposal, submit it for review with authenticated host `gh`, create a GitHub PR, and complete maintainer review. That proves the lifecycle semantics.

The regular Cowork user draft/edit/validate/stage/submit path is also proven end to end for `aiws-productivity:meeting-followup`. The 2026-05-14 test opened draft `aiws-productivity--meeting-followup--de0e75a572` from installed plugin version `0.2.1`, edited only the draft copy under `~/.aiws/plugins/...`, staged proposal `skillprop_ed458362021141179dbdb85a9df73794`, and submitted PR #2 to `sashakang/aiws-skill-tests`. The PR is open and non-draft. Installed plugin files, marketplace files, `~/.claude`, and Cowork runtime files were untouched. That historical test predated the corrected Gate 1 boundary; current normal Cowork submission leaves review and merge to repository maintainers and policy instead of writing product-level reviewer-role metadata.

The 2026-05-15 regular-user loop is now complete and recorded in the testing manual. Cowork opened and edited draft `aiws-productivity--meeting-followup--de0e75a572`, validated digest `c94dc08ad7a6633e2755611fc8f9866a158793c63617325cb9db63618e964265`, prepared a `pending_upload` package, verified the manually uploaded modified package in a new Cowork chat, cleared the pending-upload marker, staged proposal `skillprop_bb386ac3528247c7bf7ddb88793497b2`, and submitted PR #3 to `sashakang/aiws-skill-tests`. The repository allowlist guard also worked: a proposal staged with the literal placeholder `<test review repository>` was blocked before submit. See [AIWS Testing Manual](./aiws-testing-manual.md), [Cowork Modified Draft Upload Report](./cowork-modified-draft-upload-report-2026-05-15.md), [Cowork Pending Upload Deactivation Report](./cowork-pending-upload-deactivation-report-2026-05-15.md), and [Cowork Proposal Submit Report](./cowork-proposal-submit-report-2026-05-15.md).

The product gap is now concrete. Manual package upload works as a fallback/technical-pilot bridge, but it is not acceptable as the final regular-user activation experience because it can leave duplicate visible `meeting-followup` instances in Cowork. The next implementation slice must make activation/update user-friendly: no manual ZIP handling for regular users, no duplicate visible plugin instances, no direct mutation of installed marketplace files, and a truthful non-terminal fallback if Cowork still cannot activate a prepared package programmatically.

The immediate next slice is narrower than full activation UX. Runtime testing showed that Cowork can run the uploaded modified skill while AIWS cannot reliably tell whether there is one installed copy or several. Before AIWS can claim a clean activation/update model, it needs a small read-only check that reports zero, one, or multiple installed copies of a logical skill. Gate 1 is approved in [Cowork Registry Alignment Gate 1](./cowork-registry-alignment-gate1-2026-05-15.md).

The 2026-05-14 canonical Cowork user test also passed for the normal install/use/update path. Cowork installed marketplace `sashakang/ai-workspace`, installed `core-aiws@ai-workspace` and `aiws-productivity@ai-workspace`, exposed `aiws-productivity:meeting-followup`, invoked the skill successfully, updated the marketplace/plugins through the Cowork UI, and kept `meeting-followup` visible after update. See [Cowork Canonical User Test Report](./cowork-canonical-user-test-report-2026-05-14.md).

Phase 2B is the end-user runtime gap. The current `core-aiws` package still starts the AIWS MCP bridge through:

```text
core-aiws/.mcp.json -> sh -> core-aiws/bin/aiws-mcp-launcher -> uvx -> aiws-mcp serve
```

That is acceptable for maintainers and technical testers, but not for normal Cowork users. A normal Cowork user must not need Python, `uv`, `uvx`, GitHub CLI, terminal commands, or manual MCP setup.

The Gate-1 architecture direction has changed again. For private and non-public skills, the primary near-term path is a maintainer/operator "Claude Code skill workshop", not MCP running inside Claude Code and not a hosted remote MCP service that can see private local state. The workshop should use Claude Code's normal skills, workflows, and commands to update skill source, validate contracts, build Cowork packages, push to GitHub as the maintainer or bot, and prepare or upload marketplace artifacts on demand.

Cowork remains the user-facing surface for installing and using skills. A richer Cowork edit UX is still the product target, but it is deferred until the runtime and security model are clean.

The hosted FastMCP or official MCP Python SDK connector proof remains useful, but it is parked as a secondary/future proof. It must expose only harmless public proof tools until auth, permissions, and tenancy are designed. Hosted remote MCP must not expose private skills, memory, drafts, proposal records, or source content.

## Evidence

Local repo evidence:

- `core-aiws/.mcp.json` starts the `aiws` MCP server with `sh` and `${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-launcher`.
- `core-aiws/bin/aiws-mcp-launcher` exits if `CLAUDE_PLUGIN_ROOT` is missing, then requires `uvx`, then runs `uvx --from "${CLAUDE_PLUGIN_ROOT}/servers/aiws-mcp" aiws-mcp serve`.
- `scripts/build_cowork_import.py` currently reports `missing_uvx` when `uvx` is unavailable.
- `tests/test_cowork_packaging.py` currently asserts that the packaged launcher invokes the bundled server source with `uvx`.
- `aiws-mcp/pyproject.toml` defines a Python package requiring Python `>=3.11` and dependency `mcp>=1.8.0`.
- `aiws-mcp/aiws_mcp/runtime.py` selects `GhCliProposalSubmitter` when `gh` is present and `GithubHandoffProposalSubmitter` otherwise.

External evidence:

- Claude plugin MCP servers can be bundled in a plugin and started automatically from `.mcp.json` or inline `plugin.json`; plugin MCP servers use `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` for bundled files and persistent state. Source: <https://code.claude.com/docs/en/mcp>
- Local stdio MCP servers are local commands started by the host. Source: <https://code.claude.com/docs/en/mcp>
- `uvx` is an alias for `uv tool run`, which runs Python-package tools in isolated environments. Source: <https://docs.astral.sh/uv/concepts/tools/>
- PyInstaller can bundle a Python program and dependencies into a one-folder or one-file executable, but builds are platform-specific. Source: <https://pyinstaller.org/en/stable/operating-mode.html>

Closed Cowork runtime evidence:

- The canonical Cowork user test returned `capability_exposure: plugin-package` and `direct_host_install_supported: false` from `aiws.host.surfaces` when called with `host_kind: cowork`. Cowork installed plugin folders were read-only; package upload and AIWS adapter/cache roots were writable.
- Uploaded-plugin `.mcp.json` stdio experiments loaded the visible smoke skill, but Cowork did not expose the bundled `aiws.smoke.ping` MCP tool.
- Uploaded-plugin HTTP MCP experiments are treated as evidence about uploaded-plugin runtime registration, not the forward path for AIWS Phase 2B.
- Executable packaging and uploaded-plugin runtime experiments are paused unless Cowork documents or proves a supported local runtime path.

## Product Goal

Install through Cowork, operate through Cowork.

The user should install `core-aiws` and a skill plugin from the Cowork marketplace, then use draft/edit/validate/stage/submit behavior without knowing that an AIWS control-plane runtime exists. Cowork owns install, update, and activation through marketplace or package upload. AIWS owns validation, staging, proposal records, adapter/cache materialization, and package preparation. If something cannot be completed from Cowork yet, the product must return a clear non-terminal status, not ask the user to install developer tooling.

## Recommended Architecture

Use Claude Code as the near-term maintainer workshop for private and non-public skill maintenance. Do not run AIWS MCP inside Claude Code for this workflow. Keep Cowork as the normal install/use surface.

The maintainer workshop should support these operations:

- update skill source in the repository or local workspace
- validate `SKILL.md`, plugin manifests, contracts, and package boundaries
- run focused tests such as `python -m unittest tests.test_aiws_skill_manager tests.test_cowork_packaging`
- build Cowork packages or marketplace artifacts on demand
- push through the maintainer or bot identity when explicitly requested
- prepare upload instructions or upload artifacts through the supported Cowork path when the operator asks

The hosted connector proof should continue only as a harmless secondary check of Cowork's supported managed/custom connector path. FastMCP/Python is still the preferred proof technology because the existing AIWS control-plane code is already Python. The TypeScript SDK is a possible later choice only if AIWS builds a new hosted service from scratch.

This proof should start with harmless tools only:

```text
aiws.health.ping
aiws.runtime.info
```

The proof must not expose memory tools, private skills, drafts, proposal records, source content, mutate managed marketplace or organization plugin files, or write into Cowork's installed plugin packages.

The draft-management workflow still depends on local state: editable drafts under `~/.aiws/plugins/`, proposal state under `~/.aiws/state/skill-proposals/`, validation of local files, and later package/artifact generation. The hosted proof therefore cannot be the private-skills path until there is a clear auth, permissions, tenancy, and local-state design. For now, the Claude Code workshop owns maintainer/private skill maintenance.

Cowork marketplace/upload plugins remain the skills and user-facing UX surface. They should carry skills, prompts, and Cowork-facing guidance. The AIWS MCP/control-plane runtime is a separate deployable surface registered through the supported connector path.

The current package boundary is explicit: AIWS must not directly mutate `~/.cowork/plugins` or Cowork RPM/runtime state. When AIWS prepares an updated skill or adapter output, the Cowork-facing action is package upload, marketplace update, or another Cowork-supported install/update surface. The normal user path must not require repo cloning, terminal commands, manual runtime edits, direct installed-plugin edits, or `~/.claude` edits.

GitHub submission should move separately from host `gh` toward a GitHub App, bot, API, or Cowork-compatible adapter path. Local `gh` is acceptable for Phase 2A and maintainer testing, but it must not be a normal-user dependency.

Review ownership should stay simple. AIWS owns deterministic branch/PR identity and clear reporting when repository-policy enforcement is missing. GitHub owns reviewer assignment and approval enforcement through repo policy such as CODEOWNERS, branch protection, repository rules, or maintainer-controlled automation. AIWS should detect and report `CODEOWNERS: not_detected` or equivalent missing enforcement as a caveat, not write product-level reviewer-role metadata or ask normal Cowork users to choose GitHub reviewers.

## Implementation Slices

### Slice 2B.1: Claude Code Skill Workshop

Build the near-term maintainer/operator workflow for private and non-public skills. This workflow runs in Claude Code through skills, workflows, commands, and local repo tools. It does not run AIWS MCP inside Claude Code, and it does not expose private skill content through hosted MCP.

Expected workshop operations:

- update skill source in the repo or local AIWS workspace
- validate skill compatibility, plugin manifests, contracts, and package boundaries
- run focused unit tests and release checks
- build Cowork packages or marketplace artifacts on demand
- push branches or update marketplace source through the maintainer or bot identity when explicitly requested
- prepare upload instructions or upload artifacts through a supported Cowork path when the operator asks

Acceptance:

- The workflow is clearly labeled maintainer/private-skill only.
- It does not replace Cowork as the user-facing install/use surface.
- It does not require MCP running inside Claude Code.
- It validates before package build, push, or upload.
- It keeps managed marketplace and organization plugin files read-only unless the operator is intentionally updating the source repository as a maintainer.
- It produces clear changed-file, package, test, and publication evidence.

This is the primary near-term path for maintainer-owned private and non-public skill work.

### Slice 2B.2: Parked Hosted FastMCP Connector Proof

Keep the smallest hosted AIWS control-plane proof with FastMCP or the official MCP Python SDK, then register it through Cowork's supported managed/custom connector path when connector validation is useful. This is secondary/future proof work, not the near-term private-skills workflow.

Local proof artifact:

- Module: `aiws-mcp/aiws_mcp/phase2b_proof.py`
- Local maintainer smoke command, after installing the package dependencies in the active environment: `python -m aiws_mcp.phase2b_proof --transport streamable-http`
- Expected local MCP endpoint: `http://localhost:8000/mcp`
- Hosted maintainer command example for a platform that injects `PORT`: `python -m aiws_mcp.phase2b_proof --host 0.0.0.0 --port "$PORT" --mcp-path /mcp`
- Remote connector proof deployments must bind to a public interface on the hosting platform, usually `0.0.0.0` behind the platform router. `127.0.0.1` and `localhost` are only for local maintainer smoke testing because Cowork remote connectors are called from Anthropic cloud.
- The module intentionally exposes only `aiws.health.ping` and `aiws.runtime.info`.
- The pure payload functions can be tested without a live MCP client or installed MCP SDK.
- This is a developer/maintainer proof server, not something normal Cowork users run.
- This proof must not expose private skills, memory, drafts, proposal records, source content, or lifecycle tools until auth, permissions, and tenancy are designed.

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
- The implementation is clearly labeled as a parked secondary/future proof, not the private-skills path and not a completed production runtime.

This slice should not implement the full draft/edit/validate/stage/submit surface until the connector path is proven.

### Slice 2B.3: Connector-Backed Draft Lifecycle Design

Design how the hosted control plane will safely reach the required AIWS local state or equivalent managed state for draft/edit/validate/stage/submit.

Acceptance:

- The design preserves editable drafts under `~/.aiws/plugins/` or names an equivalent Cowork-supported state path.
- Proposal records remain distinct from PR submission and retain provenance under `~/.aiws/state/skill-proposals/` or an equivalent managed state path.
- Managed marketplace and organization plugin files remain read-only.
- Duplicate visible skill identities fail closed.
- The design explains how a normal Cowork user gets access without Python, `uvx`, `gh`, shell commands, or manual MCP setup.
- The design explains how hosted components avoid private skills, memory, drafts, proposal records, and source content until auth, permissions, and tenancy are defined.

### Slice 2B.4: Paused Uploaded-Plugin Stdio Evidence

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

### Slice 2B.5: Closed Uploaded-Plugin HTTP Evidence

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

### Slice 2B.6: Paused Executable Packaging

Package the existing `aiws-mcp serve` bridge into a platform-specific executable, starting with macOS because the current testing path is on macOS.

This is paused. Resume it only if Cowork documents or demonstrates a supported local runtime path that can actually register the packaged server.

Acceptance:

- The executable starts the same MCP server surface as the current `uvx` bridge.
- Startup does not require user-installed Python, `uv`, or `uvx`.
- The package builder includes the executable in `core-aiws`.
- The build output records platform, architecture, build command, binary size, and cold-start result.
- The existing source-bundled `servers/aiws-mcp` path remains available for maintainers until the binary path is proven stable.

### Slice 2B.7: Update Launcher And Packaging Tests

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

### Slice 2B.8: Cowork Runtime Validation For Normal Users

Run the lifecycle again from a normal Cowork user path where AIWS does not rely on user-installed Python, `uv`, `uvx`, or `gh`.

Status: completed for the current technical-pilot path on 2026-05-15. Marketplace install/use, draft open/edit/validate, `pending_upload` package preparation, manual upload verification, pending-upload cleanup, staging, repository guard, and submit-for-review all passed and are recorded in the testing manual. This does not make activation end-user ready, because modified-skill activation still required manual package upload and produced duplicate visible skill instances.

Acceptance:

- Marketplace install is still the primary install path.
- The AIWS control-plane tools appear through the supported Cowork connector path.
- Draft create/open, edit, validate, stage proposal, and submit or handoff all work through Cowork.
- Submit with no `gh` returns a truthful non-terminal handoff or uses the new non-CLI adapter if available.
- Managed plugin files and Cowork installed plugin folders remain read-only to AIWS.
- Skill updates prepared by AIWS flow through Cowork-owned marketplace/package upload or another supported Cowork install/update surface.
- The report explicitly records that Python, `uv`, `uvx`, and `gh` were not used by AIWS.

### Slice 2B.8A: Cowork Package Intake Probe

Before implementing any automated package handoff, prove whether Cowork consumes packages placed in the writable `package_uploads` surface reported by `aiws.host.surfaces`. Current evidence proves only that `~/.cowork/packages` is writable; it does not prove Cowork watches, imports, installs, or activates packages placed there.

Use the disposable probe utility:

```bash
python -m scripts.cowork_package_intake_probe \
  --host-id <existing-cowork-host-id>
```

The utility reads an existing Cowork host record under `~/.aiws/hosts/<host-id>/host.json`, builds a unique throwaway plugin named `aiws-cowork-package-intake-probe-<yyyymmddhhmmss>`, and copies only that ZIP to the recorded `package_uploads` directory. It must not create or update host records, use real AIWS skill packages, overwrite existing files, follow symlinked upload paths, or write anywhere else under `~/.cowork`.

Probe success requires a new Cowork chat, without using `Settings -> Plugins -> Upload a file`, to see and call `intake-probe` from the unique probe plugin. Anything less is `cowork_install_confirmation_unavailable` or `no_automatic_intake_observed`, not proof that the normal-user manual upload problem is solved.

If the probe plugin appears in Cowork, remove or disable it through Cowork plugin settings when available. If cleanup is unavailable, record the unique probe plugin id, copied package path, and Cowork cleanup limitation as evidence. Never reuse a probe identity.

### Slice 2B.8B: User-Friendly Cowork Activation And Update

Replace the current manual-upload activation bridge with a Cowork-safe activation/update path that a normal user can complete without handling ZIP files.

Gate 1: approved for staged implementation in [Cowork Activation And Update Gate 1](./cowork-activation-update-gate1-2026-05-15.md). The approved scope is activation handoff improvement, not fake activation. AIWS may prepare and hand off packages through safe Cowork-supported upload surfaces, but it must not claim `active` until Cowork confirms the modified package is visible and callable through a supported mechanism.

Current evidence:

- `activate_draft` can prepare a package and record `pending_upload`.
- Manual upload of that package through Cowork works and the modified skill runs.
- Cowork may show both the original marketplace package and uploaded modified package, so the current bridge can expose duplicate visible skill identities.
- `deactivate_draft` correctly clears only AIWS pending-upload state and does not uninstall the Cowork-uploaded package.

Expected output:

- A Cowork-facing activate/update action can apply or hand off the modified package through a Cowork-supported surface without asking the regular user to locate or upload a ZIP manually.
- The same logical skill identity remains visible to the user; duplicate visible `plugin_id + skill_id` variants are avoided, hidden, or treated as a fail-closed conflict with clear instructions.
- Installed marketplace and organization plugin files stay read-only to AIWS.
- `~/.claude`, Cowork RPM/runtime files, and unmanaged plugin folders remain untouched.
- If Cowork cannot support programmatic activation, the response remains non-terminal and honest, but the user-facing path should be simpler than "find this ZIP and upload it".

Acceptance:

- A modified draft can be activated or prepared for activation without manual ZIP handling in the normal-user happy path.
- Activation does not leave two active visible copies of `aiws-productivity:meeting-followup` unless the user explicitly chooses a separate uploaded copy or scope.
- Cleanup semantics are explicit: clearing AIWS pending state is separate from uninstalling a Cowork-uploaded plugin.
- Re-running activation is idempotent or returns the existing pending/active state without creating duplicate packages or duplicate visible skills.
- The action reports whether Cowork activation is `active`, `pending_upload`, `handoff_prepared`, `handoff_required`, or `host_capability_missing`.
- The test manual includes the new scenario and the old manual-upload scenario remains labeled fallback/technical-pilot only.

### Slice 2B.8C: Installed Skill Copy Check

Implement the approved read-only duplicate/source check from [Cowork Registry Alignment Gate 1](./cowork-registry-alignment-gate1-2026-05-15.md).

Acceptance:

- AIWS can report whether it sees zero, one, or multiple installed copies of `plugin_id + skill_id`.
- Duplicate `plugin_id + skill_id` instances return `duplicate_visible_identity` instead of silently choosing one.
- Explicit `source_plugin_root` pinning remains available for maintainer/diagnostic flows.
- The operation does not mutate Cowork RPM/runtime folders, installed marketplace or organization plugins, uploaded plugin files, hostloop caches, `~/.claude`, memory roots, proposal records, or GitHub state.
- The normal-user response explains duplicate installs in product language and does not ask the user to inspect RPM paths.

Evidence:

- Unit tests cover one installed copy, duplicate installed copies, missing skill, explicit source pinning, and no-write behavior.
- Runtime testing records whether `meeting-followup` is visible once or duplicated.

### Slice 2B.9: Non-CLI GitHub Submitter

Replace normal-user reliance on host `gh` with a GitHub App, bot, API, or Cowork-compatible GitHub connection.

Acceptance:

- Submission still uses deterministic branch identity `aiws/skill-proposals/<proposal_id>`.
- The adapter creates or updates one review item for retry safety.
- Normal Cowork submission does not invent reviewer roles.
- Users do not paste tokens into chat.
- If the adapter is unavailable, `submit_handoff_required` remains non-terminal and does not mark the proposal submitted.

Keep this separate from the FastMCP proof. Local `gh` remains Phase 2A technical-pilot evidence only and is not a normal-user submission path.

### Slice 2B.10: Repository Policy-Owned Review

Make repository-policy review visible without asking normal Cowork users to map GitHub reviewers or teams.

Recommended Gate 1 candidate plan:

- AIWS keeps deterministic branch and PR behavior with `aiws/skill-proposals/<proposal_id>`.
- GitHub repository policy enforces assignment and approval through CODEOWNERS, branch protection, repository rules, or maintainer-owned reviewer automation.
- AIWS detects and reports missing enforcement signals such as `CODEOWNERS: not_detected` and empty review requests.
- Missing enforcement remains a caveat until the target repository has policy in place.

Acceptance:

- A submitted proposal reports whether reviewer enforcement is present, absent, or unknown.
- Missing CODEOWNERS or reviewer policy does not block proposal creation, but it is visible in the Cowork-facing result and proposal state.
- The PR body states that review and merge are managed by repository maintainers and policy.
- Normal Cowork users do not select GitHub users or teams.
- The docs and UI do not claim review assignment is enforced unless GitHub policy actually enforces it.

## Gate 1 Questions

Reviewers should approve this plan only if these statements are true:

- The plan does not pretend Phase 2A is end-user ready.
- The canonical Cowork user path does not require repo clone, terminal use, manual RPM/runtime edits, direct installed-plugin edits, or `~/.claude` edits.
- Cowork owns install/update; AIWS prepares, stages, validates, materializes to AIWS-owned roots, and packages.
- The near-term private/non-public skills path is the Claude Code skill workshop, not MCP running inside Claude Code and not hosted remote MCP.
- The hosted FastMCP or official MCP Python SDK AIWS control-plane server through Cowork's supported managed/custom connector path is parked as secondary/future proof work.
- Cowork marketplace/upload plugins remain the skills and user-facing UX surface.
- The AIWS MCP/control-plane runtime is a separate deployable surface.
- Hosted remote MCP does not expose private skills, memory, drafts, proposal records, source content, or lifecycle tools until auth, permissions, and tenancy are designed.
- Uploaded-plugin `.mcp.json` stdio/HTTP experiments are closed evidence, not the path forward.
- Executable packaging and uploaded-plugin runtime experiments are paused unless Cowork documents or proves a supported local runtime path.
- The plan preserves local draft and proposal state under `~/.aiws/`.
- The plan keeps managed marketplace and organization plugin files read-only.
- The plan does not hardcode product-level reviewer roles for submit-for-review.
- The plan treats review assignment as enforceable only when GitHub repository policy or maintainer-owned automation exists.
- The plan reports missing CODEOWNERS/reviewer enforcement as a caveat instead of asking normal Cowork users to map reviewers.
- The plan keeps `uvx` and `gh` as technical-pilot paths until replaced, not as normal-user requirements.

## Phase 2B Exit Criteria

Phase 2B is complete only when a normal Cowork user can install skills and access AIWS draft/edit/validate/stage/submit through Cowork without Python, `uv`, `uvx`, GitHub CLI, terminal commands, manual plugin-file edits, or manual MCP setup.

If Cowork cannot support a safe managed/custom connector path, a supported local runtime path, or another clean adapter model for draft/edit/validate/stage/submit, Phase 2B is blocked. In that case, Phase 2A remains the honest technical-pilot path, the Claude Code workshop remains the maintainer/private-skills path, and the project should not call the Cowork skills-management workflow end-user ready.

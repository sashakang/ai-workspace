# Cowork Skills-Management Implementation Slices

This document turns the urgent Phase 2 Cowork skills-management MVP in `docs/aiws-cowork-skills-management-mvp.md` into small implementation slices for a developer session. It is a planning document only. Do not implement code from this file directly without first checking the referenced contracts and tests.

Phase 2 now starts from the Cowork Personal marketplace path. The 2026-05-14 canonical Cowork user test passed: Cowork installed marketplace `sashakang/ai-workspace`, installed `core-aiws@ai-workspace` and `aiws-productivity@ai-workspace`, exposed `aiws-productivity:meeting-followup`, invoked the skill successfully, updated the marketplace/plugins through the Cowork UI, and kept `meeting-followup` visible after update. See [Cowork Canonical User Test Report](./cowork-canonical-user-test-report-2026-05-14.md). The proven Cowork Team upload/import path remains a fallback, not the primary journey. The installed source package for the MVP should normally be marketplace-installed; it may be an uploaded Cowork plugin ZIP only when marketplace access is unavailable or the fallback path is explicitly under test. In both cases, Cowork must own the install and update operation, and AIWS must not edit installed plugin folders or runtime RPM state by hand.

The current `core-aiws` MCP bridge is a Phase 2A technical pilot when it depends on `uvx` to launch `aiws-mcp`. That dependency is acceptable only for maintainers and technical testers. For private and non-public skills, the preferred near-term path is now a Claude Code skill workshop for maintainers/operators, not MCP running inside Claude Code and not hosted remote MCP. The workshop should update skill source, validate contracts, build Cowork packages, push to GitHub as the maintainer or bot, and prepare or upload marketplace artifacts on demand.

Cowork marketplace/upload plugins remain the skills distribution and user-facing install/use surface. Cowork edit UX remains the product target, but it is deferred until the runtime and security model are clean. Hosted FastMCP or official MCP Python SDK connector work remains a parked secondary/future proof registered through Cowork's supported managed/custom connector path. It must not expose private skills, memory, drafts, proposal records, or source content until auth, permissions, and tenancy are designed. Normal Cowork users must not require Python, `uvx`, GitHub CLI, shell commands, uploaded-plugin runtime setup, or manual MCP setup.

The package-update boundary is explicit. AIWS can validate source, create drafts, stage proposals, materialize adapter output under `~/.aiws/hosts/<host-id>/adapter`, cache materialized skills under `~/.aiws/hosts/<host-id>/shared-cache/skills`, and prepare package-upload artifacts. Cowork owns plugin install, plugin update, and activation through marketplace/package UI. AIWS must treat `~/.cowork/plugins` as read-only and must not require a repo clone, terminal command, manual RPM/runtime edit, direct installed-plugin edit, or `~/.claude` edit in the canonical user path.

The implementation must stay aligned with `core-aiws/contracts/skill-management.md`. The main implementation surfaces to inspect are `aiws-mcp/aiws_mcp/skill_manager.py` and `aiws-mcp/aiws_mcp/runtime.py`, with tests in `tests/test_aiws_skill_manager.py`, `tests/test_aiws_mcp.py`, and `tests/test_aiws_productivity_plugin.py`.

The current tester-facing Phase 2A scenario is tracked in `docs/cowork-skills-management-phase2-test-plan.md`.

Registry-alignment update, 2026-05-15: after `core-aiws` 0.3.9 fallback activation, Cowork could run the manually uploaded modified `aiws-productivity:meeting-followup` package, but duplicate visible `aiws-productivity` instances were present. The approved next slice is a small read-only installed-skill copy check, documented in [Cowork Registry Alignment Gate 1](./cowork-registry-alignment-gate1-2026-05-15.md). Do not continue activation UX work by guessing the active plugin instance, editing Cowork runtime folders, or treating hostloop paths as durable source roots.

Previous Cowork runtime blocker: the user reported that the Cowork session did not expose `aiws.skills.create_or_open_draft` or `aiws.skills.validate_draft` as callable tools. ToolSearch returned no AIWS draft-management schemas. `core-aiws` version `0.3.7` now bundles the AIWS MCP bridge source, includes the Scenario D draft-record safety fix, and returns a safe submit-for-review handoff when `gh` is unavailable. Cowork runtime testing on 2026-05-14 validated the full Phase 2A A-H lifecycle with host `gh` present, including PR creation and maintainer merge in the private test repo. A later regular Cowork user test proved the draft/edit/validate/stage/submit path end to end for `aiws-productivity:meeting-followup`, including draft `aiws-productivity--meeting-followup--de0e75a572`, proposal `skillprop_ed458362021141179dbdb85a9df73794`, and PR #2 in `sashakang/aiws-skill-tests`. That historical test predated the corrected Gate 1 boundary; current normal Cowork submission leaves review and merge to repository maintainers and policy instead of writing product-level reviewer-role metadata. Do not count manual `/tmp` copies, schema-only validation, CLI-only execution, or direct filesystem reconstruction as Cowork runtime validation.

Current validation update, 2026-05-15: the regular-user loop has now been retested and recorded in `docs/aiws-testing-manual.md`. Draft `aiws-productivity--meeting-followup--de0e75a572` validated with digest `c94dc08ad7a6633e2755611fc8f9866a158793c63617325cb9db63618e964265`, manual package upload worked, pending-upload cleanup worked, the repository allowlist guard blocked a placeholder target repo, and proposal `skillprop_bb386ac3528247c7bf7ddb88793497b2` submitted PR #3 to `sashakang/aiws-skill-tests`. The remaining product gap is activation UX: manual upload is a fallback/technical-pilot bridge, and duplicate visible plugin instances are not acceptable for the final normal-user path.

## Session Rules

- Owner for every slice: developer session.
- Keep changes small enough to review in one focused pass.
- Do not mutate managed marketplace or organization plugin files in place.
- Do not mutate Cowork installed plugin folders or RPM/runtime state in place.
- Treat Cowork marketplace/package upload as the install and update boundary; AIWS prepares packages and adapter/cache output, Cowork installs or updates them.
- Keep normal user flows product-language first: `Personal`, `PNC skills`, `Company skills`, and `Public skills`.
- Do not treat `uvx`, Python, GitHub CLI, or terminal setup as acceptable requirements for normal users. If a slice depends on them, label it technical-pilot only.
- Do not run AIWS MCP inside Claude Code for the maintainer/private-skill workshop path.
- Do not expose private skills, memory, drafts, proposal records, or source content through hosted remote MCP until auth, permissions, and tenancy are designed.
- Do not treat uploaded-plugin `.mcp.json` stdio/HTTP runtime experiments as the Phase 2B path forward. They are closed evidence unless Cowork documents or proves a supported local runtime path.
- Branches, commits, package rebuilds, and pull requests are backend details unless the user explicitly asks. Normal users stage and submit through Cowork UI; repo and skill maintainers review and merge in GitHub.
- AI-engineering reviewer rule: every slice needs a brief reviewer note that explains the AI-facing behavior, the state transition, and why the change cannot silently overwrite user edits or expose duplicate skill identities.
- Validation-only and dry-run paths must not repair, backfill, delete, activate, update, stage, submit, or upload anything.

## Slice 1: Create Or Open Draft From Installed Skill

Owner: developer session.

Expected output: A Cowork-facing operation can create or reopen a draft for an installed skill using the logical identity `plugin_id + skill_id`, origin metadata, and base version/ref/commit. Editable files are copied under `~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>`, and the authoritative draft record is written under `~/.aiws/state/skill-drafts/`.

Acceptance: Creating a draft first inspects installed copies for the requested `plugin_id + skill_id`. A single matching installed copy is selected as the source. Duplicate matching copies fail closed with `duplicate_visible_identity`; AIWS must not guess. The selected source plugin is then validated, copied once, recorded with origin metadata, and returned on repeat calls without overwriting local edits. The draft path must match `aiws-mcp/aiws_mcp/skill_manager.py`: slug-normalized marketplace and plugin values, plus `origin-repo-sha10 = sha256(origin_repo)[:10]`. The suffix prevents origin collisions but does not change the user-facing identity or create duplicate visible skills. A requested skill missing from the installed plugin fails closed. An orphaned draft directory without a usable registry record fails closed and is not deleted.

Evidence: Unit tests should cover first create, reopen without overwrite, missing skill, invalid source plugin, and orphaned draft directory. Existing coverage to preserve and extend is in `tests/test_aiws_skill_manager.py`, especially the `create_or_open_draft` tests.

Likely files, modules, and contracts to inspect: `docs/aiws-cowork-skills-management-mvp.md`, `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `tests/test_aiws_skill_manager.py`, `.claude-plugin/marketplace.json`, plugin manifests under `.claude-plugin/plugin.json`, and plugin contracts under `contracts/*.contract.json`.

## Slice 2: Validate Draft Before Activation Or Staging

Owner: developer session.

Expected output: A draft validation path can validate the draft package boundary and skill compatibility before activation, staging, or submit/upload. It should update or return `last_validation_status` without performing activation or proposal submission.

Acceptance: Validation checks marketplace and plugin manifests where present, plugin contracts, Codex `skill-creator` compatibility rules, contract public skill references, and version alignment across marketplace entries, plugin manifests, and contracts where those files exist. MCP config validation applies only when an existing plugin/package already contains MCP config and the current validator behavior applies; otherwise defer MCP validation to control-plane or release-readiness work. Skill folders keep `SKILL.md` frontmatter limited to `name` and `description`; folder name and frontmatter name match; names use lowercase letters, digits, and single hyphens; support files live under `scripts/`, `references/`, or `assets/`; clutter files are rejected.

Evidence: Tests should prove valid drafts pass; extra frontmatter, missing `SKILL.md`, clutter files, contract-public-skill mismatch, and manifest/contract version mismatch fail. Add bad MCP shape and inline secret-like MCP value coverage only for fixtures that already contain MCP config and are covered by existing validator behavior. Existing tests in `tests/test_aiws_skill_manager.py` already cover many validator rules and should be extended rather than duplicated.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `tests/test_aiws_skill_manager.py`, `aiws-productivity/skills/meeting-followup/SKILL.md`, `aiws-productivity/contracts/aiws-productivity.contract.json`, and `core-aiws/contracts/core-aiws.contract.json`.

## Slice 3: Activate Modified Local Skill With One Visible Identity

Owner: developer session.

Expected output: For the current Cowork slice, activation prepares a package for manual Cowork upload and records a pending upload state. It does not install into Cowork, patch Cowork runtime files, or create an active runtime overlay. The user can use the modified skill in Cowork only after uploading the package through a Cowork-supported UI path.

Acceptance: Activation state has two meanings in this slice: absent means inactive, and `pending_upload` means a package exists for manual Cowork upload. `pending_upload` is stored under `~/.aiws/state/draft-activations/<host-id>/` after the runtime resolves or verifies the concrete Cowork host identity. It is visible only through management/status responses and must not affect `resolve`, `get`, `search`, `list_local`, or runtime skill content. It must not create a second visible skill, and it must not claim the draft is active in Cowork before a supported Cowork install/upload step happens.

Cowork runtime validation: direct host install is unsupported by current Cowork host surfaces. Until Cowork documents or exposes a supported direct activation capability, activation returns a non-terminal state such as `handoff_prepared` or `host_capability_missing` when Cowork cannot confirm the draft programmatically. AIWS must not patch `~/.cowork/plugins` to simulate activation.

Evidence: Tests should prove a modified draft produces a package and a `pending_upload` record, unchanged/invalid/out-of-scope drafts do not, pending state does not leak into runtime resolution, and activation does not mutate installed marketplace files, Cowork runtime/RPM state, `~/.claude`, proposal records, or GitHub. Add coverage proving activation rejects tampered draft records before package or pending-state writes, activation metadata cannot escape `~/.aiws/state/draft-activations/` through path traversal or symlinks, and `deactivate_draft` clears only the matching pending record by exact `draft_id` without deleting user-chosen package artifacts or clearing the draft's modified state.

Likely files, modules, and contracts to inspect: `docs/aiws-cowork-skills-management-mvp.md`, `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/runtime.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 3B: Replace Manual Upload With User-Friendly Activation

Owner: developer session.

Gate 1: approved for staged implementation in `docs/cowork-activation-update-gate1-2026-05-15.md`. The approved scope is a safer activation handoff, not a claim that Cowork activation is complete.

Expected output: A normal Cowork user can activate or prepare activation for a modified draft without manually finding and uploading a ZIP in the happy path. The implementation must use only Cowork-supported install/update surfaces. If no supported activation surface exists, the result stays non-terminal and honest, but the UX should guide the user through one clear Cowork action rather than exposing package mechanics as the product flow.

Acceptance: Activation preserves one logical visible skill identity. It does not leave two visible active copies of `aiws-productivity:meeting-followup` unless the user explicitly chooses a separate uploaded copy or scope. Installed marketplace and organization plugin folders remain read-only. `~/.claude`, Cowork RPM/runtime files, and unmanaged plugin folders remain untouched. Repeated activation is idempotent or returns the existing pending/active state. Cleanup semantics distinguish "clear AIWS pending state" from "uninstall Cowork-uploaded plugin". The manual ZIP upload path remains documented only as fallback/technical-pilot behavior.

Evidence: Tests should extend the current CW-08/CW-09/CW-10 coverage. They must prove no manual ZIP handling is required in the handoff path, duplicate visible skill identity is avoided or reported as a fail-closed conflict, activation state is correctly reported as `active`, `pending_upload`, `handoff_prepared`, `handoff_required`, or `host_capability_missing`, and deactivation does not remove Cowork-owned installed packages. Add a new scenario to `docs/aiws-testing-manual.md` when the implementation exists.

Likely files, modules, and contracts to inspect: `docs/aiws-testing-manual.md`, `docs/cowork-modified-draft-upload-report-2026-05-15.md`, `docs/cowork-pending-upload-deactivation-report-2026-05-15.md`, `aiws-mcp/aiws_mcp/runtime.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, `scripts/cowork_package_intake_probe.py`, `tests/test_aiws_mcp.py`, and `tests/test_cowork_package_intake_probe.py`.

## Slice 3C: Check Installed Skill Copies Before Activation UX

Owner: developer session.

Gate 1: approved in `docs/cowork-registry-alignment-gate1-2026-05-15.md`.

Expected output: AIWS can say whether it sees zero, one, or multiple installed copies of a logical skill.

Acceptance: The slice is read-only. If multiple installed instances share the same `plugin_id + skill_id`, AIWS returns `duplicate_visible_identity` and does not choose one unless the caller pins a concrete source. The response must not ask normal users to inspect RPM paths; it should state that Cowork has more than one installed copy and that cleanup or exact source selection is required before AIWS can manage that identity safely.

Evidence: Tests should cover one installed copy, duplicate installed copies, missing skill, explicit source pinning, and no writes outside approved AIWS-owned state. Preserve existing `discover_installed_plugins` coverage that returns `ambiguous_installed_plugin` for duplicate roots.

Runtime update: the first `core-aiws` 0.3.10 test showed that explicit `source_plugin_root` works, but default discovery missed Cowork's RPM install path. The next implementation should add known Cowork RPM/plugin roots and bounded Claude local-agent session RPM roots to default discovery without broad filesystem scanning or any Cowork runtime mutation.

Runtime update after `core-aiws` 0.3.12: Scenario 9A passed. AIWS found one installed `aiws-productivity:meeting-followup` instance without explicit source pinning and did not mutate state. The installed-copy safety check is now usable before draft/edit work proceeds.

Implementation update in `core-aiws` 0.3.13: `create_or_open_draft` now uses the installed-copy inspection result when no explicit `source_plugin_root` is provided. This makes the safety check part of the normal draft-open path.

Runtime update after `core-aiws` 0.3.13: the inspected draft/edit/validate/stage/submit path passed through Cowork and created PR #4 in `sashakang/aiws-skill-tests`.

Likely files, modules, and contracts to inspect: `docs/cowork-registry-alignment-gate1-2026-05-15.md`, `docs/cowork-activation-handoff-039-runtime-report-2026-05-15.md`, `aiws-mcp/aiws_mcp/runtime.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, `tests/test_aiws_skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 4: Track Modified Locally Status

Owner: developer session.

Expected output: The draft registry and Cowork-facing skill summary expose enough state to show the same skill identity with `Modified locally` or `Modified locally, pending Cowork upload` status when a draft differs from the installed base or has a prepared package.

Acceptance: The system can determine and persist `modified=true` based on draft content compared with the base content or base digest. Status changes are deterministic, do not depend on UI-only state, and survive process restart. A clean reopened draft remains unmodified. A local edit changes the status to `Modified locally`. Preparing a Cowork package records `pending_upload` without changing runtime resolution. Reverting clears the draft record and removes local draft files only under allowed roots; deactivation clears pending upload state without touching Cowork or uploaded packages.

Evidence: Tests should include unchanged draft, changed draft, reopened changed draft, status serialization/readback, and revert behavior. Existing draft record and revert tests in `tests/test_aiws_skill_manager.py` are the base.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `tests/test_aiws_skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 5: Stage Local Proposal Record Distinct From Submit PR

Owner: developer session.

Expected output: `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)` stages a proposed improvement with provenance and review notes. `target_scope` is the Cowork/user-facing label and policy scope. `target_repo` is the concrete backend review repository persisted for later submit-for-review. This is distinct from `submit_pr`; it writes a local record first and does not upload unless a later explicit submit-for-review action is chosen in Cowork.

Acceptance: Staging requires a valid modified draft, a chosen target scope, target review repository, summary, and rationale. Staging owns current validation for this slice: it revalidates the current draft tree, records the validation digest, and writes no proposal if current validation fails. The proposal record is written under `~/.aiws/state/skill-proposals/` and includes installed source identity, marketplace, repository, plugin, skill, version or commit, draft identity/path, validation result, target scope, target repository, summary, rationale, and active/modified status at staging time. Staging must not be silently mapped to `submit_pr`. A later submit-for-review flow may read the staged record and create or update a GitHub pull request, but only after an explicit Cowork UI action.

Evidence: Tests should prove staging writes only the local proposal record after current validation passes, rejects invalid or unmodified drafts, preserves provenance, records target scope and target repository, and does not call submit/upload. Add explicit negative coverage that a `stage_change` or `stage_proposal` path is not treated as `submit_pr`.

Likely files, modules, and contracts to inspect: `docs/aiws-cowork-skills-management-mvp.md`, `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `tests/test_aiws_skill_manager.py`, and the proposal-record state directory `~/.aiws/state/skill-proposals/`. Do not map this slice to the existing `aiws.skills.stage_change` surface; that surface is legacy host-local staged writes and lacks `draft_id`, `target_repo`, and validation-digest semantics.

## Slice 6: Submit Staged Proposal For Review From Cowork

Owner: developer session.

Expected output: A staged proposal can be submitted from Cowork through a user-friendly submit-for-review action. If no Cowork-compatible GitHub submit adapter is available, the backend returns `submit_handoff_required` after all normal submit gates pass. The backend may create or update a GitHub pull request when a real adapter is available, but the normal user does not need to use GitHub UI or handle branch, commit, remote, or token mechanics directly.

Acceptance: Submission requires an existing staged proposal, a still-valid draft, the proposal's stored target repository, and an explicit user action. It creates or updates a reviewable GitHub pull request or equivalent review item when an adapter is available, records the branch name and PR URL in the proposal state only after a real review item exists, and returns a Cowork-facing status such as `Submitted for review`. If only the no-`gh` handoff is available, it returns `submit_handoff_required` and does not mark the proposal submitted or write branch/PR metadata. Normal Cowork submission does not emit reviewer-role metadata unless explicit product-specific roles were provided. Review metadata must not be written to the draft record because one draft can have multiple proposals to different target repos. Submission must use deterministic branch identity `aiws/skill-proposals/<proposal_id>` for retry safety and refuse drafts whose current tree no longer matches the staged validation digest. It must not direct-push to protected branches, mutate managed plugin files in place, or submit a draft whose validation has failed. Repo and skill maintainers review, comment on, request changes, and merge in GitHub.

Evidence: Tests should prove submission reads an existing staged proposal, refuses missing or failed-validation proposals, rejects post-stage draft edits, records PR metadata only on the proposal, omits product-level reviewer-role metadata in the normal flow, returns already-submitted metadata without duplicate submitter calls, keeps git mechanics out of the normal user response, and does not run during staging. GitHub integration can be mocked or adapter-owned; do not require live GitHub for unit tests. Live runtime evidence should separately report whether GitHub repository policy is present, missing, or unknown.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `docs/aiws-cowork-skills-management-mvp.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `tests/test_aiws_skill_manager.py`, and any future GitHub adapter surface.

## Slice 7: Update Conflict Handling With Three Choices

Owner: developer session.

Expected output: Update from GitHub or another managed source detects a modified draft or pending Cowork upload as a hard conflict and returns only the approved choices.

Acceptance: With no modified draft and no pending Cowork upload, update can proceed through the normal update path. With a modified draft or pending Cowork upload, update fails closed and offers exactly: `keep_local_draft_and_pending_package`, `discard_local_changes_and_update`, and `submit_or_upload_first`. No silent merge, overwrite, background submission, auto-resolution, or extra choice is exposed. The user must make one explicit choice before update continues.

Evidence: Tests should assert the exact machine choices and any Cowork-facing labels map one-to-one to those choices. Existing coverage is in `tests/test_aiws_skill_manager.py` around `update_from_github_decision`; extend it for clean drafts, modified drafts, pending-upload drafts, and UI label mapping if labels are added.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `docs/aiws-cowork-skills-management-mvp.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, and `tests/test_aiws_skill_manager.py`.

## Slice 8: Enforce Write-Root Boundaries

Owner: developer session.

Expected output: All create, validate, activate, stage, update, submit, and revert operations enforce the allowed write roots from the skill-management contract.

Acceptance: Allowed write roots are `~/.aiws/plugins/`, `~/.aiws/state/skill-drafts/`, `~/.aiws/state/skill-proposals/`, `~/.aiws/state/draft-activations/`, and temporary package build output. Managed marketplace and organization plugin files are read-only inputs. Disallowed memory roots are never touched. Path traversal, symlinked roots, symlinked child paths, root-as-draft-path records, non-deterministic draft paths, and direct mutation of managed source packages fail closed.

Evidence: Tests should cover path traversal, symlinked plugin root, symlinked state parent/root, deterministic draft path symlink, draft path outside allowed roots, root-as-draft-path, validation dry-run writes nothing, and activation/staging writes only approved roots. Existing boundary tests in `tests/test_aiws_skill_manager.py` should be preserved and extended; host write-root checks in `tests/test_aiws_mcp.py` are relevant for adapter-owned writes.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `tests/test_aiws_skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 9: Tests And Fixtures For End-To-End MVP Behavior

Owner: developer session.

Expected output: A compact fixture set and tests cover the full MVP journey without relying on real Cowork, real GitHub, or user home directories.

Acceptance: Fixtures include a valid installed marketplace plugin with one public skill, an invalid skill frontmatter case, a version mismatch case, a modified draft case, a pending-upload conflict case, a duplicate visible identity case, and a staging proposal record case. Tests use temporary AIWS roots and fake host roots. No test writes to the developer's real `~/.aiws`, `~/.cowork`, `~/.codex`, or managed marketplace checkout.

Evidence: A developer can run the relevant suite locally and see focused failures if identity, validation, staging, conflict handling, or write boundaries regress. Suggested command after implementation is `python -m unittest tests.test_aiws_skill_manager tests.test_aiws_mcp tests.test_aiws_productivity_plugin`.

Likely files, modules, and contracts to inspect: `tests/test_aiws_skill_manager.py`, `tests/test_aiws_mcp.py`, `tests/test_aiws_productivity_plugin.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `.claude-plugin/marketplace.json`, `aiws-productivity/.claude-plugin/plugin.json`, and `aiws-productivity/contracts/aiws-productivity.contract.json`.

## Slice 10: Claude Code Skill Workshop

Owner: developer session.

Expected output: A maintainer/operator workflow uses Claude Code functionality, not MCP in Claude Code, to update skill source, validate contracts, build Cowork packages, push to GitHub as the maintainer or bot, and prepare or upload marketplace artifacts on demand.

Acceptance: The workflow is explicitly labeled maintainer/private-skill only and is not presented as the normal Cowork user path. It validates before package build, push, or upload. It keeps Cowork as the user-facing install/use surface, preserves repository review boundaries, and does not expose private skill content through hosted MCP. It can prepare artifacts for Cowork while leaving Cowork edit UX deferred until the runtime/security model is clean.

Evidence: Maintainer workflow doc or command surface, package build output, validation/test output, changed-file summary, and dry-run or real publication notes when explicitly requested.

## Slice 11: Parked Hosted FastMCP Control-Plane Proof

Owner: developer session.

Expected output: A hosted FastMCP or official MCP Python SDK AIWS control-plane proof can be registered through Cowork's supported managed/custom connector path when needed. It exposes only harmless tools such as `aiws.health.ping` and `aiws.runtime.info`.

Acceptance: A normal Cowork user can install the AIWS skills through Cowork and access the harmless AIWS control-plane proof tools through Cowork without Python, `uvx`, GitHub CLI, shell commands, uploaded-plugin runtime setup, or manual MCP setup. The proof must not expose memory tools, private skills, drafts, proposal records, source content, lifecycle tools, or managed marketplace/organization plugin mutation. It must not claim that draft/edit/validate/stage/submit is production-ready. FastMCP/Python is preferred because the existing AIWS control-plane code is already Python; TypeScript SDK work is deferred unless AIWS builds a new hosted service from scratch.

Evidence: Cowork connector configuration, runtime logs, visible tool names, one successful `aiws.health.ping` or `aiws.runtime.info` call, and a dependency audit proving the user did not use Python/`uvx`/`gh`/shell/manual MCP setup. If Cowork cannot support the connector path, keep this proof parked rather than passing the end-user MVP.

## Slice 12: Full Phase 2B Lifecycle Through Cowork

Owner: developer session.

Expected output: A normal Cowork user can install skills and access AIWS draft/edit/validate/stage/submit through Cowork without developer tooling.

Acceptance: The lifecycle works through Cowork and the supported control-plane path. Proposal staging remains distinct from GitHub submission. Managed plugin files remain read-only. GitHub submission uses a GitHub App, bot, API, or Cowork-compatible adapter, not normal-user `gh`. If the submit adapter is unavailable, `submit_handoff_required` remains non-terminal and does not mark the proposal submitted.

Evidence: Manual Cowork validation report, connector/runtime logs, proposal state records, and mocked or adapter-owned GitHub submission tests. Do not count Phase 2A `uvx` bridge runs, uploaded-plugin runtime smoke tests, CLI-only execution, or host `gh` as Phase 2B evidence.

## Slice 13: Repository Policy-Owned Review

Owner: developer session.

Expected output: AIWS reports repository-policy signals for proposals and PRs while GitHub repository policy owns assignment and approval. Normal Cowork users do not map GitHub reviewers or teams, and normal Cowork submission does not hardcode reviewer roles.

Corrected Gate 1 plan: AIWS keeps deterministic branch/PR behavior and may detect whether repository enforcement exists. GitHub enforces reviewer assignment and approval through CODEOWNERS, branch protection, repository rules, or maintainer-owned automation. If CODEOWNERS or reviewer policy is absent, AIWS reports the missing enforcement as a caveat and does not claim routing is enforced.

Acceptance: Submission reports repository review enforcement as present, absent, or unknown when that signal is available. Missing CODEOWNERS or empty review requests are visible in Cowork-facing status and proposal state. The PR body states that review and merge are managed by repository maintainers and policy. The implementation does not require normal users to choose GitHub accounts, teams, or repository policy details.

Evidence: Unit tests for reviewer-enforcement status parsing and proposal-state reporting, plus one live GitHub validation against a repo with no policy and one against a repo with enforced policy when that repo is available.

## Suggested Developer Session Order

1. Implement Slice 4, modified-state tracking, first. The registry already has `modified` and `last_validation_status`, and draft create/open plus write-root safety are already partially covered. Computing and persisting modified state unlocks activation status, proposal metadata, and conflict handling.
2. Add the missing Slice 1 and Slice 2 edge tests while touching the same surface: missing skill, invalid source plugin, and a draft validation operation that updates or returns `last_validation_status` without activation or staging.
3. Wire activation identity behavior and `Modified locally` status.
4. Keep Phase 2A implementation evidence separate: run the focused unit tests and add missing fixtures where coverage is still thin.
5. Build Slice 10 as the near-term maintainer/private-skill path: Claude Code skill workshop operations for source updates, validation, Cowork package build, GitHub push, and marketplace artifact preparation.
6. Keep Slice 11 parked as a harmless connector proof only: hosted FastMCP or official MCP Python SDK tools (`aiws.health.ping`, `aiws.runtime.info`) through Cowork's supported managed/custom connector path, with no private state exposure.
7. Design any connector-backed draft lifecycle only after the security model is clear enough to protect private skills, memory, drafts, proposal records, and source content.
8. Implement or resume lifecycle work through the clean Cowork path as appropriate, including local proposal-record staging as distinct from submit/upload and update conflict choice handling.
9. Add GitHub App, bot, API, or Cowork-compatible submit-for-review behavior later than the workshop and runtime/security design; normal-user GitHub CLI submission must be replaced.
10. Add repository-policy detection and reporting after the submit adapter path is clear. AIWS may report enforcement signals such as CODEOWNERS or review requests, while GitHub repository maintainers and policy own reviewer assignment and approval.

The final implementation review should check the AI-engineering reviewer rule for every slice: the behavior must be understandable to an AI agent operating through the skill-management surface, state transitions must be explicit, and no flow may quietly overwrite local work or expose two visible copies of the same logical skill.

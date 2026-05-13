# Cowork Skills-Management Implementation Slices

This document turns the urgent Phase 2 Cowork skills-management MVP in `docs/aiws-cowork-skills-management-mvp.md` into small implementation slices for a developer session. It is a planning document only. Do not implement code from this file directly without first checking the referenced contracts and tests.

Phase 2 now starts from the Cowork Personal marketplace path. The user reported that Cowork can install the AIWS plugins from the marketplace and generate `meeting-followup` nodes correctly. The proven Cowork Team upload/import path remains a fallback, not the primary journey. The installed source package for the MVP should normally be marketplace-installed; it may be an uploaded Cowork plugin ZIP only when marketplace access is unavailable or the fallback path is explicitly under test. In both cases, Cowork must own the install operation and AIWS must not edit runtime RPM state by hand.

The current `core-aiws` MCP bridge is a Phase 2A technical pilot when it depends on `uvx` to launch `aiws-mcp`. That dependency is acceptable only for maintainers and technical testers. The Phase 2B target package for normal Cowork users must not require Python, `uvx`, GitHub CLI, shell commands, or any manual runtime setup outside Cowork.

The implementation must stay aligned with `core-aiws/contracts/skill-management.md`. The main implementation surfaces to inspect are `aiws-mcp/aiws_mcp/skill_manager.py` and `aiws-mcp/aiws_mcp/runtime.py`, with tests in `tests/test_aiws_skill_manager.py`, `tests/test_aiws_mcp.py`, and `tests/test_aiws_productivity_plugin.py`.

The current tester-facing Phase 2A scenario is tracked in `docs/cowork-skills-management-phase2-test-plan.md`.

Previous Cowork runtime blocker: the user reported that the Cowork session did not expose `aiws.skills.create_or_open_draft` or `aiws.skills.validate_draft` as callable tools. ToolSearch returned no AIWS draft-management schemas. `core-aiws` version `0.3.7` now bundles the AIWS MCP bridge source, includes the Scenario D draft-record safety fix, and returns a safe submit-for-review handoff when `gh` is unavailable. Retest through the Cowork marketplace install before treating the runtime slice as accepted. Do not count manual `/tmp` copies, schema-only validation, CLI-only execution, or direct filesystem reconstruction as Cowork runtime validation.

## Session Rules

- Owner for every slice: developer session.
- Keep changes small enough to review in one focused pass.
- Do not mutate managed marketplace or organization plugin files in place.
- Keep normal user flows product-language first: `Personal`, `PNC skills`, `Company skills`, and `Public skills`.
- Do not treat `uvx`, Python, GitHub CLI, or terminal setup as acceptable requirements for normal users. If a slice depends on them, label it technical-pilot only.
- Branches, commits, package rebuilds, and pull requests are backend details unless the user explicitly asks. Normal users stage and submit through Cowork UI; repo and skill maintainers review and merge in GitHub.
- AI-engineering reviewer rule: every slice needs a brief reviewer note that explains the AI-facing behavior, the state transition, and why the change cannot silently overwrite user edits or expose duplicate skill identities.
- Validation-only and dry-run paths must not repair, backfill, delete, activate, update, stage, submit, or upload anything.

## Slice 1: Create Or Open Draft From Installed Skill

Owner: developer session.

Expected output: A Cowork-facing operation can create or reopen a draft for an installed skill using the logical identity `plugin_id + skill_id`, origin metadata, and base version/ref/commit. Editable files are copied under `~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>`, and the authoritative draft record is written under `~/.aiws/state/skill-drafts/`.

Acceptance: Creating a draft validates the source plugin first, copies the installed source once, records origin metadata, and returns the existing draft on repeat calls without overwriting local edits. The draft path must match `aiws-mcp/aiws_mcp/skill_manager.py`: slug-normalized marketplace and plugin values, plus `origin-repo-sha10 = sha256(origin_repo)[:10]`. The suffix prevents origin collisions but does not change the user-facing identity or create duplicate visible skills. A requested skill missing from the installed plugin fails closed. An orphaned draft directory without a usable registry record fails closed and is not deleted.

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

Expected output: Activation builds or installs the draft under the same logical plugin and skill identity, replacing the active user-level package through the supported Cowork/plugin install path. The Cowork UI/runtime sees one visible identity and shows `Modified locally` when the active draft differs from its base.

Acceptance: Unit/runtime identity behavior: activating a changed draft never creates a second visible copy of the same logical skill. The installed marketplace or organization package remains available internally as fallback/cache, but the active local draft wins in user-facing resolution. If duplicate visible variants are possible and scope is not pinned by user choice or organization policy, resolution fails closed.

Cowork runtime validation: direct Cowork proof is pending host capability. Until that exists, activation returns `host_capability_missing` with one non-terminal package-upload action when Cowork cannot activate the draft programmatically.

Evidence: Unit/runtime tests should prove materialized or activated local skill records replace fallback identities instead of duplicating them; `Modified locally` is returned for active changed drafts; ambiguous duplicate variants fail closed unless pinned by scope/version. Cowork runtime evidence can remain pending until direct host capability exists, but host capability gaps must return a clear non-terminal action. Existing identity and ambiguity tests live in `tests/test_aiws_mcp.py`, especially `test_materialized_skill_replaces_builtin_fallback_identity` and `test_duplicate_shared_skill_ids_fail_closed_unless_pinned`.

Likely files, modules, and contracts to inspect: `docs/aiws-cowork-skills-management-mvp.md`, `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/runtime.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 4: Track Modified Locally Status

Owner: developer session.

Expected output: The draft registry and Cowork-facing skill summary expose enough state to show the same skill identity with `Modified locally` status when an active draft differs from the installed base.

Acceptance: The system can determine and persist `modified=true` based on draft content compared with the base content or base digest. Status changes are deterministic, do not depend on UI-only state, and survive process restart. A clean reopened draft remains unmodified. A local edit changes the status to `Modified locally`. Reverting clears the draft record and removes local draft files only under allowed roots.

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

Acceptance: Submission requires an existing staged proposal, a still-valid draft, the proposal's stored target repository, and an explicit user action. It creates or updates a reviewable GitHub pull request or equivalent review item when an adapter is available, records the branch name and PR URL in the proposal state only after a real review item exists, and returns a Cowork-facing status such as `Submitted for review`. If only the no-`gh` handoff is available, it returns `submit_handoff_required`, includes required reviewer roles including `AI engineer`, and does not mark the proposal submitted or write branch/PR metadata. Review metadata must not be written to the draft record because one draft can have multiple proposals to different target repos. Submission must use deterministic branch identity `aiws/skill-proposals/<proposal_id>` for retry safety and refuse drafts whose current tree no longer matches the staged validation digest. It must not direct-push to protected branches, mutate managed plugin files in place, or submit a draft whose validation has failed. Repo and skill maintainers review, comment on, request changes, and merge in GitHub.

Evidence: Tests should prove submission reads an existing staged proposal, refuses missing or failed-validation proposals, rejects post-stage draft edits, records PR metadata only on the proposal, includes `AI engineer` reviewer routing, returns already-submitted metadata without duplicate submitter calls, keeps git mechanics out of the normal user response, and does not run during staging. GitHub integration can be mocked or adapter-owned; do not require live GitHub for unit tests.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `docs/aiws-cowork-skills-management-mvp.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `tests/test_aiws_skill_manager.py`, and any future GitHub adapter surface.

## Slice 7: Update Conflict Handling With Three Choices

Owner: developer session.

Expected output: Update from GitHub or another managed source detects an active modified draft as a hard conflict and returns only the approved choices.

Acceptance: With no active modified draft, update can proceed through the normal update path. With an active modified draft, update fails closed and offers exactly: `keep_local_modified_skill_active`, `discard_local_changes_and_update`, and `submit_or_upload_first`. No silent merge, overwrite, background submission, auto-resolution, or extra choice is exposed. The user must make one explicit choice before update continues.

Evidence: Tests should assert the exact machine choices and any Cowork-facing labels map one-to-one to those choices. Existing coverage is in `tests/test_aiws_skill_manager.py` around `update_from_github_decision`; extend it for inactive modified drafts, active unmodified drafts, and UI label mapping if labels are added.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `docs/aiws-cowork-skills-management-mvp.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, and `tests/test_aiws_skill_manager.py`.

## Slice 8: Enforce Write-Root Boundaries

Owner: developer session.

Expected output: All create, validate, activate, stage, update, submit, and revert operations enforce the allowed write roots from the skill-management contract.

Acceptance: Allowed write roots are `~/.aiws/plugins/`, `~/.aiws/state/skill-drafts/`, `~/.aiws/state/skill-proposals/`, and temporary package build output. Managed marketplace and organization plugin files are read-only inputs. Disallowed memory roots are never touched. Path traversal, symlinked roots, symlinked child paths, root-as-draft-path records, non-deterministic draft paths, and direct mutation of managed source packages fail closed.

Evidence: Tests should cover path traversal, symlinked plugin root, symlinked state parent/root, deterministic draft path symlink, draft path outside allowed roots, root-as-draft-path, validation dry-run writes nothing, and activation/staging writes only approved roots. Existing boundary tests in `tests/test_aiws_skill_manager.py` should be preserved and extended; host write-root checks in `tests/test_aiws_mcp.py` are relevant for adapter-owned writes.

Likely files, modules, and contracts to inspect: `core-aiws/contracts/skill-management.md`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `tests/test_aiws_skill_manager.py`, and `tests/test_aiws_mcp.py`.

## Slice 9: Tests And Fixtures For End-To-End MVP Behavior

Owner: developer session.

Expected output: A compact fixture set and tests cover the full MVP journey without relying on real Cowork, real GitHub, or user home directories.

Acceptance: Fixtures include a valid installed marketplace plugin with one public skill, an invalid skill frontmatter case, a version mismatch case, a modified draft case, an active modified conflict case, a duplicate visible identity case, and a staging proposal record case. Tests use temporary AIWS roots and fake host roots. No test writes to the developer's real `~/.aiws`, `~/.cowork`, `~/.codex`, or managed marketplace checkout.

Evidence: A developer can run the relevant suite locally and see focused failures if identity, validation, staging, conflict handling, or write boundaries regress. Suggested command after implementation is `python -m unittest tests.test_aiws_skill_manager tests.test_aiws_mcp tests.test_aiws_productivity_plugin`.

Likely files, modules, and contracts to inspect: `tests/test_aiws_skill_manager.py`, `tests/test_aiws_mcp.py`, `tests/test_aiws_productivity_plugin.py`, `aiws-mcp/aiws_mcp/skill_manager.py`, `aiws-mcp/aiws_mcp/runtime.py`, `.claude-plugin/marketplace.json`, `aiws-productivity/.claude-plugin/plugin.json`, and `aiws-productivity/contracts/aiws-productivity.contract.json`.

## Slice 10: Dependency-Free Cowork Runtime Package

Owner: developer session.

Expected output: The Cowork import artifact can start the AIWS skill-management bridge for a normal Cowork user without requiring user-installed Python, `uvx`, GitHub CLI, or shell commands.

Acceptance: The package either includes a self-contained runtime bridge or uses a Cowork-guaranteed runtime/connector. Installing the package through Cowork is enough for the user to access the skill-management tools. Any remaining `uvx`, Python, or local `gh` dependency is clearly marked as technical-pilot only and blocks Phase 2B acceptance. GitHub review submission must either use a user-visible Cowork/GitHub connection, an organization bot/App, or another supported non-terminal auth path; users must not paste tokens into chat.

Evidence: Add a dependency audit for the Cowork package, a startup smoke test for the packaged runtime, and a manual Cowork validation report proving the tools appear after upload on a machine that has no separately installed Python/`uvx`/`gh` dependency used by AIWS. If Cowork cannot support that yet, record the path as blocked rather than passing the end-user MVP.

## Suggested Developer Session Order

1. Implement Slice 4, modified-state tracking, first. The registry already has `modified` and `last_validation_status`, and draft create/open plus write-root safety are already partially covered. Computing and persisting modified state unlocks activation status, proposal metadata, and conflict handling.
2. Add the missing Slice 1 and Slice 2 edge tests while touching the same surface: missing skill, invalid source plugin, and a draft validation operation that updates or returns `last_validation_status` without activation or staging.
3. Wire activation identity behavior and `Modified locally` status.
4. Add local proposal-record staging as a distinct operation from submit/upload.
5. Add explicit Cowork submit-for-review behavior that can create or update a GitHub PR behind the scenes.
6. Remove or hide technical-pilot runtime dependencies by delivering the dependency-free Cowork runtime package.
7. Finish update conflict choice handling and Cowork-facing labels.
8. Run the focused unit tests and add missing fixtures where coverage is still thin.

The final implementation review should check the AI-engineering reviewer rule for every slice: the behavior must be understandable to an AI agent operating through the skill-management surface, state transitions must be explicit, and no flow may quietly overwrite local work or expose two visible copies of the same logical skill.

# Cowork Skills-Management MVP Notes

## Scope

This note captures the urgent Cowork skills-management MVP for current users after a clean Cowork-supported AIWS install. It follows Phase 2 in `docs/aiws-project-development-plan.md` and depends on the Phase 1 install gate being usable first: a user installs `core-aiws` and a domain plugin through Cowork, then manages an installed skill from that package.

Current install status: the Personal marketplace path is now the primary journey. The user reported that Cowork installed the AIWS marketplace plugins and generated `meeting-followup` nodes correctly. The Cowork Team upload/import flow, `Organization settings -> Plugins -> Add plugin -> Upload a file`, remains a validated fallback using individual ZIPs for `core-aiws` and `aiws-productivity`.

The MVP is intentionally narrow. It covers creating or opening a draft from an installed skill, validating the draft, activating a modified local skill, staging a proposed improvement, submitting it for maintainer review from Cowork, tracking local modification state, and handling update conflicts safely. GitHub can be used as the backend review system, but normal users should not need to use GitHub UI directly. The MVP does not wait for broader memory sync, complete `aiws-mcp` alignment, or the final target control plane, but it must remain compatible with the target architecture in `docs/aiws-target-architecture.md`.

Runtime status has two levels. The current MCP-backed `core-aiws` bridge is a technical pilot path because it starts `aiws-mcp` through `uvx`. It can validate the lifecycle semantics with AIWS maintainers and technical testers, but it is not the target Cowork user experience. The target MVP package must not require normal users to install Python, install `uvx`, configure GitHub CLI, or run terminal commands.

## Source Documents

Use these documents as the governing references:

- `docs/aiws-project-development-plan.md` for phase order and acceptance criteria.
- `docs/aiws-skills-cowork-marketplace.md` for Cowork marketplace, plugin, and scoped-variant behavior.
- `docs/cowork-skills-management-phase2-test-plan.md` for the current Phase 2A validation scenario.
- `core-aiws/contracts/skill-management.md` for the closed operation surface and draft registry contract.
- `docs/aiws-target-architecture.md` for target-state AIWS runtime boundaries.

## MVP User Journey

The user starts from an installed Cowork skill, such as `aiws-productivity/meeting-followup`, installed through the Cowork marketplace path by default. The fallback ZIP upload path is acceptable only when marketplace access is unavailable or explicitly under test. The MVP must not start from a cloned repository, a raw filesystem path, RPM reconstruction, or manual Cowork runtime edits.

1. Create or open a draft from the installed skill.
2. Edit the draft under the AIWS draft workspace.
3. Validate the draft against skill compatibility rules and plugin/package expectations.
4. Activate the modified local skill.
5. See the same skill identity in Cowork with `Modified locally` status.
6. Stage a proposed improvement with provenance and review notes.
7. Submit the staged proposal from Cowork when ready.
8. Let repo or skill maintainers review, comment on, and merge the resulting proposal in GitHub.

The MVP should use product-language targets such as `Personal`, `PNC skills`, `Company skills`, and `Public skills`. Branches, commits, remotes, pull request creation, and package rebuild details are backend concerns unless the user explicitly asks for them.

Normal-user operations must stay inside Cowork. Any Python, `uvx`, `gh`, or shell requirement belongs only to a technical pilot checklist and must be removed or hidden behind a self-contained package before broader customer rollout.

## Local State

Editable draft files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>
```

This is the deterministic path used by `aiws-mcp/aiws_mcp/skill_manager.py`: marketplace and plugin values are slug-normalized, and `origin-repo-sha10` is `sha256(origin_repo)[:10]`. The suffix prevents origin repository collisions. It is not part of the visible skill identity, which remains `plugin_id + skill_id`, and it must not create duplicate visible skills.

The authoritative draft registry lives under:

```text
~/.aiws/state/skill-drafts/
```

The installed marketplace or organization package remains the source variant and fallback/cache. User edits are personal drafts or proposals derived from that installed variant. AIWS must never mutate managed marketplace or organization plugin files in place.

Each draft registry record should preserve the fields required by `core-aiws/contracts/skill-management.md`, including `plugin_id`, `skill_id`, origin marketplace and repository metadata, base version/commit, `draft_path`, `active`, `modified`, publish target, branch name, PR URL, validation status, and `updated_at`.

## Identity And Status

AIWS must preserve one user-facing skill identity. A modified local draft replaces the installed version in the Cowork UI/runtime, while the installed version remains internally available as fallback/cache.

Cowork must not show two visible copies of the same logical skill. The logical identity remains:

```text
plugin_id + skill_id
```

When the local draft is active and changed from its base, Cowork shows the same skill with:

```text
Modified locally
```

If duplicate visible variants of the same logical skill are possible and the scope is not pinned by the user or organization policy, the operation must fail closed rather than guessing.

## Operations

The MVP should stay within the closed skill-management operation surface from `core-aiws/contracts/skill-management.md`:

```text
validate_plugin(source_or_package)
create_or_open_draft(plugin_id, skill_id, origin_repo, origin_marketplace, base_ref)
refresh_modified_status(draft_id)
build_draft_package(draft_id, package_output_dir)
activate_draft(draft_id, host_kind, package_output_dir)
update_from_github(plugin_id, marketplace_id)
stage_proposal(draft_id, target_scope, target_repo, summary, rationale)
submit_pr(proposal_id, submitter)
revert_draft(draft_id)
```

For Phase 2 MVP acceptance, the required staging operation is `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)`. It writes a local proposal record under `~/.aiws/state/skill-proposals/` with enough provenance and review notes for later review. `target_scope` is the Cowork/user-facing label and policy scope. `target_repo` is the concrete backend review repository persisted for later submit-for-review. Staging owns current validation for the draft: it revalidates the current draft tree, records the validation digest, and writes no proposal if current validation fails. It must not be silently treated as `submit_pr`.

`submit_pr` or an equivalent submitter flow is a separate explicit action after staging. It consumes the staged `proposal_id` and uses the proposal's stored `target_repo`; it must not ask for or accept a fresh repository value at submit time. In the Cowork UX, this should appear as a friendly submit-for-review action, not as a git workflow. The backend may create or update a GitHub pull request, and maintainers may use GitHub UI to review and merge it.

For the current Cowork MVP, `activate_draft` should use the reinstall-draft strategy: build a package under the same plugin identity and replace the active user-level plugin package through the supported Cowork/plugin install path. If Cowork cannot activate the draft programmatically, the operation should return `host_capability_missing` with one non-terminal package-upload action instead of pretending activation succeeded.

## Validation

Validation must run before draft activation and before staging or submitting a proposed improvement. The MVP should validate at least:

- marketplace and plugin manifests when a package boundary is involved
- plugin contracts
- skill folder compatibility with Codex `skill-creator` rules
- version alignment across marketplace entries, plugin manifests, and contracts when those files are present

Managed skill folders must keep `SKILL.md` frontmatter limited to `name` and `description`; the folder name must match the frontmatter `name`; names should use lowercase letters, digits, and single hyphens; and support material should live under `scripts/`, `references/`, or `assets/`.

Dry-run or validation-only actions must not repair, backfill, delete, activate, update, or submit anything.

## Update Conflict Handling

When updating from GitHub or another managed source, an active modified draft is a hard conflict. AIWS must fail closed and offer only these three choices:

```text
keep local modified skill active
discard local changes and update
submit/upload first
```

The UI may phrase these in friendlier language, but it must not add extra choices that imply silent merge, overwrite, background submission, or automatic conflict resolution. The user must make an explicit choice before the update proceeds.

## Staging Proposed Improvements

Staging a proposed improvement records the user's draft as a proposal for a target scope. It should include enough provenance for review:

- installed source identity: marketplace, repository, plugin, skill, version or commit
- draft identity and path
- validation result
- chosen target scope
- target review repository
- review notes or change summary
- active/modified status at the time of staging

Staging writes a local proposal record first. Submission comes after that record exists and should create a reviewable proposal, normally a GitHub pull request or equivalent review item. Submission must recheck that the draft tree still matches the validation digest captured during staging; if the draft changed, the user restages. Retry safety comes from deterministic branch identity `aiws/skill-proposals/<proposal_id>`, so repeat submits update or return the same review item instead of creating duplicates. Required reviewer roles include `AI engineer`. Direct push is not part of the normal current-user flow.

Normal users should stay in Cowork for this sequence:

```text
Edit skill -> validate -> stage proposal -> submit for review -> track status
```

Maintainers use GitHub for this sequence:

```text
Review PR -> comment or request changes -> merge -> release/upload updated plugin package
```

Cowork should show user-facing states such as:

```text
Draft
Modified locally
Ready to submit
Submitted for review
Changes requested
Merged
```

## Boundaries

This MVP does not expose memory tools, run memory import/export flows, or touch memory paths. Memory sync is a later shared-infrastructure phase.

This MVP also does not require complete `aiws-mcp` alignment. It may be implemented through the `core-aiws` skill-management bridge or an equivalent Cowork adapter now, as long as the state and identity rules remain compatible with the target control plane. In target state, install, update, draft editing, local activation, staging, and submission should map cleanly onto the AIWS runtime under `~/.aiws/` and the host adapter model in `docs/aiws-target-architecture.md`.

Allowed write roots for the MVP are:

```text
~/.aiws/plugins/
~/.aiws/state/skill-drafts/
~/.aiws/state/skill-proposals/
temporary package build output
```

Managed marketplace and organization plugin files are read-only inputs. Host-specific activation or package export is adapter-owned behavior, not direct mutation of managed source packages.

## Acceptance Notes

The MVP is done when a current Cowork user can:

- create or open a draft from an installed skill
- validate the draft before activation or staging
- activate a modified local skill without creating a duplicate visible identity
- see and track `Modified locally` status for the active modified draft
- stage a proposed improvement with provenance and review notes
- submit a staged proposal for maintainer review from Cowork
- update safely, with active modified draft conflicts limited to the three approved choices
- install and use the skill-management workflow without installing Python, `uvx`, GitHub CLI, or running terminal commands

The technical pilot is useful but not end-user complete while it depends on `uvx` or local GitHub CLI. The MVP is not done if it mutates managed marketplace or organization plugin files in place, creates a second visible copy of the same logical skill, hides local modification state, requires normal users to use GitHub UI for submission, requires normal users to install Python/`uvx`/`gh`, or lets update flows overwrite active local edits without explicit user choice.

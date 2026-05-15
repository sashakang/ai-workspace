# Skill Management Contract

`core-aiws` owns the AIWS skill-management workflow for Cowork-facing install, update, edit, test, staged proposal creation, and submit-for-review handoff. Users install `core-aiws`; they do not install a separate skill-manager plugin.

## Local Manager Boundary

The skill manager is an internal `core-aiws` tool bridge. Its contract covers validation, editable draft creation, draft modified-state refresh, package build and activation, GitHub update decisions, local proposal staging, pull request submission, and draft revert behavior. Some operations are target contract surface and may not be wired as runtime bridge tools in every current slice.

The bridge must expose no memory tools, must not run memory import or export flows, and must not touch memory paths.

Allowed write roots:

```text
~/.aiws/plugins/
~/.aiws/state/skill-drafts/
~/.aiws/state/skill-proposals/
~/.aiws/state/draft-activations/
~/.aiws/state/git-worktrees/
temporary package build output
explicit package output directories supplied by the caller
```

Disallowed write roots:

```text
~/.aiws/memory/
~/.aiws/imports/
~/.aiws/exports/
~/.claude/plugins/data/*memory*
```

## Operation Contract

The skill-management contract is limited to this operation surface:

```text
validate_plugin(source_or_package)
create_or_open_draft(plugin_id, skill_id, origin_repo, origin_marketplace, base_ref, allow_parallel_draft=false)
list_draft_files(draft_id)
read_draft_file(draft_id, relative_path)
write_draft_file(draft_id, relative_path, content)
delete_draft_file(draft_id, relative_path)
refresh_modified_status(draft_id)
validate_draft(draft_id)
build_draft_package(draft_id, package_output_dir)
activate_draft(draft_id, host_kind, host_id, package_output_dir)
deactivate_draft(draft_id, host_kind, host_id)
update_from_github(plugin_id, marketplace_id)
stage_proposal(draft_id, target_scope, target_repo, summary, rationale)
submit_pr(proposal_id, submitter)
revert_draft(draft_id)
```

`create_or_open_draft` must not silently create a second draft for the same `plugin_id + skill_id` when a different active draft already exists. If an active related draft exists, the operation fails closed unless the caller explicitly sets `allow_parallel_draft=true`. Normal Cowork editing should keep using the returned `draft_id` with `read_draft_file`, `write_draft_file`, and later lifecycle operations. The explicit override exists for advanced workflows where the user intentionally wants separate drafts for different origins or review repositories.

`stage_proposal` writes a local proposal record only, under `~/.aiws/state/skill-proposals/`. It records the draft, target scope, target review repository, summary, rationale, provenance, and validation status for later review. `target_scope` is the Cowork/user-facing label and policy scope. `target_repo` is the concrete backend review repository persisted for a later submit-for-review action. Staging must not upload, submit, create a pull request, or push changes; `submit_pr` or another explicit submit-for-review operation is follow-on behavior. Package export or upload is an admin/deployment fallback, not the normal user staging path.

`submit_pr` consumes a staged `proposal_id`, not a fresh repository argument. The proposal's stored `target_repo` is the review destination. Before calling the submitter adapter, the manager revalidates that the current draft tree still matches the staged `validation_tree_digest`, that the plugin still validates with the original plugin ID and version, and that the requested skill still exists. If the draft changed after staging, the user must restage. The submitter receives deterministic branch identity `aiws/skill-proposals/<proposal_id>` and owns GitHub mechanics; it must create or update one review item for retry safety. Normal Cowork proposal submission does not invent reviewer roles. Review and merge are managed by the target repository's maintainers and policies, and normal users are not asked to map GitHub reviewers or teams. If the runtime cannot submit because no Cowork-compatible GitHub adapter is available, the submitter may return a non-terminal `submit_handoff_required` result after all gates pass. That result must not mark the proposal submitted or write branch/PR metadata. PR metadata is stored on the proposal record only after a real review item exists, because one draft can have multiple proposals to different target repos.

The runtime may use a GitHub REST API submitter when a host-provided GitHub token is available. Tokens must come from environment or host configuration, not from normal users pasting credentials into chat. If no API submitter is configured, `gh` may remain a technical-pilot fallback; if neither path is available, submission returns `submit_handoff_required`.

Successful submit responses and submit handoff responses must include `post_merge_delivery` guidance. The guidance explains that regular users do not manually upload ZIP files in the normal path. After maintainer merge, Cowork receives the updated plugin through GitHub-synced marketplace update/sync or, for manual marketplaces, a maintainer/admin same-name ZIP upload that overwrites the old plugin.

Draft file operations are the Cowork-facing edit surface for this phase. They are limited to text files under `skills/<skill_id>/` for the draft's own `skill_id`. They must reject path traversal, absolute paths, symlinks, binary content, and any path outside that managed skill folder. They must not edit contracts, plugin manifests, memory paths, installed source plugin packages, or Cowork/Claude runtime state.

For this phase, proposals are skill-folder-only. `validate_draft`, `stage_proposal`, and `submit_pr` must reject a draft if any changed path is outside `skills/<skill_id>/`. `validate_draft` refreshes and persists validation status and digest metadata without staging, submitting, activating, or building a package. The GitHub submitter must sync exactly that skill folder into the target repository, so the validated proposal content and the pull request diff cannot diverge.

`build_draft_package` requires an explicit `package_output_dir`; callers must choose the output location. The manager must not invent a default path. Before writing a package, it refreshes the draft modified state, revalidates the draft plugin manifest with the original `plugin_id` and `base_version`, confirms the requested `skill_id` is still present, and rejects symlinks in the draft tree, the output directory, or a preexisting package path. The output directory must not be inside the draft tree or under the disallowed memory, import, export, or Claude memory data roots.

Draft packages for Cowork use the original draft plugin root as a flat ZIP root. Valid entries look like:

```text
.claude-plugin/plugin.json
skills/<skill_id>/SKILL.md
contracts/<plugin_id>.contract.json
```

The ZIP must not contain a wrapper directory, absolute paths, or `..` traversal entries. The manifest inside the package preserves the original plugin name and version; package creation must not use runtime adapter identities such as `aiws-generated-plugin`.

Draft activation and handoff status for the Cowork slice is explicit and intentionally narrow:

| State | Meaning | Runtime effect |
|---|---|---|
| absent | No draft activation record exists; the draft is inactive for that host. | None |
| `pending_upload` | A modified draft package was prepared for manual Cowork upload. | Management/status only; it must not change skill resolution. |
| `handoff_prepared` | A handoff status layered on top of `pending_upload`: a modified draft package was copied to a Cowork package-upload surface, but Cowork has not confirmed activation. | Management/status only; it must not change skill resolution or claim activation. |

`active` runtime overlays and `deactivated` tombstones are out of scope for this Cowork slice. Deactivation removes the pending record; absence again means inactive.

`activate_draft` in Phase 2 Slice 3A supports only `host_kind='cowork'`. `package_output_dir` remains required and explicit. The runtime adapter resolves or registers the concrete `host_id` before calling the low-level skill manager; if a caller supplies `host_id`, it must match the registered host identity for that `host_kind`. Before building a package or writing pending state, activation must reload the draft record, re-derive the canonical draft identity from the record's `plugin_id`, `skill_id`, and `origin_repo`, reject any mismatch with the requested `draft_id`, and re-check that the stored draft path is the expected path under `~/.aiws/plugins/`.

If the draft is unchanged after refresh, activation returns `not_modified` with no actions and does not create a package or pending record. If the draft is modified, activation rebuilds the Cowork package and records `pending_upload` under `~/.aiws/state/draft-activations/<host-id>/<draft_id>.json`. If no safe Cowork package-upload surface is available, it returns `host_capability_missing` with one non-terminal `package_upload` action pointing at the ZIP for manual Cowork upload. If a safe Cowork package-upload surface is available, it may copy the package there and return `handoff_prepared` with one non-terminal `cowork_package_handoff` action. `handoff_prepared` is not `active`; it still requires Cowork confirmation in a new chat or through another supported Cowork visibility/callability check before activation can be claimed. The activation metadata root, host directory, final record path, temporary write path, package-upload root, and copied package path must all be checked for path traversal and symlink escape before write or delete. Existing copied package files may be reused only when their bytes match the prepared package; different existing content must fail closed. The record file name is the canonical `draft_id`, not just `plugin_id + skill_id`, so multiple marketplaces or source repositories with the same plugin and skill names do not collide. Writes must be atomic replace operations. The pending record is visible only through management/status responses; it must not affect `resolve`, `get`, `search`, `list_local`, or runtime skill content. This slice must not mutate Cowork runtime state, RPM files, installed marketplace or organization plugin files, `~/.claude`, proposal records, GitHub state, AIWS host registry paths, or memory/import/export paths.

`deactivate_draft` is pending-upload cancellation, not proof that anything was removed from Cowork. It clears only the pending activation record for the supplied `draft_id` and host. It must verify that the pending record's stored `draft_id` exactly matches the requested draft before deleting it; plugin and skill identity alone are not sufficient. It must not clear draft `modified` state, bypass update-conflict handling for modified drafts, delete user-chosen package artifacts, restore or mutate an installed marketplace package, remove anything from Cowork, edit proposal records, or touch GitHub. If the package was manually uploaded to Cowork, removing it remains a Cowork UI action.

`revert_draft` is draft cleanup, not Cowork runtime cleanup. It removes the specific draft worktree under `~/.aiws/plugins/` and its matching draft record under `~/.aiws/state/skill-drafts/`. It must reject non-canonical record IDs, unexpected draft paths, symlinks, path traversal, and any path outside AIWS draft roots. It must not remove installed plugins, Cowork RPM/runtime files, packages, proposal records, GitHub branches or PRs, `~/.claude`, or memory data.

## Draft Registry

Editable files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>
```

`marketplace-slug` and `plugin-id` are slug-normalized with the same `slug()` behavior used by `aiws-mcp/aiws_mcp/skill_manager.py`. `origin-repo-sha10` is `sha256(origin_repo)[:10]`. The path suffix prevents collisions between plugins with the same ID from different origin repositories. It is storage identity only; the user-facing skill identity remains `plugin_id + skill_id`, and the suffix must not create duplicate visible skills.

The authoritative state lives under:

```text
~/.aiws/state/skill-drafts/
```

Each draft record must include:

```text
plugin_id
skill_id
origin_marketplace
origin_repo
origin_ref
base_version
base_commit
draft_path
base_tree_digest
current_tree_digest
active
modified
publish_target
branch_name
pr_url
last_validation_status
last_validation_tree_digest
updated_at
```

`base_tree_digest` is captured when the draft is created and is the immutable comparison point for local modified-state tracking. `current_tree_digest` is refreshed by explicit status refresh and by validation-gated operations such as package build, activation, and proposal staging. The digest covers sorted relative paths and file bytes so content changes, additions, and deletions are detected. Refresh must fail closed on symlinks or path escapes and must update only the draft registry record; it must not overwrite draft files or source plugin files.

Validation success persists `last_validation_status='passed'` and `last_validation_tree_digest=<current_tree_digest>`. Validation failure persists `last_validation_status='failed'` and clears `last_validation_tree_digest`.

## Proposal Registry

Staged proposal records live under:

```text
~/.aiws/state/skill-proposals/
```

Each proposal record must use canonical `draft_id` rather than `record_id` and include:

```text
proposal_id
draft_id
plugin_id
skill_id
origin_marketplace
origin_repo
origin_ref
base_version
base_commit
draft_path
base_tree_digest
current_tree_digest
validation_status
validation_tree_digest
target_scope
target_repo
summary
rationale
active
modified
status
branch_name
pr_url
created_at
updated_at
```

Proposal files must be created with collision-safe IDs and must never overwrite an existing proposal file. Proposal state roots, final paths, and temporary paths must fail closed on symlinks.

A staged proposal submitted for review moves from `status='staged'` to `status='submitted_for_review'` only after the submitter returns nonblank `branch_name` and `pr_url`. Successful submission also adds `submitted_at` to the proposal record. Explicitly supplied product-specific `required_review_roles` may be persisted, but the normal Cowork flow omits role metadata. If submission fails or returns invalid metadata, local proposal state remains staged and retryable. If an already submitted proposal has complete metadata, submit returns that existing result without calling the submitter again. If submitted metadata is incomplete, submit fails closed.

When a modified draft or pending Cowork upload exists, update from GitHub must fail closed and offer only:

```text
keep_local_draft_and_pending_package
discard_local_changes_and_update
submit_or_upload_first
```

## Skill Compatibility

Managed skills must remain compatible with Codex `skill-creator` rules:

- skill folder name matches `SKILL.md` frontmatter `name`
- names use lowercase letters, digits, and single hyphens
- frontmatter contains only `name` and `description`
- description carries trigger/use-case language
- resources use `scripts/`, `references/`, and `assets/`
- skill folders do not contain clutter files such as `README.md`, `CHANGELOG.md`, install guides, or quick references

## GitHub Policy

Users edit and test first, then stage a proposal with `target_scope` and `target_repo`. A later explicit submit-for-review action submits the staged proposal and may create or update a pull request. Direct push is not part of the normal user flow.

GitHub auth is delegated to the authenticated user, Cowork organization connection, or configured organization bot/App. Users must not paste tokens into chat.

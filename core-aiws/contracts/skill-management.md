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
create_or_open_draft(plugin_id, skill_id, origin_repo, origin_marketplace, base_ref)
refresh_modified_status(draft_id)
build_draft_package(draft_id, package_output_dir)
activate_draft(draft_id, host_kind, package_output_dir)
update_from_github(plugin_id, marketplace_id)
stage_proposal(draft_id, target_scope, target_repo, summary, rationale)
submit_pr(draft_id, target_repo)
revert_draft(draft_id)
```

`stage_proposal` writes a local proposal record only, under `~/.aiws/state/skill-proposals/`. It records the draft, target scope, target review repository, summary, rationale, provenance, and validation status for later review. `target_scope` is the Cowork/user-facing label and policy scope. `target_repo` is the concrete backend review repository persisted for a later submit-for-review action. Staging must not upload, submit, create a pull request, or push changes; `submit_pr` or another explicit submit-for-review operation is follow-on behavior. Package export or upload is an admin/deployment fallback, not the normal user staging path.

`build_draft_package` requires an explicit `package_output_dir`; callers must choose the output location. The manager must not invent a default path. Before writing a package, it refreshes the draft modified state, revalidates the draft plugin manifest with the original `plugin_id` and `base_version`, confirms the requested `skill_id` is still present, and rejects symlinks in the draft tree, the output directory, or a preexisting package path. The output directory must not be inside the draft tree or under the disallowed memory, import, export, or Claude memory data roots.

Draft packages for Cowork use the original draft plugin root as a flat ZIP root. Valid entries look like:

```text
.claude-plugin/plugin.json
skills/<skill_id>/SKILL.md
contracts/<plugin_id>.contract.json
```

The ZIP must not contain a wrapper directory, absolute paths, or `..` traversal entries. The manifest inside the package preserves the original plugin name and version; package creation must not use runtime adapter identities such as `aiws-generated-plugin`.

`activate_draft` in Phase 2 Slice 3A supports only `host_kind='cowork'`. If the draft is unchanged after refresh, it returns `not_modified` with no actions and does not create a package. If the draft is modified, it builds the Cowork package and returns `host_capability_missing` with one non-terminal `package_upload` action pointing at the ZIP for manual Cowork upload. This slice must not mutate Cowork runtime state, RPM files, `~/.claude`, AIWS host registry paths, or memory/import/export paths.

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

When an active modified draft exists, update from GitHub must fail closed and offer only:

```text
keep_local_modified_skill_active
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

Users edit and test first, then stage a proposal with `target_scope` and `target_repo`. A later explicit submit-for-review action may create or update a pull request. Direct push is not part of the normal user flow.

GitHub auth is delegated to the authenticated user, Cowork organization connection, or configured organization bot/App. Users must not paste tokens into chat.

# Skill Management Contract

`core-aiws` owns the AIWS skill-management workflow for Cowork-facing install, update, edit, test, and upload operations. Users install `core-aiws`; they do not install a separate skill-manager plugin.

## Local Manager Boundary

The skill manager is an internal `core-aiws` tool bridge. It may validate plugins, create editable drafts, build draft packages, activate draft packages, update from GitHub, submit pull requests, and revert drafts.

The bridge must expose no memory tools, must not run memory import or export flows, and must not touch memory paths.

Allowed write roots:

```text
~/.aiws/plugins/
~/.aiws/state/skill-drafts/
temporary package build output
```

Disallowed write roots:

```text
~/.aiws/memory/
~/.aiws/imports/
~/.aiws/exports/
~/.claude/plugins/data/*memory*
```

## Operations

The bridge exposes a closed operation surface:

```text
validate_plugin(source_or_package)
create_or_open_draft(plugin_id, skill_id, origin_repo, origin_marketplace, base_ref)
build_draft_package(draft_id)
activate_draft(draft_id)
update_from_github(plugin_id, marketplace_id)
submit_pr(draft_id, target_repo)
revert_draft(draft_id)
```

`activate_draft` uses the reinstall-draft strategy: build a package under the same plugin identity and replace the active user-level plugin package through the supported host/plugin install path. If the host cannot activate the draft programmatically, it must return `host_capability_missing` with one non-terminal package-upload action.

## Draft Registry

Editable files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>
```

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
active
modified
publish_target
branch_name
pr_url
last_validation_status
updated_at
```

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

Users edit and test first, then choose an upload target. Upload creates a pull request by default. Direct push is not part of the normal user flow.

GitHub auth is delegated to the authenticated user, Cowork organization connection, or configured organization bot/App. Users must not paste tokens into chat.

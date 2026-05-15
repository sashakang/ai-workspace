# Skill Management Protocol

Use this protocol when a user wants to install, update, edit, test, or upload an AIWS skill in Cowork.

## User-Facing Rules

- Do not ask normal users to run bash commands.
- Do not expose Git terms unless the user asks for advanced details.
- Show one skill identity. If a draft is modified, present it as `Modified locally`; if a Cowork package has been prepared, present it as `Modified locally, pending Cowork upload`.
- Keep memory import out of scope.

## Install Or Update

For a public marketplace, use the Cowork Personal marketplace flow. For a private or organization marketplace, use the Cowork Organization GitHub sync flow.

Before activation, run the release validation gate:

- validate marketplace and plugin manifests
- validate contracts
- validate every `.mcp.json`
- validate every skill folder against Codex `skill-creator` compatibility rules
- fail on marketplace/plugin/contract version drift
- reject `.mcp.json` files with top-level `servers`

If a modified draft or pending Cowork upload exists, do not silently update. Offer only:

```text
keep local draft and pending package
discard local changes and update
submit/upload first
```

## Edit And Test

Create or open a draft through the internal `core-aiws` skill-manager bridge. Store editable files under `~/.aiws/plugins/` and durable state under `~/.aiws/state/skill-drafts/`.

After a draft is opened, keep using its `draft_id`. Do not run a fresh draft-open flow during edit, validation, staging, or submit unless you are intentionally reopening the same draft. If an active draft already exists for the same plugin and skill, creating a second draft for a different target must fail closed unless the caller explicitly chooses an advanced parallel-draft override.

Use the draft file operations for Cowork-facing edits:

```text
list_draft_files(draft_id)
read_draft_file(draft_id, relative_path)
write_draft_file(draft_id, relative_path, content)
delete_draft_file(draft_id, relative_path)
```

For this phase, draft edits are limited to text files under `skills/<skill_id>/` for the selected skill. Do not edit plugin manifests, contracts, memory files, installed source packages, or Cowork/Claude runtime state through these operations.

After edit, build and activate a draft package under the same plugin identity. The edited skill becomes the active version in the UI and runtime. If programmatic activation is unavailable, provide one package upload action and report the host capability gap.

## Stage And Submit

When the user wants to propose an improvement, first stage the proposal through the internal `core-aiws` skill-manager bridge. Ask for the target in product language and resolve it to a concrete backend review repository:

```text
Personal
Unit/project
Company
Public
```

Call `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)`. `target_scope` is the Cowork/user-facing label and policy scope. `target_repo` is the concrete repository to use later for maintainer review. Staging revalidates the current draft tree, records the validation digest, writes a local proposal record under `~/.aiws/state/skill-proposals/`, and must not create a branch, commit, push, upload, or open a pull request.

This phase supports skill-folder-only proposals. If the draft contains changes outside `skills/<skill_id>/`, require the user to revert or split those changes before staging.

Only after the user explicitly chooses submit-for-review may the backend call `submit_pr(proposal_id, submitter)`. Submission uses the staged proposal's stored `target_repo`; do not accept a fresh repository value at submit time. The submitter must use deterministic branch identity `aiws/skill-proposals/<proposal_id>` and create or update one review item for retry safety. Normal Cowork submission must not invent reviewer-role metadata or ask the user to map roles to GitHub users. If Cowork has no working GitHub submit adapter, return a non-terminal `submit_handoff_required` result after the normal submit gates pass; do not mark the proposal submitted or write branch/PR metadata. GitHub-side repository policy owns actual reviewer assignment, review, and merge. If permission is missing, offer only non-terminal fallbacks: request access, personal/fork PR path, or admin package export.

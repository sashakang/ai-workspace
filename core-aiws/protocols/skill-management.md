# Skill Management Protocol

Use this protocol when a user wants to install, update, edit, test, or upload an AIWS skill in Cowork.

## User-Facing Rules

- Do not ask normal users to run bash commands.
- Do not expose Git terms unless the user asks for advanced details.
- Show one skill identity. If a modified draft is active, present it as `Modified locally`, not as a second skill.
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

If an active modified draft exists, do not silently update. Offer only:

```text
keep local modified skill active
discard local changes and update
submit/upload first
```

## Edit And Test

Create or open a draft through the internal `core-aiws` skill-manager bridge. Store editable files under `~/.aiws/plugins/` and durable state under `~/.aiws/state/skill-drafts/`.

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

Only after the user explicitly chooses submit-for-review may the backend create or update a pull request using the staged proposal's `target_repo` and the available GitHub identity or organization bot/App. If permission is missing, offer only non-terminal fallbacks: request access, personal/fork PR path, or admin package export.

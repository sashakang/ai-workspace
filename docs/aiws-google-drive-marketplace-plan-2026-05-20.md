# Google Drive Backend For Shared AIWS Marketplaces

## Summary

Use **Google Drive**, not Confluence, as the temporary non-GitHub backend for additional AIWS marketplaces.

This is a **peer backend, fallback-first** design:

- infrastructure plugins stay on the current GitHub/public path
- domain plugins may still live in `sashakang/ai-workspace` or other GitHub repos where that works
- Google Drive is added for governed shared scopes:
  - `company`
  - `unit:<id>`
  - `project:<id>`

The main simplification is the visibility model:

- **one marketplace = one Google Drive root folder**
- that root folder defines **one uniform visibility model**
- everything inside that marketplace shares the same visibility
- if visibility must differ, that is a **different marketplace**, not a different plugin ACL inside the same marketplace

## Implementation Changes

### Identity and backend model

Normalize marketplace identity around four fields:

- `scope_id`: `company | unit:<id> | project:<id>`
- `marketplace_id`
- `backend_kind`: `github | google_drive`
- `backend_ref`
  - GitHub: `owner/repo`
  - Drive: marketplace root folder ID

Canonical plugin variant identity is:

- `(marketplace_id, plugin_id)`

Backend-of-record is pinned per that key:

- value: exactly one `backend_kind + backend_ref`

No dual-write and no live mirroring between GitHub and Drive in v1.

`marketplace_id` rules:

- `marketplace_id` is a globally unique stable slug minted or validated by AIWS at marketplace registration time
- uniqueness is checked in one canonical AIWS marketplace registry across all scopes and backends
- duplicate marketplace registration fails closed
- `marketplace_id` is immutable after creation
- `marketplace_id` is not derived from mutable folder names or display names
- changing scope or folder name does not change `marketplace_id`
- rename is not an in-place edit; after first publication it is either forbidden or treated as a new marketplace plus explicit migration

Because a scope may have multiple marketplaces:

- every **write path** must carry `marketplace_id`
- every **read path that resolves a concrete plugin variant** must carry `marketplace_id`, or fail closed if more than one visible marketplace matches
- no implicit first-match resolution

### Drive storage shape

Each Drive-backed marketplace uses this root layout:

```text
<marketplace-root>/
  marketplace.json
  plugins/
    <plugin_id>/
      index.json
      proposals/
        in_review/
          <proposal_id>/
        approved/
        rejected/
        released/
      packages/
        <version>/
          <plugin_id>-<version>.zip
          release.json
      locks/
```

Rules:

- `marketplace.json` contains marketplace-level metadata only
- all plugin-owned state lives under `plugins/<plugin_id>/...`
- hosts discover plugins from the visible marketplace root and its plugin folders
- local caches, locks, and materialization records must be keyed by `(marketplace_id, plugin_id)`

### Proposal packet and review flow

Each proposal folder contains:

- `base.SKILL.md` - immutable base snapshot
- `proposed.SKILL.md` - candidate release artifact
- `proposal.json` - canonical machine state

Rules:

- `base.SKILL.md` is a read-only snapshot of the currently published skill
- reviewers may update only `proposed.SKILL.md`
- AIWS owns `proposal.json`
- AIWS publishes from `proposed.SKILL.md`
- there is no separate Google Doc review surface in v1
- review happens in Google Drive / Google Docs UI by comparing the two Markdown files
- frontmatter, versioning, package assembly, and plugin metadata stay AIWS-owned

Flow:

1. local draft is edited and validated
2. `stage_proposal(..., scope_id=..., marketplace_id=..., backend_kind="google_drive")`
3. `submit_for_review(proposal_id)` creates the proposal packet under `plugins/<plugin_id>/proposals/in_review/<proposal_id>/`
4. reviewers compare `base.SKILL.md` and `proposed.SKILL.md` in the Drive/Docs UI and adjust `proposed.SKILL.md` if needed
5. approval is moving the **same proposal folder ID** to the known `approved` parent folder
6. a marketplace editor runs `publish_approved_proposal(proposal_id)`

### Approval, publish, and failure rules

Approval rules:

- approval is detected only when the **same proposal folder ID** changes parent to the known `approved` folder ID
- copying, renaming, duplicating, or recreating a folder does not count
- approval pins the exact approved `proposed.SKILL.md` file revision and content hash
- if `proposed.SKILL.md` changes after approval, AIWS marks the proposal `needs_reapproval`, moves it back to `in_review`, and requires a new approval move

Canonical proposal states:

- `submitted_for_review`
- `approved_pending_publish`
- `needs_reapproval`
- `publishing`
- `released`
- `rejected`

Add two backend operations:

- `refresh_proposal_state(proposal_id)`  
  Reconciles Drive signals into canonical state. Does not publish.

- `publish_approved_proposal(proposal_id)`  
  Marketplace-editor action. Uses the pinned approved `proposed.SKILL.md` exactly, validates, patch-bumps, builds ZIP, uploads package, writes `release.json`, updates `index.json`, and moves the proposal to `released`

Publish safety rules:

- plugin-level release lock per `(marketplace_id, plugin_id)`
- stale-base check before version bump
- idempotent release attempt key per publish attempt
- if publish fails, AIWS records failure, moves the same proposal back to `in_review`, sets `needs_reapproval`, and does **not** allow in-place retry without re-approval
- no hidden autonomous publisher; explicit publish is required

### Authority and host contract

Auth model stays **per-user OAuth**.

V1 authority model is simple:

- any user who has **marketplace edit authority** may review and publish
- there is no separate reviewer/publisher split in v1

That matches the uniform marketplace visibility model and avoids inventing a second permission system too early.

Hosts consume only published artifacts:

- `index.json`
- ZIP package
- `release.json`

Hosts do not depend on proposal folders or Google Docs internals.

Behavior by host:

- `Cowork`: stays on its current package/update boundary
- `Claude Code` and `Codex`: resolve `(marketplace_id, plugin_id)`, download ZIP, validate, materialize through existing AIWS adapter rules

## Test Plan

- GitHub-backed marketplaces continue unchanged.
- Drive backend works for `company`, `unit:<id>`, and `project:<id>`.
- Multiple marketplaces in one scope require explicit `marketplace_id`, or fail closed.
- Marketplace visibility is uniform per marketplace root folder.
- Proposal creation writes `base.SKILL.md`, `proposed.SKILL.md`, and `proposal.json` into the correct plugin subtree.
- Approval works only for the original proposal folder ID moving to the known approved parent.
- Approval pins a `proposed.SKILL.md` revision and content hash; post-approval file edits force `needs_reapproval`.
- Publish requires `approved_pending_publish`.
- Publish uses the pinned approved `proposed.SKILL.md`, not whatever exists later.
- Publish is lock-protected, stale-base-protected, and idempotent.
- Failed publish returns the proposal to `in_review` with `needs_reapproval`.
- Code, Codex, and Cowork can all consume the same published Drive-backed package model.

## Assumptions and defaults

- Google Drive is the chosen temporary non-GitHub backend; Confluence is rejected for v1.
- Infrastructure plugins stay where they are now.
- Domain plugins may still use GitHub where appropriate.
- `project:<id>` is first-class.
- A scope may have multiple marketplaces.
- One marketplace is one Drive root folder and one visibility boundary.
- Version bump rule is always `patch`.
- V1 uses explicit publish, not autonomous publish.
- V1 uses marketplace-edit authority for publish; no separate reviewer/publisher role split yet.

# Executive Summary — Google Drive Backend For Shared AIWS Marketplaces

## Decision

Use **Google Drive**, not Confluence, as the temporary non-GitHub backend for additional shared AIWS marketplaces.

This does not replace GitHub everywhere. It adds a second backend for cases where GitHub is blocked or not ready.

## What stays the same

- Infrastructure plugins stay on the current GitHub/public path.
- Domain plugins may still live in `sashakang/ai-workspace` or other GitHub repos where that works.
- Cowork, Claude Code, and Codex remain first-class hosts.

## What changes

Google Drive becomes a supported backend for shared marketplaces in these scopes:

- `company`
- `unit:<id>`
- `project:<id>`

A scope may contain several marketplaces.

Each Drive-backed marketplace is one Google Drive root folder.

That folder is the visibility boundary:

- everything inside it has the same visibility
- if a plugin needs different visibility, it goes into a different marketplace folder

## Core operating model

- one concrete plugin variant is identified by `(marketplace_id, plugin_id)`
- `marketplace_id` is a globally unique immutable AIWS-issued or AIWS-validated ID
- backend-of-record is pinned per variant: GitHub or Google Drive, not both
- all writes and concrete-plugin lookups must carry `marketplace_id`
- no implicit “pick the first marketplace” behavior

## Review and release flow

Each proposal contains:

- `base.SKILL.md`
- `proposed.SKILL.md`
- `proposal.json`

There is no separate Google Doc review artifact in v1.

Review happens in the Drive/Docs UI by comparing the two Markdown files. Reviewers may adjust `proposed.SKILL.md`.

Approval works like this:

- the same proposal folder is moved to the known `approved` folder
- approval pins the exact `proposed.SKILL.md` revision and content hash
- if `proposed.SKILL.md` changes later, approval is invalidated and re-approval is required

Release works like this:

- release is explicit, not automatic
- any user with marketplace edit authority may publish in v1
- AIWS validates, patch-bumps, builds the ZIP, updates package metadata, and records the release

## Safety rules

- plugin-level release lock per `(marketplace_id, plugin_id)`
- stale-base check before version bump
- idempotent publish attempt key
- failed publish returns the proposal to `in_review` with `needs_reapproval`
- no hidden background publisher

## Why Google Drive over Confluence

Google Drive can act as:

- file store for Markdown proposals
- metadata store
- package store

Confluence is acceptable as a discussion surface, but it is the wrong shape for package files and release metadata. It would likely force a second storage system anyway.

## Practical implication

This gives AIWS a host-agnostic shared-marketplace backend that works without forcing all non-public shared plugin work into GitHub immediately, while keeping the model simple enough to implement safely.

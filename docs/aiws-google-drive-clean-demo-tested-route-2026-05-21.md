# AIWS Google Drive Clean Demo Tested Route

**Date:** 2026-05-22  
**Status:** PASS  
**Primary manual:** [AIWS Google Drive Clean User Demo Manual](./aiws-google-drive-clean-user-demo-manual-2026-05-21.md)

This report captures what was actually proven in Cowork for the clean Google Drive marketplace route.

## Names And IDs

| Concept | Value |
|---|---|
| Infrastructure repo | `sashakang/ai-workspace` |
| Infrastructure marketplace | `ai-workspace` |
| Infrastructure plugin | `core-aiws` |
| Verified infrastructure version | `0.3.46` |
| Drive marketplace display name | Checkout Main |
| Drive marketplace_id | `checkout-main` |
| Drive folder id | `1P3Cd5DBaz_bxhxh3MQnb_sBEx6eKQi3Z` |
| Domain plugin display name | Productivity |
| Domain plugin_id | `productivity` |
| Skill display name | Meeting Follow-up |
| Skill id | `meeting-followup` |
| Initial published version | `0.2.3` |
| Published update version | `0.2.4` |

Use `AIWS` only for infrastructure. The Drive demo domain plugin is `Productivity`, not `AIWS Productivity`.

## Verified Flow

1. Created a clean Google Drive marketplace without mutating the old `checkout-main-real` folder.
2. Published initial `productivity:meeting-followup` version `0.2.3`.
3. Registered `checkout-main` as a Google Drive AIWS marketplace.
4. Verified `aiws.marketplaces.drive_workflow` shows Checkout Main / Productivity / Meeting Follow-up.
   - `workflow_schema_version: 1`
   - `cowork_native_visible: false`
   - `current_skill` points directly to Productivity / Meeting Follow-up when the filtered view has one skill.
   - `next_action_detail` carries the full recommended action payload without scanning the full actions list.
   - `plugin_id` and `skill_id` filters can target Productivity / Meeting Follow-up directly.
   - `selection_status` and `selected_skill_count` distinguish a filtered hit from an empty workflow view.
   - per-skill `actions` include materialize, draft, validate, stage, submit, refresh, publish, cleanup preview, and core update status checks.
5. Resolved and materialized `meeting-followup` from `marketplace_id: checkout-main`.
6. Opened a draft without supplying `source_plugin_root`.
7. Rejected stale draft metadata from the old `cowork-upload` route.
8. Validated identity guards:
   - expected `productivity` passes
   - expected `aiws-productivity` fails
9. Edited only `skills/meeting-followup/SKILL.md`.
10. Staged a Google Drive proposal to `checkout-main`.
11. Rejected staging to wrong marketplace `checkout-main-real`.
12. Submitted the proposal for Drive review.
13. Moved the Drive proposal folder to `approved`.
14. Published version `0.2.4`.
15. Pulled the update from a fresh resolve/materialize path.

## Key Evidence

Published proposal:

```text
proposal_id: skillprop_0bf4544349974a2a83b6a958b281122a
draft_id: productivity--meeting-followup--a345febbc8
marketplace_id: checkout-main
plugin_id: productivity
skill_id: meeting-followup
published_version: 0.2.4
package_file_id: 1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT
release_file_id: 1LsAdsP_Xbtfx06zP5UG_O9BDYtQNk6za
index_file_id: 1TcIrus0FyUAshBVCvlZnaQvYPZLWLNao
```

Final pull-update verification:

```text
resolve marketplace_id: checkout-main
resolve plugin_id: productivity
resolve skill_id: meeting-followup
resolve version: 0.2.4
resolve source: google-drive:checkout-main:productivity:1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT

materialize marketplace_id: checkout-main
materialize plugin_id: productivity
materialize skill_id: meeting-followup
materialize version: 0.2.4
materialize source: google-drive:checkout-main:productivity:1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT
plugin_cache_path: ~/.aiws/hosts/<host>/shared-cache/plugins/checkout-main/productivity/0.2.4
```

## Bugs Found And Fixed

### 1. Drive Materialization Lost Plugin Identity

Problem: materialized Drive packages could create an `aiws-generated-plugin` style root instead of preserving `plugin_id: productivity`.

Fix: materialization now writes a valid plugin cache root under:

```text
~/.aiws/hosts/<host>/shared-cache/plugins/checkout-main/productivity/<version>
```

### 2. Draft Creation Needed Manual Scaffold

Problem: `create_or_open_draft` could not open a Drive marketplace draft from materialized cache without a manually supplied `source_plugin_root`.

Fix: draft creation can now find the materialized Drive plugin root by `marketplace_id + plugin_id + skill_id`.

### 3. Stale Drafts Reopened Silently

Problem: an old dirty draft with matching canonical id could reopen even if its source metadata was `cowork-upload` / `uploaded`.

Fix: existing draft source identity must match requested source identity. Mismatches fail with a clear error.

### 4. Resolver Preferred Stale Cache Over Current Drive Index

Problem: after publishing `0.2.4`, resolve/materialize still returned cached `0.2.3`.

Fix: when `marketplace_id` is supplied and no explicit version is pinned, resolver prefers the current Google Drive published record over stale materialized cache.

### 5. Scope Display Produced Duplicate Rows

Problem: workflow display showed duplicate rows for the same version because filesystem-safe cache path used `project_checkout-main` while the registry scope was `project:checkout-main`.

Fix: materialized records now use canonical scope from `.aiws-skill-manifest.json`, and workflow/search display dedupes same-version Drive/cache rows while preserving `materialized: true`.

## Current Expected Display

After the complete run, `aiws.marketplaces.drive_workflow` may show both:

```text
Meeting Follow-up 0.2.3 materialized true
Meeting Follow-up 0.2.4 materialized true
```

This is expected version history, not the duplicate-scope bug. The default workflow payload no longer shows scope; `include_debug: true` exposes the legacy canonical scope when diagnostics need it:

```text
project:checkout-main
```

For a clean demo view, call `aiws.marketplaces.drive_workflow` with `latest_only: true`. It should show only:

```text
Meeting Follow-up 0.2.4 materialized true
scope: absent from the default workflow payload
```

## Not Proven / Follow-Up

- Cowork native UI still does not render AIWS Drive marketplaces as first-class marketplace entries.
- `core-aiws` cannot update itself from inside its own MCP runtime; use `aiws.runtime.update_status` for exact native Cowork Directory update instructions.
- Old Drive package deletion is intentionally not part of the demo path.
- Maintenance cleanup is available through guarded `aiws.marketplaces.delete_artifact`.
- Scopes remain as debug/internal storage until the compatibility migration is complete.

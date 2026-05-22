# AIWS Google Drive Clean User Demo Manual

**Date:** 2026-05-22  
**Status:** Verified end to end  
**Purpose:** Demonstrate the clean Google Drive marketplace path for a demo domain skill while keeping AIWS infrastructure in the original GitHub marketplace.

## Verified Route

| Layer | Value |
|---|---|
| Infrastructure marketplace | `ai-workspace` |
| Infrastructure source | `sashakang/ai-workspace@master` |
| Required infrastructure plugin | `core-aiws` |
| Verified infrastructure version | `0.3.40` |
| Drive marketplace display name | Checkout Main |
| Drive marketplace_id | `checkout-main` |
| Drive backend_ref | `1P3Cd5DBaz_bxhxh3MQnb_sBEx6eKQi3Z` |
| Drive scope_id | `project:checkout-main` |
| Demo domain plugin display name | Productivity |
| Demo domain plugin_id | `productivity` |
| Demo skill display name | Meeting Follow-up |
| Demo skill_id | `meeting-followup` |
| Starting Drive version | `0.2.3` |
| Published update version | `0.2.4` |
| Published package file_id | `1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT` |

Use `AIWS` only for the infrastructure/platform. The Google Drive demo domain plugin is `Productivity`, not `AIWS Productivity`.

## Important Boundaries

- Do not use ZIP upload as the normal user path.
- Do not use Cowork Directory install for the Google Drive `productivity` domain plugin.
- Do not use RPM, `cowork-upload`, GitHub PR flow, or direct installed-plugin edits for the Drive demo path.
- `aiws.host.install` does not update `core-aiws`; it only packages the generated Cowork adapter.
- Updating `core-aiws` currently requires Cowork's native plugin Directory / marketplace UI and a new Cowork task.
- AIWS Drive marketplace skills do not appear in Cowork's native plugin sidebar yet; use AIWS tools to browse, materialize, draft, validate, stage, and publish them.
- Old materialized versions can remain visible as version history. This is not the duplicate scope-row bug.

## Success Criteria

The demo passes only if:

1. `core-aiws` runs at `0.3.40` or newer.
2. `aiws.marketplaces.drive_workflow` shows `checkout-main`.
3. `meeting-followup` resolves from `marketplace_id: checkout-main` with `plugin_id: productivity`.
4. Materialization creates AIWS cache paths under `~/.aiws/.../shared-cache/...`, not Cowork hostloop temp paths.
5. Draft creation works without `source_plugin_root`.
6. Validation rejects wrong expected identity.
7. Google Drive proposal staging accepts `checkout-main` and rejects a wrong marketplace.
8. Submit, approve, publish, then pull-update returns version `0.2.4`.

## Phase 0: Update Infrastructure

Run this before testing new infrastructure behavior.

```text
Use Cowork native plugin marketplace tools or the Cowork Directory UI.

Find the installed plugin core-aiws@ai-workspace.
Update or reinstall that native plugin from marketplace ai-workspace.
Do not call aiws.host.install.
Do not build or stage aiws-generated-plugin.zip.

After the native plugin update completes, start a new Cowork task/session and call aiws.runtime.info.
Report plugin_version and declared_tools count.
```

Expected:

```text
plugin_version: 0.3.40
declared_tools count: 39
```

If `plugin_version` is older, stop. The current session is still running old MCP code.

If there is confusion about how to update infrastructure, run:

```text
Call aiws.runtime.update_status. Report installed_version, marketplace_latest_version, update_available, can_self_update, not_an_update_method, and required_action.
```

Expected:

```text
can_self_update: false
not_an_update_method: aiws.host.install only packages generated adapter skills; it does not update core-aiws.
required_action: Update or reinstall core-aiws@ai-workspace in Cowork's native Directory, then start a new Cowork task/session.
```

## Phase 1: Browse The Drive Marketplace

```text
Call aiws.marketplaces.drive_workflow with marketplace_id: checkout-main and host_kind: cowork.
Report the Checkout Main marketplace, Productivity plugin, Meeting Follow-up skill rows, versions, scopes, and materialized status.
```

Expected:

```text
marketplace_id: checkout-main
plugin_id: productivity
skill_id: meeting-followup
scope: project:checkout-main
workflow_schema_version: 1
cowork_native_visible: false
actions include: materialize_skill, open_draft, validate_draft, stage_proposal, submit_for_review, refresh_proposal_state, publish_approved_proposal, delete_old_artifact_dry_run, check_core_update_status
```

One row for `0.2.4` with `materialized: true` is expected after the full demo. Older versions such as `0.2.3` may also be visible as materialized history.

For a clean demo view, hide version history:

```text
Call aiws.marketplaces.drive_workflow with marketplace_id: checkout-main, host_kind: cowork, latest_only: true.
Report the Productivity / Meeting Follow-up rows only.
```

Expected after the full demo:

```text
Meeting Follow-up 0.2.4 materialized true
scope: project:checkout-main
```

## Phase 2: Resolve And Materialize

```text
Call aiws.skills.resolve with skill_id: meeting-followup, marketplace_id: checkout-main, host_kind: cowork.

Then call aiws.skills.materialize with skill_id: meeting-followup, marketplace_id: checkout-main, host_kind: cowork.

Report only:
resolve marketplace_id, plugin_id, skill_id, version, source
materialize marketplace_id, plugin_id, skill_id, version, source, cache_path, plugin_cache_path
```

Expected after publish:

```text
marketplace_id: checkout-main
plugin_id: productivity
skill_id: meeting-followup
version: 0.2.4
source: google-drive:checkout-main:productivity:1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT
plugin_cache_path: ~/.aiws/hosts/<host>/shared-cache/plugins/checkout-main/productivity/0.2.4
```

Do not infer these fields from skill output. Use raw AIWS resolve/materialize manifests.

## Phase 3: Use The Skill

```text
Use Meeting Follow-up from the Checkout Main Google Drive marketplace on these notes:

Decision: Start the clean Google Drive marketplace demo.
Alex will verify the Productivity skill was installed from Checkout Main.
Open question: whether the user can modify and propose an update next.

Report first output line and whether the output includes meeting minutes, decisions, action items, unresolved questions, and a draft follow-up message.
```

Expected first output line for the verified updated skill:

```text
> 📋 meeting-followup v3
```

## Phase 4: Open A Clean Draft

If an old stale draft exists, the expected guard error is:

```text
Existing draft productivity--meeting-followup--a345febbc8 has a different source identity ...
```

In that case, revert the stale draft before continuing.

```text
Create or open a draft for plugin_id: productivity, skill_id: meeting-followup, marketplace_id: checkout-main, target_repo: checkout-main.
Do not provide source_plugin_root.
Report exactly: status, record_id, plugin_id, skill_id, origin_marketplace, origin_ref, base_version, base_commit, modified.
```

Expected clean result:

```text
status: draft_opened
record_id: productivity--meeting-followup--a345febbc8
plugin_id: productivity
skill_id: meeting-followup
origin_marketplace: checkout-main
origin_ref: checkout-main
base_version: 0.2.3
base_commit: google-drive
modified: false
```

For a post-publish draft, `base_version` may be `0.2.4`.

## Phase 5: Edit And Validate

```text
Read draft file productivity--meeting-followup--a345febbc8 at relative_path: skills/meeting-followup/SKILL.md.
Append this exact line near the end of the file:

Demo validation marker: drive-clean-path-2026-05-22

Then write the file back with aiws.skills.write_draft_file.
Validate with expected_plugin_id: productivity and expected_marketplace_id: checkout-main.
Report write status, validation_status, modified, and changed files if available.
```

Expected:

```text
write status: written
validation_status: passed
modified: true
changed files: skills/meeting-followup/SKILL.md
```

Negative validation check:

```text
Validate draft productivity--meeting-followup--a345febbc8 with expected_plugin_id: aiws-productivity and expected_marketplace_id: checkout-main.
Report the full error exactly.
```

Expected:

```text
Draft plugin_id 'productivity' does not match expected plugin_id 'aiws-productivity'.
```

## Phase 6: Stage A Drive Proposal

Positive staging:

```text
Stage draft productivity--meeting-followup--a345febbc8 as a Google Drive proposal with target_scope: project:checkout-main, target_repo: null, title: Drive clean path validation, rationale: Verify clean Google Drive marketplace staging for productivity meeting-followup, backend_kind: google_drive, backend_ref: 1P3Cd5DBaz_bxhxh3MQnb_sBEx6eKQi3Z, marketplace_id: checkout-main.

Report status, proposal_id, draft_id, marketplace_id, backend_kind, backend_ref.
```

Verified result:

```text
status: staged
proposal_id: skillprop_0bf4544349974a2a83b6a958b281122a
draft_id: productivity--meeting-followup--a345febbc8
marketplace_id: checkout-main
backend_kind: google_drive
backend_ref: 1P3Cd5DBaz_bxhxh3MQnb_sBEx6eKQi3Z
```

Negative staging guard:

```text
Stage draft productivity--meeting-followup--a345febbc8 as a Google Drive proposal with target_scope: project:checkout-main-real, target_repo: null, title: Wrong marketplace validation, rationale: Verify staging rejects mismatched Google Drive marketplace, backend_kind: google_drive, backend_ref: 1hfJ3qv2p7EAnwbdVOVjnftMyshN4K1Rh, marketplace_id: checkout-main-real.

Report the full error exactly.
```

Expected:

```text
Draft origin_marketplace 'checkout-main' does not match target marketplace_id 'checkout-main-real'.
```

## Phase 7: Submit For Review

```text
Submit proposal skillprop_0bf4544349974a2a83b6a958b281122a for review.
Report status, proposal_id, draft_id, marketplace_id, backend_kind, proposal_folder_url, backend_review_state.
```

Verified result:

```text
status: submitted_for_review
marketplace_id: checkout-main
backend_kind: google_drive
backend_review_state: in_review
proposal_folder_url: https://drive.google.com/drive/folders/1T8qPNYDS6Jhg3Mpz4GwNrq_AG_CVg5aI
```

## Phase 8: Approve In Google Drive

Manual reviewer step:

1. Open the proposal folder.
2. Move the proposal folder from `in_review` to `approved` for the same plugin review area.

Then run:

```text
Refresh proposal state for proposal_id: skillprop_0bf4544349974a2a83b6a958b281122a.
Report status, backend_review_state, proposal_id, marketplace_id, approved_at, approved_proposed_skill_file_id, approved_proposed_skill_md5.
```

Verified result:

```text
status: approved_pending_publish
backend_review_state: approved
proposal_id: skillprop_0bf4544349974a2a83b6a958b281122a
marketplace_id: checkout-main
approved_proposed_skill_file_id: 1E0tDw1DCdwkF8IlwKiNIJXUuksaAt0vG
approved_proposed_skill_md5: dafa5ea872af73d5a0ad6589331aeb10
```

## Phase 9: Publish

```text
Publish approved proposal skillprop_0bf4544349974a2a83b6a958b281122a.
Report status, backend_review_state, proposal_id, marketplace_id, plugin_id, skill_id, published_version, package_file_id, release_file_id, index_file_id.
```

Verified result:

```text
status: released
backend_review_state: released
proposal_id: skillprop_0bf4544349974a2a83b6a958b281122a
marketplace_id: checkout-main
plugin_id: productivity
skill_id: meeting-followup
published_version: 0.2.4
package_file_id: 1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT
release_file_id: 1LsAdsP_Xbtfx06zP5UG_O9BDYtQNk6za
index_file_id: 1TcIrus0FyUAshBVCvlZnaQvYPZLWLNao
```

## Phase 10: Pull The Published Update

Use a new Cowork task/session if infrastructure or plugin code changed.

```text
Call aiws.skills.resolve with skill_id: meeting-followup, marketplace_id: checkout-main, host_kind: cowork.

Then call aiws.skills.materialize with skill_id: meeting-followup, marketplace_id: checkout-main, host_kind: cowork.

Report only:
resolve marketplace_id, plugin_id, skill_id, version, source
materialize marketplace_id, plugin_id, skill_id, version, source, cache_path, plugin_cache_path
```

Verified result:

```text
resolve version: 0.2.4
materialize version: 0.2.4
marketplace_id: checkout-main
plugin_id: productivity
skill_id: meeting-followup
source: google-drive:checkout-main:productivity:1kHkGVdTO0-_JCrxrg4vX-6Mi9BvwLkMT
cache_path: ~/.aiws/hosts/<host>/shared-cache/skills/project_checkout-main/meeting-followup/0.2.4
plugin_cache_path: ~/.aiws/hosts/<host>/shared-cache/plugins/checkout-main/productivity/0.2.4
```

This is the final pull-update PASS condition.

## Known Current Limitations

- Cowork cannot update `core-aiws` from inside the currently running `core-aiws` MCP runtime; use `aiws.runtime.update_status` for the exact native update instruction.
- `aiws.host.install` packages generated adapters only; it is not an infrastructure plugin updater.
- Cowork native UI does not yet render AIWS Drive marketplaces as first-class marketplace entries.
- Drive MCP and AIWS Drive client may use different OAuth sessions. Prefer AIWS tools for marketplace state.
- Old package versions may remain visible as materialized history. This is useful for rollback.

## Optional Maintenance: Dry-Run Artifact Cleanup

Use this only for maintenance cleanup, not during the normal demo path. The tool is constrained to a registered Drive marketplace artifact version and refuses to delete the current version.

Dry run:

```text
Call aiws.marketplaces.delete_artifact with marketplace_id: checkout-main, plugin_id: productivity, version: 0.2.3, dry_run: true.
Report status, current_version, would_delete, deleted.
```

Expected:

```text
status: planned
current_version: 0.2.4
would_delete: package, release_metadata, and possibly version_folder
deleted: []
```

Actual cleanup requires explicit confirmation:

```text
Call aiws.marketplaces.delete_artifact with marketplace_id: checkout-main, plugin_id: productivity, version: 0.2.3, dry_run: false, confirm: true.
```

The tool refuses current-version deletion. This should fail:

```text
Call aiws.marketplaces.delete_artifact with marketplace_id: checkout-main, plugin_id: productivity, version: 0.2.4, dry_run: false, confirm: true.
```

## Follow-Up Development Plan

Do after the demo path is locked:

- Add a first-class Cowork native plugin update workflow.
- Render AIWS Drive marketplaces in the Cowork-visible marketplace workflow/UI.
- Remove or retire user-facing scopes after explicit `marketplace_id` resolution remains stable.

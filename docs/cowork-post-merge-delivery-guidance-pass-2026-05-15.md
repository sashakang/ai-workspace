# Cowork Post-Merge Delivery Guidance PASS

**Date:** 2026-05-15  
**Core package:** `core-aiws` 0.3.16  
**Scenario:** Scenario 12A, post-merge marketplace delivery guidance  
**Result:** PASS

## Summary

Cowork successfully completed the regular user draft/edit/validate/stage/submit path and returned the new `post_merge_delivery` guidance after submit.

The important product behavior passed: regular users are not asked to manually upload ZIP files after submitting a skill proposal. The regular user next step is to wait for maintainer review, merge, and Cowork marketplace update or sync.

## Setup

```text
marketplace: sashakang/ai-workspace
core-aiws version: 0.3.16
aiws-productivity version: 0.2.1
skill: aiws-productivity:meeting-followup
installed copies found: 1
duplicate installed copies: no
```

## Draft

Cowork reused the existing active draft:

```text
draft_id: aiws-productivity--meeting-followup--25bf8e1a23
draft_path: ~/.aiws/plugins/cowork-upload/aiws-productivity-25bf8e1a23/
selected source plugin root: rpm/plugin_01UbGZsu5hJezcVifsV8C75U
```

The edit was confined to:

```text
skills/meeting-followup/SKILL.md
```

Installed plugin files were not touched.

## Validation

```text
validation_status: passed
modified: true
status_label: Modified locally
current_tree_digest: cd3f563a...564ec4
validation_tree_digest: cd3f563a...564ec4
```

The current and validation digests matched.

No package was built, no proposal was staged during validation, GitHub was not touched, and installed plugin files were not touched.

## Stage

```text
proposal_id: skillprop_e5b0ba9eb9e64ad38915be7d72731b33
target_repo: sashakang/aiws-skill-tests
target_scope: Personal test skills
validation_digest: cd3f563a...564ec4
```

Staging created only the local proposal record. It did not build a package, create a branch, commit, push, create a PR, mutate Cowork runtime files, touch installed plugin files, or touch `~/.claude`.

## Submit

```text
submit status: submitted_for_review
proposal_id: skillprop_e5b0ba9eb9e64ad38915be7d72731b33
target_repo: sashakang/aiws-skill-tests
branch_name: aiws/skill-proposals/skillprop_e5b0ba9eb9e64ad38915be7d72731b33
pr_url: https://github.com/sashakang/aiws-skill-tests/pull/5
proposal status changed staged -> submitted: yes
```

## Post-Merge Delivery Guidance

The submitted response included:

```text
post_merge_delivery.status: marketplace_update_required_after_merge
post_merge_delivery.normal_user_manual_zip_upload_required: false
post_merge_delivery.regular_user_next_step: Wait for maintainer review, merge, and Cowork marketplace update/sync.
post_merge_delivery.local_activation: technical_pilot_fallback_only
```

Delivery paths returned:

```text
github_synced: maintainer merges, then Cowork marketplace update/sync happens or automatic sync applies
manual: maintainer/admin uploads a same-name ZIP as the manual-marketplace fallback
```

## Side Effects

```text
installed plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated: no
```

## Interpretation

This confirms the normal user path is now clean:

1. The user edits, validates, stages, and submits from Cowork.
2. After submit, the user waits for maintainer review and merge.
3. Updated skill delivery returns through Cowork marketplace update/sync.
4. Manual ZIP upload is not presented as the regular user path.
5. Local package activation remains a technical-pilot fallback only.

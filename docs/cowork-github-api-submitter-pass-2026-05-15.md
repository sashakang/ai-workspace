# Cowork GitHub API Submitter PASS

**Date:** 2026-05-15  
**Core package:** `core-aiws` 0.3.17  
**Scenario:** Scenario 12B, non-CLI GitHub submitter  
**Result:** PASS

## Summary

Cowork successfully submitted a staged AIWS skill proposal through the GitHub API submitter.

The important product behavior passed: proposal submission did not require host `gh`, and the user did not paste a GitHub token into chat. The token was available to the AIWS runtime through host configuration.

## Setup

```text
core-aiws version: 0.3.17
aiws-productivity version: 0.2.1
skill: aiws-productivity:meeting-followup
GitHub API submitter available: yes
host gh required: no
GitHub token pasted into chat: no
```

## Draft Flow

Cowork opened the existing `meeting-followup` draft, made a small wording edit inside the draft copy, validated the draft, staged a proposal, revalidated before submit, and submitted the proposal for review.

```text
draft_id: aiws-productivity--meeting-followup--25bf8e1a23
changed file: skills/meeting-followup/SKILL.md
validation status: passed
digest gate: passed
```

The draft edit was isolated under `~/.aiws/plugins/cowork-upload/...`; installed plugin files were not touched.

## Stage

```text
proposal_id: skillprop_eda007fd1ea24c48821c9a33c7e56dab
target_repo: sashakang/aiws-skill-tests
```

## Submit

```text
submit status: submitted_for_review
proposal_id: skillprop_eda007fd1ea24c48821c9a33c7e56dab
target_repo: sashakang/aiws-skill-tests
branch_name: aiws/skill-proposals/skillprop_eda007fd1ea24c48821c9a33c7e56dab
pr_url: https://github.com/sashakang/aiws-skill-tests/pull/6
host gh required: no
GitHub token pasted into chat: no
```

## Post-Merge Delivery

```text
post_merge_delivery present: yes
post_merge_delivery.status: marketplace_update_required_after_merge
post_merge_delivery.normal_user_manual_zip_upload_required: false
```

## Side Effects

```text
installed plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated: no
```

## Interpretation

This validates the 0.3.17 non-CLI submitter path in Cowork:

1. A regular user can submit a staged skill proposal without local `gh`.
2. The GitHub token is supplied by host configuration, not pasted into chat.
3. The proposal still follows the same digest gate and repository allowlist guard.
4. The PR is created in the target review repository.
5. Delivery after merge still goes through Cowork marketplace update/sync, not regular-user ZIP upload.

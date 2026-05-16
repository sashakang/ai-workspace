# Cowork Update Conflict Review And Resolution PASS

**Date:** 2026-05-16  
**Core package:** `core-aiws` 0.3.20  
**Domain plugin:** `aiws-productivity` 0.2.2  
**Scenario:** CW-15, marketplace update conflict review and safe resolution  
**Result:** PASS

## Summary

Cowork exercised the full update-conflict path for a modified `aiws-productivity:meeting-followup` draft after the marketplace plugin updated from `0.2.1` to `0.2.2`.

The runtime created a trusted update candidate without asking the user for filesystem paths, showed both local-vs-base and remote-vs-base diffs, exposed exactly the three approved resolver choices, and resolved the conflict by accepting the remote version. The draft was updated to the remote `0.2.2` base and marked clean. Installed plugin files, Cowork runtime files, `~/.claude`, and memory paths were not touched.

## Setup

Before this test, `aiws-productivity` was updated in the marketplace source:

| Item | Value |
|---|---|
| Previous `aiws-productivity` version | `0.2.1` |
| New `aiws-productivity` version | `0.2.2` |
| Updated skill | `meeting-followup` |
| Remote skill change | Follow-up messages should be direct and clear, lead with the key action or decision, and avoid filler. |

Cowork then refreshed/updated the marketplace plugin and confirmed:

| Check | Result |
|---|---|
| `core-aiws` installed | PASS, `0.3.20` |
| `aiws-productivity` installed | PASS, `0.2.2` |
| `meeting-followup` visible | PASS |
| `prepare_update_candidate` available | PASS |
| `review_update_conflict` available | PASS |
| `resolve_update_conflict` available | PASS |

## Candidate Preparation

| Field | Value |
|---|---|
| Status | `update_candidate_created` |
| `update_candidate_id` | `updcand_b69531afec4f4264a63616b6277a5754` |
| Plugin | `aiws-productivity` |
| Skill | `meeting-followup` |
| Base digest | `6a1c80b6fc99baeb0c0b758c80686240a63d65f3f0114b9a825dbfa8ac81b7b5` |
| Remote digest | `45ee5b71e06b58de56cd5665f3c16df2ec33cf3043e585db1037df3d8531f603` |
| Remote version | `0.2.2` |
| User filesystem paths required | No |

`update_available: true` confirmed the draft base and installed remote differed.

## Conflict Review

| Field | Value |
|---|---|
| `review_id` | `updrev_d1dae177b82546a7855323bfbb63534b` |
| Status | `update_conflict` |
| Reason | `modified_draft_or_pending_upload` |
| Local changed files | `skills/meeting-followup/SKILL.md` |
| Remote changed files | `.claude-plugin/plugin.json`, `contracts/aiws-productivity.contract.json`, `skills/meeting-followup/SKILL.md` |
| Local non-skill changed files | none |
| Remote non-skill changed files | `.claude-plugin/plugin.json`, `contracts/aiws-productivity.contract.json` |
| Pending upload | none |

Local-vs-base diff showed the local draft changed:

```diff
--- base/skills/meeting-followup/SKILL.md
+++ local/skills/meeting-followup/SKILL.md
-  - draft follow-up messages
+  - draft follow-up messages (keep them direct and clear — lead with the key action or decision, avoid filler)
```

Remote-vs-base diff showed the remote update made the same skill edit and also changed plugin metadata from `0.2.1` to `0.2.2`.

Available resolver choices were exactly:

```text
keep_local_draft_and_pending_package
discard_local_changes_and_update
submit_or_upload_first
```

No merge choice was exposed.

## Resolution

The test chose `discard_local_changes_and_update`, because local and remote had the same `SKILL.md` edit and the remote also had the correct `0.2.2` metadata.

| Field | Value |
|---|---|
| Status | `discarded_local_changes_and_updated` |
| `review_id` | `updrev_d1dae177b82546a7855323bfbb63534b` |
| Draft | `aiws-productivity--meeting-followup--de0e75a572` |
| Modified | `false` |
| Base digest after resolve | `45ee5b71e06b58de56cd5665f3c16df2ec33cf3043e585db1037df3d8531f603` |
| Current digest after resolve | `45ee5b71e06b58de56cd5665f3c16df2ec33cf3043e585db1037df3d8531f603` |
| Cleared pending uploads | `0` |
| Remote non-skill files adopted | `.claude-plugin/plugin.json`, `contracts/aiws-productivity.contract.json` |

The draft is now clean against the remote `0.2.2` base.

## Safety

| Surface | Result |
|---|---|
| Installed plugin files touched | No |
| Cowork runtime files mutated | No |
| `~/.claude` touched | No |
| Memory paths touched | No |
| User filesystem paths requested | No |
| AIWS draft/state mutated | Yes, expected |

The resolver response included `mutated: true`; this refers to the AIWS draft worktree/state being updated. It does not mean Cowork runtime files were mutated.

## Conclusion

CW-15 passed end to end. The marketplace update conflict path can now:

- create a trusted server-owned update candidate
- show local and remote diffs
- report remote metadata changes separately
- present only the three approved resolver choices
- resolve by accepting the remote update
- mark the draft clean against the new remote base
- avoid installed plugin, Cowork runtime, `~/.claude`, and memory mutations

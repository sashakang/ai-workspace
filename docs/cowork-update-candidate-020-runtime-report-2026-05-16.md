# Cowork Update Candidate 0.3.20 Runtime Report

**Date:** 2026-05-16  
**Core package:** `core-aiws` 0.3.20  
**Scenario:** CW-15, marketplace update candidate preparation and normal proposal submit  
**Result:** PASS

## Summary

Cowork loaded `core-aiws` 0.3.20 and exposed the update-candidate tools. A modified `aiws-productivity:meeting-followup` draft was recreated under 0.3.20 so the draft had a base snapshot, the preserved local edit was reapplied, validation passed, and `prepare_update_candidate` ran successfully without asking the user for filesystem paths.

The candidate-preparation result was `no_update_available`, which is correct for this run because the installed marketplace plugin still matched the draft base. Since there was no remote/base difference, the conflict-review resolver path was not exercised in runtime. The normal proposal path then staged and submitted the validated local edit, creating PR #8 in `sashakang/aiws-skill-tests`. The user reported that PR #8 was merged.

## Evidence

| Check | Result |
|---|---|
| `core-aiws` installed | PASS |
| `core-aiws` version | `0.3.20` |
| `aiws.skills.prepare_update_candidate` available | PASS |
| `aiws.skills.review_update_conflict` available | PASS |
| `aiws.skills.resolve_update_conflict` available | PASS |
| Fresh draft created with clean base/current digest | PASS |
| Preserved local edit reapplied | PASS |
| Draft validation | PASS |
| `prepare_update_candidate` | PASS, `no_update_available` |
| Proposal staged | PASS |
| Proposal submitted | PASS |
| PR merged by user | PASS |

## Draft

| Field | Value |
|---|---|
| Old draft reverted | `aiws-productivity--meeting-followup--25bf8e1a23` |
| Fresh draft | `aiws-productivity--meeting-followup--de0e75a572` |
| Draft path | `~/.aiws/plugins/rpm/aiws-productivity-de0e75a572` |
| Plugin | `aiws-productivity` |
| Skill | `meeting-followup` |
| Base version | `0.2.1` |
| Base digest | `6a1c80b6fc99baeb0c0b758c80686240a63d65f3f0114b9a825dbfa8ac81b7b5` |
| Current digest after edit | `8cbf17bcff9b9efb8e4512d3bdc2f50dd3bc7c518c523041964c7dca847b0865` |
| Validation digest | `8cbf17bcff9b9efb8e4512d3bdc2f50dd3bc7c518c523041964c7dca847b0865` |

Local edit reapplied:

```text
- draft follow-up messages (keep them direct and clear — lead with the key action or decision, avoid filler)
```

## Update Candidate Result

| Field | Value |
|---|---|
| Status | `no_update_available` |
| `update_candidate_id` | `null` |
| Base digest | `6a1c80b6fc99baeb0c0b758c80686240a63d65f3f0114b9a825dbfa8ac81b7b5` |
| Remote digest | `6a1c80b6fc99baeb0c0b758c80686240a63d65f3f0114b9a825dbfa8ac81b7b5` |
| Remote version | `0.2.1` |
| User filesystem paths required | No |

Interpretation: the installed plugin matched the draft base, so no conflict candidate was needed. This confirms the missing-snapshot blocker is fixed for fresh 0.3.20 drafts, but it does not exercise the conflict-review diff/resolution branch.

## Proposal Submit

| Field | Value |
|---|---|
| Proposal ID | `skillprop_b67e84e9bfd64a56889338ca47226d81` |
| Target repo | `sashakang/aiws-skill-tests` |
| Target scope | `Personal test skills` |
| Digest gate | PASS, `validation_tree_digest == current_tree_digest` |
| Allowlist gate | PASS |
| Branch | `aiws/skill-proposals/skillprop_b67e84e9bfd64a56889338ca47226d81` |
| PR | https://github.com/sashakang/aiws-skill-tests/pull/8 |
| PR state | Merged, per user report |
| Package built | No |

Correction from the runtime chat: submit-for-review created a branch and PR; it did not build a Cowork ZIP package.

## Safety

| Surface | Result |
|---|---|
| Installed plugin files touched | No |
| Cowork runtime files mutated | No |
| `~/.claude` touched | No |
| Manual filesystem paths requested from user | No |
| Package built/uploaded | No |

## Caveat

The runtime conflict-review path remains untested because the installed plugin and draft base were identical. A future test needs a real marketplace update where `prepare_update_candidate` returns `update_candidate_created`, followed by `review_update_conflict` and one resolver choice.

# Cowork Repository Review Policy PASS

**Date:** 2026-05-16  
**Core package:** `core-aiws` 0.3.18  
**Scenario:** Scenario 12C, repository review policy visibility  
**Result:** PASS

## Summary

Cowork successfully submitted a staged AIWS skill proposal and returned `repository_review_policy` metadata.

The important product behavior passed: Cowork did not ask the normal user to choose GitHub reviewers, did not emit hardcoded AI engineer reviewer metadata, and did not block submit because CODEOWNERS was missing.

## Setup

```text
core-aiws version: 0.3.18
aiws-productivity version: 0.2.1
skill: aiws-productivity:meeting-followup
submit-for-review tool: available
```

## Draft Flow

Cowork reused the existing active draft:

```text
draft_id: aiws-productivity--meeting-followup--25bf8e1a23
selected source plugin root: rpm/plugin_01UbGZsu5hJezcVifsV8C75U
duplicate installed copies: no
changed file: skills/meeting-followup/SKILL.md
```

The edit changed `no filler` to `avoid filler` in the follow-up message guidance. The edit stayed inside the AIWS draft under `~/.aiws/plugins/cowork-upload/...`; installed plugin files were not touched.

## Validation

```text
validation status: passed
modified: true
status label: Modified locally
current_tree_digest: b9db1e84...6d94d7
validation_tree_digest: b9db1e84...6d94d7
```

The current and validation digests matched.

## Stage

```text
proposal_id: skillprop_04eb5b9bb9834e8b8b8bf32d287a8e7a
target_repo: sashakang/aiws-skill-tests
target_scope: Personal test skills
validation_tree_digest: b9db1e84d744ed34e339ae744a5644aaebf625360257c2217b987bebeb6d94d7
```

Staging did not build a package, create a branch, commit, push, create a PR, mutate Cowork runtime files, touch installed plugin files, or touch `~/.claude`.

## Submit

```text
submit status: submitted_for_review
proposal_id: skillprop_04eb5b9bb9834e8b8b8bf32d287a8e7a
target_repo: sashakang/aiws-skill-tests
branch_name: aiws/skill-proposals/skillprop_04eb5b9bb9834e8b8b8bf32d287a8e7a
pr_url: https://github.com/sashakang/aiws-skill-tests/pull/7
```

## Repository Review Policy

```text
repository_review_policy present: yes
repository_review_policy.status: absent
repository_review_policy.codeowners: not_detected
repository_review_policy.normal_user_selects_reviewers: false
repository_review_policy.caveat: CODEOWNERS not detected; repository maintainers still own review and merge.
```

Additional checks:

```text
required_review_roles emitted: no
hardcoded AI engineer reviewer metadata emitted: no
missing CODEOWNERS blocked submit: no
installed plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated: no
```

## Interpretation

This validates the no-CODEOWNERS branch of repository-policy visibility:

1. AIWS reports missing CODEOWNERS as a caveat.
2. Missing CODEOWNERS does not block proposal submission.
3. Review ownership stays with repository maintainers and repository policy.
4. Normal Cowork users are not asked to map reviewers or teams.
5. Normal Cowork submission does not emit hardcoded reviewer-role metadata.

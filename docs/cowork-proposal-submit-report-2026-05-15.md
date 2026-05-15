# Cowork Proposal Submit Report

**Date:** 2026-05-15  
**Result:** PASS, including repository-guard evidence  
**Scope:** CW-11 and CW-12 verification that a regular Cowork user can stage a modified `aiws-productivity:meeting-followup` draft as a local proposal and submit it to the allowed review repository.

## Summary

The proposal flow passed after re-staging with the real target repository. Cowork staged a local proposal for the modified draft without creating any remote side effects, then submitted it for review after revalidating the draft and passing the repository allowlist gate.

The test also produced useful guard evidence: an earlier submit attempt was correctly blocked because the proposal had been staged with the literal placeholder `<test review repository>` instead of the real repository. That blocked attempt did not create a branch, commit, push, or pull request.

## Draft

```text
draft_id: aiws-productivity--meeting-followup--de0e75a572
validation/current digest: c94dc08ad7a6633e2755611fc8f9866a158793c63617325cb9db63618e964265
```

Before submit, Cowork revalidated the draft and confirmed:

```text
validation_tree_digest == current_tree_digest
```

The digest gate passed, proving the submitted proposal matched the validated draft state.

## Repository Guard Evidence

An earlier staged proposal had:

```text
proposal_id: skillprop_276125b8c6754e059be0644b1b0ae2bf
stored target_repo: <test review repository>
allowed_target_repos: ["sashakang/aiws-skill-tests"]
```

Cowork correctly failed closed before calling `submit_for_review` because the stored target repo was not in the allowlist.

Observed guard result:

```text
submit result/status: BLOCKED
repo allowlist gate passed: no
branch created: no
commit created: no
push: no
pull request: no
installed marketplace plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated: no
```

## Stage Evidence

The proposal was re-staged with the real target repository:

```text
proposal_id: skillprop_bb386ac3528247c7bf7ddb88793497b2
target_repo: sashakang/aiws-skill-tests
target_scope: Personal test skills
status: staged
next_action: submit_for_review
```

Staging side effects:

```text
package built: no
branch / commit / push / PR created: no
Cowork runtime files mutated: no
installed plugin files touched: no
```

The local proposal record was written under:

```text
~/.aiws/state/skill-proposals/skillprop_bb386ac3528247c7bf7ddb88793497b2.json
```

## Submit Evidence

Submit result:

```text
submit status: submitted_for_review
proposal_id: skillprop_bb386ac3528247c7bf7ddb88793497b2
target_repo used: sashakang/aiws-skill-tests
branch_name: aiws/skill-proposals/skillprop_bb386ac3528247c7bf7ddb88793497b2
pr_url: https://github.com/sashakang/aiws-skill-tests/pull/3
proposal status changed staged -> submitted: yes
validation/digest gate passed: yes
installed marketplace plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated: no
errors / manual follow-up: none
```

Result: PASS.

## Product Notes

This confirms the regular-user proposal flow works for a modified skill draft:

1. User edits and validates a draft.
2. User stages the draft as a local proposal.
3. Cowork blocks submission if the stored target repo is not allowed.
4. Cowork submits to the allowed review repo after the digest gate passes.

The review and merge decision remains with the repository owner or repository policy. The Cowork user should not be asked to decide GitHub reviewer routing.

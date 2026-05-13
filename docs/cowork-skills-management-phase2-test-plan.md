# Cowork Skills-Management Phase 2 Test Plan

**Date:** 2026-05-13  
**Scope:** Validate the Cowork skills-management lifecycle after marketplace install.

This plan starts from the primary Cowork marketplace journey. Manual ZIP import is a fallback install path only.

The current lifecycle bridge is still **Phase 2A technical pilot** behavior. It may depend on the bundled `core-aiws` MCP bridge and `uvx`. It is not yet the final normal-user Cowork experience.

## What You Are Testing

You are testing whether a marketplace-installed Cowork skill can be:

1. opened as a local AIWS draft
2. edited safely
3. validated without side effects
4. prepared for later activation and proposal review

The main operation to test now is:

```text
aiws.skills.validate_draft
```

Validation must check the draft and update status metadata. It must not build a package, activate the draft, stage a proposal, submit a pull request, or mutate the installed marketplace plugin.

## Tester Rules

Use Cowork prompts first. Do not type code unless Cowork exposes a raw tool-call surface.

For each operation, this plan gives:

- **Prompt to Cowork:** what to paste into Cowork
- **Expected tool call:** what Cowork or the AIWS bridge should do behind the scenes
- **Record:** what you need to save from the result

If Cowork cannot reach the named tool, mark the test `BLOCKED` and record the exact error.

## Placeholders

Replace these before testing:

```text
<test review repository>
<clean test review repository>
<disposable test review repository>
```

Use a test repository that is safe for proposal experiments. Example:

```text
sashakang/aiws-skill-tests
```

Do not use a real maintained skills repository for submit-for-review testing unless the maintainer explicitly approved that test PR. For validation-only clean or disposable drafts, the repository value is mainly used to create a distinct draft identity in the current technical-pilot bridge.

Draft identity uses the target repository as part of the origin identity in the current technical-pilot bridge. If you want a truly separate draft without resetting the AIWS test root, use a distinct test repository value for that scenario, for example:

```text
sashakang/aiws-skill-tests-clean
sashakang/aiws-skill-tests-disposable
```

```text
<temporary package output directory outside ~/.claude>
```

Use a temporary AIWS package directory, not a Claude memory path. Example:

```text
~/.aiws/tmp/cowork-phase2-packages
```

## Install Starting Point

Start from Cowork marketplace install:

1. Open Cowork.
2. Add the AIWS marketplace:

```text
sashakang/ai-workspace
```

3. Install `core-aiws`.
4. Install `aiws-productivity`.
5. Confirm `meeting-followup` is visible.
6. Generate `meeting-followup` nodes from a harmless test input.

Prompt to Cowork:

```text
Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork marketplace install first.
```

Record:

- Cowork UI path used to add the marketplace
- installed plugin IDs for `core-aiws` and `aiws-productivity`
- visible skill label for `meeting-followup`
- short proof that `meeting-followup` generated nodes correctly

## Safety Rules

- Do not delete, move, or edit `~/.claude`.
- Do not run memory sync commands.
- Do not edit Cowork RPM files or manifests by hand.
- Do not copy plugin folders directly into Cowork runtime directories.
- Do not edit installed marketplace plugin files in place.
- Draft edits must stay under the AIWS draft workspace.
- For this phase, user edits must stay inside `skills/meeting-followup/`.
- Run destructive negative tests only against a disposable draft, disposable AIWS test root, or a draft that has been snapshotted and can be restored.
- Do not continue normal lifecycle testing from a draft after intentionally removing `SKILL.md` or editing out-of-scope files.

## Scenario A: Create Or Open Draft

Prompt to Cowork:

```text
Create or open an AIWS draft for the installed skill:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: <test review repository>

Use the installed Cowork marketplace plugin as the source. Do not edit the installed marketplace plugin files. Create the editable draft under the AIWS draft workspace.
```

Expected tool call:

```text
aiws.skills.create_or_open_draft(
  plugin_id: "aiws-productivity",
  skill_id: "meeting-followup",
  target_repo: "<test review repository>"
)
```

Expected result:

```text
status: draft_opened
draft_path: ~/.aiws/plugins/...
```

Record:

- `draft_id` or `record_id`
- `draft_path`
- source plugin or marketplace label, if Cowork shows it

The draft path must be under `~/.aiws/plugins/`. It must not be inside the installed marketplace plugin.

## Scenario B: Happy Path Draft Validation

Start from the draft created in Scenario A.

Prompt to Cowork:

```text
Edit the AIWS draft for aiws-productivity/meeting-followup.

Make a small harmless text change inside skills/meeting-followup/ only.
Do not edit contracts, plugin manifests, memory files, runtime files, or installed marketplace plugin files.
After editing, tell me which draft file changed.
```

Record:

- changed file path
- confirmation that the changed file is under `skills/meeting-followup/`

Then validate.

Prompt to Cowork:

```text
Validate this AIWS draft without activating it, staging a proposal, building a package, submitting a PR, or editing installed marketplace files:

draft_id: <draft_id from Scenario A>
```

Expected tool call:

```text
aiws.skills.validate_draft(<draft_id>)
```

Expected result:

```text
status: validated
validation_status: passed
modified: true
status_label: Modified locally
```

Confirm no side effects happened:

- no Cowork runtime files were edited manually
- no package ZIP was created by validation
- no proposal record was created
- no GitHub branch, commit, push, or pull request was created
- installed marketplace plugin files were not changed

## Scenario C: Unchanged Draft Validation

This scenario must use a clean draft. Do not reuse the modified draft from Scenario B unless you first restore it to its original content.

Use one of these clean-start options:

- use a fresh disposable AIWS test root
- restore the draft from a snapshot taken before Scenario B
- use a distinct validation-only `target_repo` value so `create_or_open_draft` creates a separate draft identity

Prompt to Cowork:

```text
Create or open a clean AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: <clean test review repository>

Do not edit the draft. Then validate it without activating, staging, packaging, or submitting anything.
```

Expected tool calls:

```text
aiws.skills.create_or_open_draft(
  plugin_id: "aiws-productivity",
  skill_id: "meeting-followup",
  target_repo: "<clean test review repository>"
)

aiws.skills.validate_draft(<clean_draft_id>)
```

Expected validation result:

```text
status: validated
validation_status: passed
modified: false
status_label: Current
```

Confirm no proposal, package, activation, or GitHub action happened.

## Scenario D: Out-Of-Scope Edit Fails Closed

Use a disposable draft or snapshot the draft before this scenario.

If you are not using a fresh disposable AIWS test root, use a distinct validation-only `target_repo` value so this scenario cannot corrupt the normal draft from Scenario B.

Prompt to Cowork:

```text
Create or open a disposable AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: <disposable test review repository>

In that disposable draft, make a test-only edit outside skills/meeting-followup/, for example in a contract or plugin manifest.

Then run draft validation.

Do not activate, stage, package, submit, or edit installed marketplace plugin files.
```

Expected tool calls:

```text
aiws.skills.create_or_open_draft(
  plugin_id: "aiws-productivity",
  skill_id: "meeting-followup",
  target_repo: "<disposable test review repository>"
)

aiws.skills.validate_draft(<disposable_draft_id>)
```

Expected result:

```text
tool result: error
persisted draft last_validation_status: failed
persisted draft last_validation_tree_digest: null
```

The operation must fail closed. It must not create a package, proposal, PR, or runtime mutation.

After this scenario, discard or restore the disposable draft.

## Scenario E: Missing Skill Fails Closed

Use a disposable draft or snapshot the draft before this scenario.

If you are not using a fresh disposable AIWS test root, use a distinct validation-only `target_repo` value so this scenario cannot corrupt the normal draft from Scenario B.

Prompt to Cowork:

```text
Create or open a disposable AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: <disposable test review repository>

In that disposable draft, temporarily remove or rename:

skills/meeting-followup/SKILL.md

Then run draft validation.

Do not activate, stage, package, submit, or edit installed marketplace plugin files.
```

Expected tool calls:

```text
aiws.skills.create_or_open_draft(
  plugin_id: "aiws-productivity",
  skill_id: "meeting-followup",
  target_repo: "<disposable test review repository>"
)

aiws.skills.validate_draft(<disposable_draft_id>)
```

Expected result:

```text
tool result: error
persisted draft last_validation_status: failed
persisted draft last_validation_tree_digest: null
```

The operation must fail closed. It must not create a package, proposal, PR, or runtime mutation.

After this scenario, discard or restore the disposable draft.

## Scenario F: Activation Technical-Pilot Check

Run this only after Scenario B passes.

Prompt to Cowork:

```text
Activate the validated AIWS draft for Cowork as a Phase 2A technical-pilot check.

draft_id: <draft_id from Scenario B>
host_kind: cowork
package_output_dir: <temporary package output directory outside ~/.claude>

Do not edit Cowork runtime files directly. If Cowork cannot activate the draft programmatically, return the package-upload fallback action.
```

Expected tool call:

```text
aiws.skills.activate_draft(
  <draft_id>,
  host_kind: "cowork",
  package_output_dir: "<temporary package output directory outside ~/.claude>"
)
```

Expected current Phase 2A result:

```text
status: host_capability_missing
requires_manual_upload: true
actions[0].type: package_upload
```

This means the bridge can build a Cowork package, but Cowork activation is still a manual upload fallback in this technical-pilot slice.

## Scenario G: Stage Proposal Without Submitting

Run this only after Scenario B passes.

Prompt to Cowork:

```text
Stage the validated AIWS draft as a proposal, but do not submit it for review yet.

draft_id: <draft_id from Scenario B>
target_scope: Personal test skills
target_repo: <test review repository>
summary: Test update to meeting-followup
rationale: Validate the Cowork Phase 2 skill proposal flow.

Staging must create only a local proposal record. Do not create a branch, commit, push, pull request, package, or Cowork runtime mutation.
```

Expected tool call:

```text
aiws.skills.stage_proposal(
  <draft_id>,
  target_scope: "Personal test skills",
  target_repo: "<test review repository>",
  summary: "Test update to meeting-followup",
  rationale: "Validate the Cowork Phase 2 skill proposal flow."
)
```

Expected result:

```text
status: staged
next_action: submit_for_review
proposal_id: <proposal_id>
```

Record:

- `proposal_id`
- proposal path, if returned
- confirmation that no branch, commit, push, or PR was created

## Scenario H: Submit For Review, Optional And Guarded

This scenario is optional. Run it only when a test repository or fake/dry-run submitter is available.

Do not run this against a real maintained skills repository unless the maintainer explicitly approved the test PR.

Prompt to Cowork:

```text
Submit this staged AIWS proposal for review using only the allowed test repository.

proposal_id: <proposal_id from Scenario G>
allowed_target_repos:
- <test review repository>

If the stored target repository is not in allowed_target_repos, fail closed. Do not submit anywhere else.
```

Expected tool call:

```text
aiws.skills.submit_for_review(
  <proposal_id>,
  allowed_target_repos: ["<test review repository>"]
)
```

Expected result:

```text
status: submitted_for_review
branch_name: aiws/skill-proposals/<proposal_id>
pr_url: <review PR URL>
```

Expected persisted proposal state:

```text
required_review_roles includes AI engineer
```

Negative submit guard:

Prompt to Cowork:

```text
Test the submit-for-review repository guard for this staged proposal.

proposal_id: <proposal_id from Scenario G>
allowed_target_repos:
- <different test repository that is not the proposal target_repo>

This must fail closed because the proposal's stored target_repo is not allowed. Do not create a branch, commit, push, pull request, package, or Cowork runtime mutation.
```

Expected tool call:

```text
aiws.skills.submit_for_review(
  <proposal_id>,
  allowed_target_repos: ["<different test repository that is not the proposal target_repo>"]
)
```

Expected result:

```text
tool result: error
reason: target_repo is not allowed
```

Confirm no branch, commit, push, pull request, package, or Cowork runtime mutation was created.

## Pass Criteria

Mark the core Phase 2A validation slice as `PASS` only if:

- the skill was installed through the Cowork marketplace path
- `meeting-followup` works before draft testing starts
- draft creation does not mutate installed marketplace files
- valid changed draft validation passes
- unchanged draft validation passes with `modified=false`
- out-of-scope edits fail closed
- missing skill validation fails closed
- validation creates no package, proposal, branch, commit, push, or PR
- `~/.claude` remains untouched
- memory sync commands were not run

Mark lifecycle continuation as `PASS` only if the tested continuation scenarios also prove:

- activation returns `host_capability_missing`
- activation returns `requires_manual_upload: true`
- activation returns `actions[0].type: package_upload`
- staging returns `status: staged`
- staging returns `next_action: submit_for_review`
- staging creates only a local proposal record
- staging does not create a branch, commit, push, pull request, package, or Cowork runtime mutation
- if submit-for-review is tested, the call uses `allowed_target_repos`
- if submit-for-review is tested, it fails closed when the stored target repo is not allowed
- if submit-for-review is tested and succeeds, proposal state records `required_review_roles` including `AI engineer`

## Fail Or Block Criteria

Mark as `FAIL` if:

- validation mutates installed marketplace files
- validation creates a package, proposal, or GitHub review item
- validation passes when files outside `skills/meeting-followup/` changed
- validation passes when the requested skill is missing
- validation touches `~/.claude` or memory sync paths
- activation reports success while requiring manual package upload
- staging creates a branch, commit, push, pull request, package, or Cowork runtime mutation
- submit-for-review runs without `allowed_target_repos`
- submit-for-review succeeds against a repository outside `allowed_target_repos`

Mark as `BLOCKED` if:

- Cowork cannot install `core-aiws` or `aiws-productivity` from the marketplace
- Cowork cannot expose or reach the draft-management tool surface
- the runtime bridge cannot start in the technical-pilot environment
- the tester cannot safely distinguish draft files from installed marketplace files

## Evidence To Record

Record:

- Cowork version/build.
- Account type.
- Marketplace UI path.
- Installed plugin IDs.
- Visible skill label for `meeting-followup`.
- Proof that `meeting-followup` generated nodes before draft testing.
- Draft ID.
- Draft path.
- Files edited.
- `validate_draft` result for changed draft.
- `validate_draft` result for unchanged draft.
- Failure output for out-of-scope edit.
- Failure output for missing skill.
- Confirmation that validation created no package, proposal, PR, branch, commit, or push.
- Confirmation that `~/.claude` was not touched.
- Confirmation that no memory sync commands were run.

## Report Template

```text
Cowork skills-management Phase 2A validation result: PASS / FAIL / BLOCKED

Tester:
Date:
Cowork version/build:
Account type:

Marketplace UI path:
Marketplace repo/path:
Installed plugins:
- core-aiws:
- aiws-productivity:

Starter skill:
- meeting-followup visible: yes/no
- meeting-followup nodes generated: yes/no
- evidence:

Draft:
- draft_id:
- draft_path:
- edited files:

Validation:
- changed draft result:
- unchanged draft result:
- out-of-scope edit result:
- missing skill result:

Side effects:
- package created by validation: no/yes
- proposal created by validation: no/yes
- branch/commit/push/PR created by validation: no/yes
- installed marketplace files mutated: no/yes
- ~/.claude touched: no/yes
- memory sync commands run: no/yes

Lifecycle continuation, if tested:
- activation result:
- staging result:
- submit-for-review result:

Logs/errors:
Result notes:
Open blockers:
```

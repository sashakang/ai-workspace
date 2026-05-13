# Cowork Skills-Management Phase 2 Test Plan

**Date:** 2026-05-13  
**Scope:** Validate the Cowork skills-management lifecycle after marketplace install.

This plan starts from the primary Cowork marketplace journey. Manual ZIP import is a fallback install path only. The current lifecycle bridge is still Phase 2A technical pilot behavior because the runtime may depend on the bundled `core-aiws` MCP bridge and `uvx`; it is not yet the final normal-user Cowork experience.

## Goal

Confirm that a marketplace-installed skill can be opened as a local draft, edited safely, validated without side effects, and prepared for the later activation and proposal flow.

The main behavior to prove now is the new validation step:

```text
aiws.skills.validate_draft
```

Validation must check the draft and update status metadata without building a package, activating the draft, staging a proposal, submitting a pull request, or mutating the installed marketplace plugin.

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

Record the Cowork UI path, plugin IDs, visible skill label, and any marketplace/source labels Cowork shows.

## Safety Rules

- Do not delete, move, or edit `~/.claude`.
- Do not run memory sync commands.
- Do not edit Cowork RPM files or manifests by hand.
- Do not copy plugin folders directly into Cowork runtime directories.
- Do not edit installed marketplace plugin files in place.
- Draft edits must stay under the AIWS draft workspace.
- For this phase, user edits must stay inside `skills/meeting-followup/`.
- Run destructive negative tests only against a disposable draft, disposable AIWS test root, or a draft that has been snapshotted and can be restored. Do not continue normal lifecycle testing from a draft after intentionally removing `SKILL.md` or editing out-of-scope files.

## Test Scenario A: Happy Path Draft Validation

1. Create or open a draft for:

```text
aiws.skills.create_or_open_draft(
  plugin_id: "aiws-productivity",
  skill_id: "meeting-followup",
  target_repo: "<test review repository>"
)
```

2. Confirm the draft is created under `~/.aiws/plugins/`, not inside the installed marketplace plugin.
3. Edit a text file under:

```text
skills/meeting-followup/
```

4. Run the draft validation action:

```text
aiws.skills.validate_draft(draft_id)
```

5. Confirm the validation result:

```text
status: validated
validation_status: passed
modified: true
status_label: Modified locally
```

6. Confirm no side effects happened:

- no Cowork runtime files were edited manually
- no package ZIP was created by validation
- no proposal record was created
- no GitHub branch, commit, push, or pull request was created
- installed marketplace plugin files were not changed

## Test Scenario B: Unchanged Draft Validation

1. Create or open a clean draft that has not been edited. If Scenario A already modified the only available draft, use a fresh disposable AIWS test root or restore the draft to its original content before this scenario.
2. Run:

```text
aiws.skills.validate_draft(draft_id)
```

3. Confirm:

```text
status: validated
validation_status: passed
modified: false
status_label: Current
```

4. Confirm no proposal, package, activation, or GitHub action happened.

## Test Scenario C: Out-Of-Scope Edit Fails Closed

1. Open a disposable draft or snapshot the draft so it can be restored after this scenario.
2. Edit a file outside the managed skill folder, for example a contract or plugin manifest.
3. Run:

```text
aiws.skills.validate_draft(draft_id)
```

4. Expected result:

```text
tool result: error
persisted draft last_validation_status: failed
persisted draft last_validation_tree_digest: null
```

The operation should fail closed and must not create a package, proposal, PR, or runtime mutation.

## Test Scenario D: Missing Skill Fails Closed

1. Open a disposable draft or snapshot the draft so it can be restored after this scenario.
2. Temporarily remove or rename:

```text
skills/meeting-followup/SKILL.md
```

3. Run:

```text
aiws.skills.validate_draft(draft_id)
```

4. Expected result:

```text
tool result: error
persisted draft last_validation_status: failed
persisted draft last_validation_tree_digest: null
```

No proposal, package, activation, or GitHub action should happen.

## Test Scenario E: Continue Lifecycle After Validation

After Scenario A passes, continue with the already implemented lifecycle checks:

1. Activate the draft with an explicit Cowork host kind and package output directory:

```text
aiws.skills.activate_draft(
  draft_id,
  host_kind: "cowork",
  package_output_dir: "<temporary package output directory outside ~/.claude>"
)
```

2. Expected current Phase 2A result:

```text
status: host_capability_missing
requires_manual_upload: true
actions[0].type: package_upload
```

This means the bridge can build a Cowork package, but Cowork activation is still a manual upload fallback in this technical-pilot slice.

3. Stage a proposal with:

```text
aiws.skills.stage_proposal(
  draft_id,
  target_scope: "<user-facing target>",
  target_repo: "<test review repository>",
  summary: "<short summary>",
  rationale: "<why this change should be reviewed>"
)
```

4. Expected result:

```text
status: staged
next_action: submit_for_review
```

Staging must write a local proposal record only. It must not create a branch, commit, push, or pull request.

5. Submit for review only after an explicit submit action, and only against a test repository or fake/dry-run submitter. Do not run this step against a real maintained skills repository unless the maintainer has explicitly approved the test PR.

```text
aiws.skills.submit_for_review(
  proposal_id,
  allowed_target_repos: ["<test review repository>"]
)
```

Expected result:

```text
status: submitted_for_review
branch_name: aiws/skill-proposals/<proposal_id>
pr_url: <review PR URL>
proposal state required_review_roles includes AI engineer
```

## Pass Criteria

Mark the Phase 2A validation slice as `PASS` only if:

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

## Fail Or Block Criteria

Mark as `FAIL` if:

- validation mutates installed marketplace files
- validation creates a package, proposal, or GitHub review item
- validation passes when files outside `skills/meeting-followup/` changed
- validation passes when the requested skill is missing
- validation touches `~/.claude` or memory sync paths

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

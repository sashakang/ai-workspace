# AIWS Testing Manual

Last updated: 2026-05-16.

This manual is the starting point for AIWS testing. It lists the currently implemented scenarios, the prompt or command to use, and the expected answer. Keep detailed historical reports in their original files; keep this page current when a new scenario becomes part of the maintained test set.

Current version assumptions:

- `core-aiws` package version: `0.3.20`
- `aiws-productivity` package version: `0.2.2`
- Primary Cowork journey: marketplace install from `sashakang/ai-workspace`
- Fallback Cowork journey: ZIP upload through Cowork plugin settings

## Rules For All Cowork Tests

- Start from Cowork prompts unless a scenario explicitly says to run a local command.
- Do not edit `~/.claude`, Claude Code memory, Cowork RPM files, Cowork runtime manifests, or installed plugin folders by hand.
- Do not copy plugin folders directly into Cowork runtime directories.
- Treat marketplace install as the primary path. ZIP import is fallback or diagnostic only.
- Record exact errors and mark the scenario `BLOCKED` when Cowork cannot expose the required AIWS tool surface.
- Keep draft lifecycle scenarios in the same Cowork chat unless a scenario explicitly says to start a new chat. In practice, run CW-03, CW-04, CW-08, and CW-10 in the same chat so the `draft_id` and current draft state stay easy to track.
- Start a new Cowork chat after installing or uploading a plugin package. In practice, CW-09 should run in a new chat after the package from CW-08 is uploaded, because Cowork may only refresh the visible skill list when a new chat starts.

Common placeholders:

```text
<test review repository> = sashakang/aiws-skill-tests
<temporary package output directory outside ~/.claude> = ~/.aiws/tmp/cowork-phase2-packages
```

## Scenario Index

| ID | Scenario | Type | Expected status |
|---|---|---|---|
| CW-01 | Cowork marketplace install and skill invocation | Manual Cowork | PASS |
| CW-02 | Manual ZIP import fallback | Manual Cowork + local package build | PASS when marketplace path is unavailable |
| CW-03 | Create or open draft | Manual Cowork | PASS |
| CW-04 | Edit draft and validate | Manual Cowork | PASS |
| CW-05 | Clean draft validation | Manual Cowork | PASS |
| CW-06 | Out-of-scope edit fails closed | Manual Cowork safety | PASS when rejected or failed closed |
| CW-07 | Missing `SKILL.md` fails closed | Manual Cowork safety | PASS when failed closed |
| CW-08 | Prepare Cowork package and activation handoff | Manual Cowork technical pilot | PASS with `pending_upload` or `handoff_prepared` |
| CW-09 | Manual upload of modified draft package | Manual Cowork technical pilot | PASS |
| CW-10 | Deactivate pending upload marker | Manual Cowork cleanup | PASS |
| CW-10A | Revert stale draft records | Manual Cowork cleanup | PASS |
| CW-11 | Stage proposal without submitting | Manual Cowork | PASS |
| CW-12 | Submit proposal for review | Manual Cowork + GitHub | PASS or non-terminal handoff |
| CW-12A | Post-merge marketplace delivery guidance | Cowork/product workflow | Planned |
| CW-13 | Cowork package intake probe | Local command + new Cowork chat | Evidence-gathering |
| CW-14 | Hosted/uploaded MCP smoke experiments | Manual Cowork diagnostic | Currently BLOCKED |
| CW-15 | Marketplace update conflict review and safe resolution | Cowork/API lifecycle | PASS when diff review and chosen resolution behave safely |
| AUTO-01 | Cowork ZIP package builder tests | Automated unittest | PASS |
| AUTO-02 | Cowork package intake probe tests | Automated unittest | PASS |
| AUTO-03 | AIWS MCP lifecycle regression tests | Automated unittest | PASS |
| AUTO-04 | Full repository unittest suite | Automated unittest | PASS |
| AUTO-05 | Marketplace update conflict regression tests | Automated unittest | PASS |

## Scenario 1: Cowork Marketplace Install And Skill Invocation

Purpose: confirm the normal Cowork install/use path before draft-management testing.

Prompt to Cowork:

```text
Check my AIWS setup.

Verify:
1. Marketplace `sashakang/ai-workspace` is installed.
2. `core-aiws` is installed and updated to version 0.3.20 or newer.
3. `aiws-productivity` is installed.
4. `meeting-followup` skill is visible.

Then invoke meeting-followup on this test input:

Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork marketplace install first.

Do not edit anything. Report PASS/BLOCKED with exact evidence.
```

Expected answer:

```text
Result: PASS
Marketplace installed: sashakang/ai-workspace
core-aiws installed: yes
aiws-productivity installed: yes
meeting-followup visible: yes
meeting-followup invoked successfully: yes
```

The generated notes should include the decision, Alice's Friday action item, Ben's review action item, and a short follow-up message. Record Cowork version/build and plugin IDs if Cowork exposes them.

Source: [Cowork Canonical User Test Report](./cowork-canonical-user-test-report-2026-05-14.md).

## Scenario 2: Manual ZIP Import Fallback

Purpose: confirm Cowork's supported ZIP upload path when marketplace install is unavailable or when Team upload behavior is under test.

Build artifacts from the repo root if a maintainer has not already provided them:

```bash
python scripts/build_cowork_import.py
```

Expected command output:

```text
dist/cowork-import/core-aiws-0.3.20.zip
dist/cowork-import/aiws-productivity-0.2.2.zip
```

Cowork UI path:

```text
Organization settings -> Plugins -> Add plugin -> Upload a file
```

Upload:

```text
core-aiws-0.3.20.zip
aiws-productivity-0.2.2.zip
```

Prompt to Cowork after upload:

```text
Confirm `core-aiws` and `aiws-productivity` are installed.
Confirm `meeting-followup` is visible.

Then invoke meeting-followup on this input:

Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork plugin import install first.

Report whether the plugins installed, whether meeting-followup is visible, whether the skill ran, and whether ~/.claude or Cowork runtime files were touched.
```

Expected answer:

```text
Result: PASS
core-aiws installed: yes
aiws-productivity installed: yes
meeting-followup visible: yes
meeting-followup invocation: successful
~/.claude touched: no
Memory sync commands run: no
RPM/runtime files edited manually: no
```

Source: [Cowork Manual ZIP Import Fallback Test Plan](./cowork-clean-import-test-plan.md) and [ZIP Import Validation PASS](./aiws-cowork-plugin-import-validation-pass.md).

## Scenario 3: Create Or Open Draft

Purpose: confirm Cowork can open an editable AIWS draft from an installed skill without touching installed plugin files.

Prompt to Cowork:

```text
Create or open an AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: <test review repository>

Use the installed marketplace plugin as the source. Do not clone the repo. Do not edit installed plugin files.

Report:
- installed skill inspection status
- installed skill instance_count
- draft_id
- draft_path
- whether draft_path is under ~/.aiws/plugins/
- whether installed marketplace plugin files were touched
```

Expected answer:

```text
installed skill inspection status: ok
installed skill instance_count: 1
status: draft_opened
draft_path: ~/.aiws/plugins/...
draft_path under ~/.aiws/plugins/: yes
installed marketplace plugin files touched: no
```

Record the returned `draft_id`. The draft path must not be inside the installed Cowork plugin/RPM path. If installed skill inspection returns `duplicate_visible_identity`, draft creation must stop instead of guessing which installed copy to use. Starting in `core-aiws` 0.3.14, if another active draft already exists for the same plugin and skill, opening a different draft must fail closed unless the caller explicitly sets `allow_parallel_draft: true`.

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-a-create-or-open-draft).

Latest 0.3.13 evidence: [Cowork Inspected Draft Proposal Submit PASS](./cowork-inspected-draft-proposal-submit-pass-2026-05-15.md).

## Scenario 4: Edit Draft And Validate

Purpose: confirm a safe draft edit can be validated with no package, proposal, GitHub action, or runtime mutation.

Prompt to Cowork:

```text
Edit only this draft file:

skills/meeting-followup/SKILL.md

Use the exact draft_id returned by Scenario 3. Do not call create_or_open_draft again unless you are only reopening that same draft_id.

Make one harmless test edit: add a short instruction that follow-up messages should be clear and concise.

Do not edit any file outside skills/meeting-followup/.
Do not touch installed marketplace plugin files.
Do not stage, package, activate, submit, or use GitHub.

Report:
- exact file changed
- whether it is under skills/meeting-followup/
- whether installed plugin files were touched
```

Expected answer:

```text
exact file changed: skills/meeting-followup/SKILL.md
under skills/meeting-followup/: yes
installed plugin files touched: no
```

If Cowork creates or edits a different `draft_id` than the one returned by Scenario 3, mark the scenario failed and stop. The point of this scenario is to preserve the same draft identity through edit and validation.

Then validate:

```text
Validate the draft.

Do not package, activate, stage, submit, or touch GitHub.

Report:
- validation status
- modified status
- status label
- current_tree_digest
- validation_tree_digest
- whether any package was built
- whether any proposal was staged
- whether GitHub was touched
- whether installed marketplace plugin files were touched
```

Expected answer:

```text
validation status: passed
modified status: true
status label: Modified locally
current_tree_digest: <digest>
validation_tree_digest: <same digest>
package built: no
proposal staged: no
GitHub touched: no
installed marketplace plugin files touched: no
```

Latest 0.3.13 evidence: [Cowork Inspected Draft Proposal Submit PASS](./cowork-inspected-draft-proposal-submit-pass-2026-05-15.md).

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-b-happy-path-draft-validation).

## Scenario 5: Clean Draft Validation

Purpose: confirm an unchanged draft validates as current.

Prompt to Cowork:

```text
Create or open a clean AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: sashakang/aiws-skill-tests-clean

Do not edit the draft. Then validate it without activating, staging, packaging, or submitting anything.

Report validation status, modified status, status label, and whether any side effects happened.
```

Expected answer:

```text
validation status: passed
modified status: false
status label: Current
package built: no
proposal staged: no
GitHub touched: no
installed marketplace plugin files touched: no
```

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-c-unchanged-draft-validation).

## Scenario 6: Out-Of-Scope Edit Fails Closed

Purpose: confirm validation refuses draft changes outside the managed skill folder.

Prompt to Cowork:

```text
Run Scenario D through the AIWS draft-management tools only.

Create or open a disposable AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: sashakang/aiws-skill-tests-disposable

After the tool returns a draft_id and draft_path, confirm the draft_path is under ~/.aiws/plugins/.

In that returned AIWS draft only, try to make a test-only edit outside skills/meeting-followup/, for example in a contract or plugin manifest.

Then call aiws.skills.validate_draft(draft_id).

Do not create a manual /tmp copy. Do not run manual schema-only validation. Do not activate, stage, package, submit, or edit installed marketplace plugin files.
```

Expected answer:

```text
Result: PASS if either safe outcome happens

Outcome A:
write outside skills/meeting-followup/ is rejected before validation

Outcome B:
validation fails closed
last_validation_status: failed
last_validation_tree_digest: null

package built: no
proposal staged: no
GitHub touched: no
installed plugin files touched: no
```

After this scenario, discard or restore the disposable draft.

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-d-out-of-scope-edit-fails-closed).

## Scenario 7: Missing SKILL.md Fails Closed

Purpose: confirm a missing required skill entrypoint fails safely.

Prompt to Cowork:

```text
Run Scenario E through the AIWS draft-management tools only.

Create or open a disposable AIWS draft for:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: sashakang/aiws-skill-tests-disposable-missing-skill

After the tool returns a draft_id and draft_path, confirm the draft_path is under ~/.aiws/plugins/.

In that returned AIWS draft only, temporarily remove or rename:

skills/meeting-followup/SKILL.md

Then call aiws.skills.validate_draft(draft_id).

Do not activate, stage, package, submit, or edit installed marketplace plugin files.
```

Expected answer:

```text
tool result: error
reason includes missing SKILL.md
last_validation_status: failed
last_validation_tree_digest: null
package built: no
proposal staged: no
GitHub touched: no
installed plugin files touched: no
```

After this scenario, discard or restore the disposable draft.

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-e-missing-skill-fails-closed).

## Scenario 8: Prepare Cowork Package And Activation Handoff

Purpose: confirm `activate_draft` builds a package and records pending upload or handoff state without claiming Cowork activation.

Chat/session rule: run this in the same Cowork chat as Scenario 3 and Scenario 4, using the modified `draft_id` from that chat. Do not start a new chat for this scenario unless you first reopen the same draft and confirm it is still modified and valid.

Prompt to Cowork:

```text
Activate the draft for Cowork using the supported package-upload path.

Use:
draft_id: <modified draft_id>
host_kind: cowork
package_output_dir: ~/.aiws/tmp/cowork-phase2-packages

Do not directly mutate Cowork runtime files.
Do not edit installed marketplace plugin files.
Do not stage a proposal.
Do not create a GitHub branch or PR.
Do not touch ~/.claude.

Report:
- activation status
- activation_status
- activation_effective
- requires_manual_upload
- requires_cowork_confirmation, if returned
- package_path
- copied_package_path, if returned
- activation_record_path
- host_id
- whether the pending upload record is under ~/.aiws/state/draft-activations/<host-id>/<draft_id>.json
- whether installed plugin files, ~/.claude, Cowork runtime files, proposals, or GitHub were touched
```

Expected answer:

```text
status: host_capability_missing
activation_status: pending_upload
activation_effective: false
requires_manual_upload: true
package_path: ~/.aiws/tmp/cowork-phase2-packages/<draft_id>.zip
activation_record_path: ~/.aiws/state/draft-activations/<host-id>/<draft_id>.json
installed plugin files touched: no
~/.claude touched: no
Cowork runtime files directly mutated: no
proposal staged: no
GitHub touched: no
```

Alternative expected answer when Cowork has a safe package-upload surface available:

```text
status: handoff_prepared
activation_status: pending_upload
activation_effective: false
requires_manual_upload: false
requires_cowork_confirmation: true
package_path: ~/.aiws/tmp/cowork-phase2-packages/<draft_id>.zip
copied_package_path: <Cowork package_uploads>/<draft_id>.zip
activation_record_path: ~/.aiws/state/draft-activations/<host-id>/<draft_id>.json
installed plugin files touched: no
~/.claude touched: no
Cowork runtime files directly mutated: no
proposal staged: no
GitHub touched: no
```

`handoff_prepared` is not `active`. It means AIWS copied the package to a Cowork package-upload surface, but Cowork has not yet confirmed that the modified skill is visible and callable. If `core-aiws` 0.3.20 still returns `host_capability_missing`, record it as a fallback-path PASS when the package and pending-upload record are produced safely.

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-f-activation-technical-pilot-check).

## Scenario 9: Manual Upload Of Modified Draft Package

Purpose: confirm the package produced by Scenario 8 can be installed through Cowork's supported upload UI.

Chat/session rule: upload the package first, then start a new Cowork chat for the verification prompt. The new chat is deliberate: it checks whether Cowork exposes the uploaded package and skill after plugin loading refreshes.

Cowork UI path:

```text
Settings -> Plugins -> Add plugin -> Upload a file
```

Upload the `package_path` returned by Scenario 8. Then start a new Cowork chat.

Prompt to Cowork:

```text
Check whether the uploaded modified `aiws-productivity` package is installed and whether `meeting-followup` is visible.

Then invoke meeting-followup on this test input:

Decision: Validate pending-upload draft activation.
Alice will send the revised notes by Friday.
Ben will review them.

Report:
- whether the uploaded package is installed
- whether meeting-followup is visible
- whether meeting-followup runs successfully
- whether the output reflects the updated instruction that follow-up messages should be clear and concise
```

Expected answer:

```text
uploaded package installed: yes
meeting-followup visible: yes
meeting-followup runs successfully: yes
updated instruction reflected: yes
```

If `meeting-followup` appears twice, record it. That means Cowork has both the marketplace package and uploaded package installed; it does not prove AIWS can replace the active plugin in place. This is a PASS for the technical-pilot upload bridge, but it is a product gap for the final regular-user activation experience. If AIWS metadata cannot resolve a skill that the Cowork Skill invocation system can run, record that as a registry-alignment caveat.

Latest evidence: [Cowork Modified Draft Upload Report](./cowork-modified-draft-upload-report-2026-05-15.md) and [Cowork Activation Handoff 0.3.9 Runtime Report](./cowork-activation-handoff-039-runtime-report-2026-05-15.md).

## Scenario 9A: Inspect Installed Skill Copies

Purpose: confirm AIWS can tell whether Cowork has zero, one, or multiple installed copies of the same logical skill before AIWS tries to manage it.

Run this in a Cowork chat after updating `core-aiws` to `0.3.20` or later.

Prompt to Cowork:

```text
Inspect installed copies of this AIWS skill:

plugin_id: aiws-productivity
skill_id: meeting-followup

Use aiws.skills.inspect_installed_skill if it is available.

Do not create or edit a draft.
Do not activate anything.
Do not stage or submit a proposal.
Do not touch GitHub, ~/.claude, memory, or Cowork runtime files.

Report:
- status
- instance_count
- selected_instance, if any
- whether duplicate installed copies were found
- whether anything was mutated
```

Expected answer when there is one installed copy:

```text
status: ok
instance_count: 1
selected_instance: present
duplicate installed copies: no
mutated anything: no
```

Expected answer when duplicate copies exist:

```text
status: duplicate_visible_identity
instance_count: 2 or more
selected_instance: null
duplicate installed copies: yes
mutated anything: no
```

If the tool is not available, update `core-aiws` from the marketplace and start a new Cowork chat before retesting.

Latest evidence: [Cowork Installed Skill Inspection PASS](./cowork-installed-skill-inspection-pass-2026-05-15.md).

## Scenario 10: Deactivate Pending Upload Marker

Purpose: confirm pending-upload cleanup only clears AIWS state and does not remove Cowork-uploaded plugins or draft edits.

Prompt to Cowork:

```text
Deactivate the draft pending-upload state for:

draft_id: <draft_id from Scenario 8>
host_kind: cowork

This should only clear the AIWS pending-upload record. It must not remove the Cowork-uploaded plugin, delete the package ZIP, revert draft edits, touch GitHub, or touch ~/.claude.

Report:
- status
- activation_status
- cleared
- whether package_path still exists
- whether draft remains modified
- whether Cowork-uploaded plugin was removed
```

Expected answer:

```text
status: deactivated
activation_status: inactive
cleared: true
package_path still exists: yes
draft remains modified: yes
Cowork-uploaded plugin removed: no
GitHub touched: no
~/.claude touched: no
```

If the package ZIP cannot be checked because the test runs from a sandbox that cannot see the Mac package path, record that as an evidence caveat, not as a failure. The critical pass condition is that AIWS pending-upload state is cleared while draft edits and Cowork-uploaded plugin state remain untouched.

Latest evidence: [Cowork Pending Upload Deactivation Report](./cowork-pending-upload-deactivation-report-2026-05-15.md).

## Scenario 10A: Revert Stale Draft Records

Purpose: clean up stale AIWS draft records after drift-protection testing, while keeping one intentional draft.

Use this only when you have an explicit keep list and an explicit revert list. Do not ask Cowork to decide which draft matters. If there is any doubt, refresh the draft and report it instead of reverting it.

Prompt to Cowork:

```text
Clean up stale AIWS drafts for:

plugin_id: aiws-productivity
skill_id: meeting-followup

Keep this draft_id and do not modify or revert it:
<draft_id to keep>

Revert only these stale draft_ids:
- <stale draft_id 1>
- <stale draft_id 2>
- <stale draft_id 3>

For each stale draft_id:
1. Call aiws.skills.refresh_draft first and report whether it exists.
2. If it exists and is not the keep draft, call aiws.skills.revert_draft.
3. If revert_draft is not available, stop and report BLOCKED. Do not delete files manually.

Do not touch installed plugin files, Cowork RPM/runtime files, ~/.claude, memory, packages, proposals, GitHub branches, commits, pushes, or PRs.

After cleanup, try to create or open this draft without allow_parallel_draft:

plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: sashakang/aiws-skill-tests-drift-check

Expected behavior:
- If the keep draft still exists, create_or_open_draft should still fail closed because one active draft remains.
- If no active draft remains, create_or_open_draft may create a new draft.

Report:
- kept draft_id
- reverted draft_ids
- draft_ids that were already missing
- any errors
- whether create_or_open_draft still failed closed or created a new draft
- whether installed plugin files were touched
- whether GitHub was touched
```

Expected answer when one keep draft remains:

```text
status: PASS
kept draft_id: <draft_id to keep>
reverted draft_ids: <stale IDs only>
already missing: <IDs if any>
create_or_open_draft after cleanup: failed closed
reason: existing active draft
installed plugin files touched: no
GitHub touched: no
manual filesystem deletion: no
```

For the 2026-05-15 drift-protection test, the draft currently recommended to keep is `aiws-productivity--meeting-followup--25bf8e1a23`, because it produced the successful regular-user proposal and PR #4. Treat that as test evidence, not a universal rule.

Latest evidence: [Cowork Stale Draft Cleanup PASS](./cowork-stale-draft-cleanup-pass-2026-05-15.md).

## Scenario 11: Stage Proposal Without Submitting

Purpose: confirm staging writes only a local proposal record.

Prompt to Cowork:

```text
Stage the validated AIWS draft as a proposal, but do not submit it for review yet.

draft_id: <modified draft_id>
target_scope: Personal test skills
target_repo: <test review repository>
summary: Test update to meeting-followup
rationale: Validate the Cowork Phase 2 skill proposal flow.

Staging must create only a local proposal record. Do not create a branch, commit, push, pull request, package, or Cowork runtime mutation.
```

Expected answer:

```text
status: staged
next_action: submit_for_review
proposal_id: <proposal_id>
branch created: no
commit created: no
push: no
pull request: no
package built: no
Cowork runtime mutation: no
```

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-g-stage-proposal-without-submitting).

Latest evidence: [Cowork Proposal Submit Report](./cowork-proposal-submit-report-2026-05-15.md).

Latest 0.3.13 evidence: [Cowork Inspected Draft Proposal Submit PASS](./cowork-inspected-draft-proposal-submit-pass-2026-05-15.md).

## Scenario 12: Submit Proposal For Review

Purpose: confirm staged proposals can be submitted or handed off safely.

Prompt to Cowork:

```text
Submit this staged AIWS proposal for review using only the allowed test repository.

proposal_id: <proposal_id from Scenario 11>
allowed_target_repos:
- <test review repository>

If the stored target repository is not in allowed_target_repos, fail closed. Do not submit anywhere else.
```

Expected answer when a real submitter is available:

```text
status: submitted_for_review
target_repo: <test review repository>
branch_name: aiws/skill-proposals/<proposal_id>
pr_url: <review PR URL>
post_merge_delivery.status: marketplace_update_required_after_merge
post_merge_delivery.normal_user_manual_zip_upload_required: false
normal Cowork reviewer-role metadata: omitted
```

Expected answer when no Cowork-compatible submitter is available:

```text
status: submit_handoff_required
proposal_id: <proposal_id>
target_repo: <test review repository>
branch_name: aiws/skill-proposals/<proposal_id>
terminal: false
no_pr_created: true
proposal remains staged: yes
post_merge_delivery.status: marketplace_update_required_after_merge
post_merge_delivery.normal_user_manual_zip_upload_required: false
```

Negative repository-guard prompt:

```text
Test the submit-for-review repository guard for this staged proposal.

proposal_id: <proposal_id from Scenario 11>
allowed_target_repos:
- <different test repository that is not the proposal target_repo>

This must fail closed because the proposal's stored target_repo is not allowed. Do not create a branch, commit, push, pull request, package, or Cowork runtime mutation.
```

Expected answer:

```text
tool result: error
reason: target_repo is not allowed
branch created: no
commit created: no
push: no
pull request: no
package built: no
Cowork runtime mutation: no
```

If a proposal was accidentally staged with the literal placeholder `<test review repository>`, the repository guard must block submit when the allowlist contains the real repository. Record this as a guard PASS and re-stage with the real target repo before testing successful submit.

Source: [Cowork Skills-Management Phase 2 Test Plan](./cowork-skills-management-phase2-test-plan.md#scenario-h-submit-for-review-optional-and-guarded), [Regular User Draft Submit Report](./cowork-regular-user-draft-submit-report-2026-05-14.md), and [Cowork Proposal Submit Report](./cowork-proposal-submit-report-2026-05-15.md).

Latest 0.3.13 evidence: [Cowork Inspected Draft Proposal Submit PASS](./cowork-inspected-draft-proposal-submit-pass-2026-05-15.md).

## Scenario 12A: Post-Merge Marketplace Delivery Guidance

Purpose: confirm the normal user path does not ask users to activate local ZIP packages after a proposal is submitted. The updated skill reaches Cowork through marketplace update/sync after maintainer merge.

Status: implemented and runtime-tested in `core-aiws` 0.3.16.

Prompt to Cowork after Scenario 12 succeeds:

```text
Report the post-merge delivery guidance from the submitted proposal response.

Confirm:
1. The regular user is not asked to manually upload a ZIP.
2. The normal path is maintainer review and merge, followed by Cowork marketplace update/sync.
3. Manual same-name ZIP upload is only a maintainer/admin path for manual marketplaces.
4. Local package activation is only a technical-pilot fallback, not the regular user path.
5. No duplicate visible skill copies are expected in the normal path.
```

Expected behavior:

```text
regular user action: submit proposal for review
maintainer action: review and merge
delivery path:
- GitHub-synced marketplace: trigger Cowork marketplace update/sync or rely on automatic sync if enabled
- manual marketplace: maintainer/admin uploads a new ZIP with the same plugin name
regular user manual ZIP upload: no
local package activation: fallback/technical pilot only
duplicate visible skill copies: not acceptable in the normal path
```

Latest evidence: [Cowork Post-Merge Delivery Guidance PASS](./cowork-post-merge-delivery-guidance-pass-2026-05-15.md).

## Scenario 12B: Non-CLI GitHub Submitter

Purpose: confirm AIWS no longer requires host `gh` when a host-provided GitHub token is configured.

Status: implemented and runtime-tested in `core-aiws` 0.3.17.

Automated verification from the repo root:

```bash
python -m unittest \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_github_api_submitter_creates_branch_commit_and_pr_without_gh \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_github_api_submitter_no_changes_keeps_proposal_staged \
  tests.test_aiws_mcp.AiwsMcpSkillTests.test_cowork_runtime_submit_for_review_prefers_github_api_submitter_when_token_exists
```

Expected result:

```text
Ran 3 tests
OK
```

Runtime Cowork prompt, only after the host has a GitHub token configured for AIWS:

```text
Submit this staged AIWS proposal for review using the configured GitHub API submitter if available.

proposal_id: <proposal_id from Scenario 11>
allowed_target_repos:
- <test review repository>

Before submitting, revalidate the draft and confirm the digest gate passes.
Report whether a PR was created, branch_name, pr_url, post_merge_delivery, and whether host gh was required.
```

Expected behavior:

```text
status: submitted_for_review
branch_name: aiws/skill-proposals/<proposal_id>
pr_url: <review PR URL>
host gh required: no
normal user token paste required: no
post_merge_delivery.status: marketplace_update_required_after_merge
```

If no host token is configured, the runtime may still use `gh` as a technical-pilot fallback or return `submit_handoff_required`. That is not a failure of the API submitter; it means the host credential path has not been configured for Cowork yet.

Latest evidence: [Cowork GitHub API Submitter PASS](./cowork-github-api-submitter-pass-2026-05-15.md).

## Scenario 12C: Repository Review Policy Visibility

Purpose: confirm Cowork submit results report repository-owned review policy without asking the normal user to choose GitHub reviewers.

Status: implemented and runtime-tested in `core-aiws` 0.3.18 and later for a repository without CODEOWNERS.

Automated verification from the repo root:

```bash
python -m unittest \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_gh_submitter_syncs_only_skill_folder_and_creates_non_draft_pr_without_reviewers \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_gh_submitter_reuses_existing_pr_only_after_refreshing_body_and_marking_ready \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_github_api_submitter_creates_branch_commit_and_pr_without_gh
```

Expected result:

```text
Ran 3 tests
OK
```

Runtime Cowork prompt after Scenario 12 or 12B succeeds:

```text
Report the repository review policy metadata from the submitted proposal response.

Confirm:
1. repository_review_policy is present.
2. repository_review_policy.status is one of present, absent, or unknown.
3. repository_review_policy.codeowners is reported if known.
4. normal_user_selects_reviewers is false.
5. No required_review_roles or hardcoded AI engineer reviewer metadata is emitted in the normal Cowork flow.
6. Missing CODEOWNERS is reported as a caveat, not as a submit blocker.
```

Expected behavior for a repository without CODEOWNERS:

```text
repository_review_policy.status: absent
repository_review_policy.codeowners: not_detected
repository_review_policy.normal_user_selects_reviewers: false
submit blocked because CODEOWNERS missing: no
```

Expected behavior for a repository where CODEOWNERS is detected:

```text
repository_review_policy.status: present
repository_review_policy.codeowners: detected
repository_review_policy.normal_user_selects_reviewers: false
```

Latest evidence: [Cowork Repository Review Policy PASS](./cowork-repository-review-policy-pass-2026-05-16.md).

## Scenario 13: Cowork Package Intake Probe

Purpose: test whether Cowork automatically consumes files copied to the `package_uploads` surface. This scenario must use a disposable probe plugin only.

From the repo root:

```bash
python -m scripts.cowork_package_intake_probe \
  --host-id <existing-cowork-host-id>
```

Expected command answer:

```json
{
  "status": "package_copied_to_upload_surface",
  "plugin_id": "aiws-cowork-package-intake-probe-<yyyymmddhhmmss>",
  "skill_id": "intake-probe",
  "probe_marker": "AIWS_COWORK_PACKAGE_INTAKE_PROBE_LOADED aiws-cowork-package-intake-probe-<yyyymmddhhmmss>",
  "cowork_install_confirmation": "unavailable_until_new_cowork_chat_checks_visibility",
  "reuse_allowed": false
}
```

Then start a new Cowork chat. Do not use `Settings -> Plugins -> Upload a file`.

Prompt to Cowork:

```text
Check whether this disposable probe plugin or skill is visible:

plugin_id: <plugin_id returned by the probe command>
skill_id: intake-probe

If it is visible, invoke intake-probe and report whether the output contains this marker:

<probe_marker returned by the probe command>

Do not manually upload any ZIP. Do not install anything through Settings. Report whether Cowork consumed the package automatically.
```

Expected answer if automatic intake works:

```text
result: cowork_install_confirmed
probe plugin visible: yes
intake-probe callable: yes
marker returned: yes
cleanup required: remove or disable the probe plugin through Cowork plugin settings
```

Expected answer if automatic intake is not observed:

```text
result: no_automatic_intake_observed
probe plugin visible: no
intake-probe callable: no
manual upload used: no
```

If Cowork cannot determine visibility, record:

```text
result: cowork_install_confirmation_unavailable
```

Source: [AIWS Cowork Phase 2B Runtime Plan](./aiws-cowork-phase2b-runtime-plan.md#slice-2b8a-cowork-package-intake-probe).

## Scenario 14: Hosted / Uploaded MCP Smoke Experiments

Purpose: preserve evidence about Cowork MCP runtime shapes. These are diagnostic experiments, not the normal user path.

Current expected answer:

```text
Uploaded-plugin stdio MCP smoke: BLOCKED / tool not exposed
Uploaded-plugin HTTP MCP smoke: BLOCKED / tool not exposed
Supported managed/custom connector proof: future work
```

Do not treat these failures as failure of normal skill invocation. `meeting-followup` is a Cowork skill, not an MCP tool. MCP is currently used successfully for AIWS lifecycle tools exposed by `core-aiws`.

Source: [AIWS Cowork Phase 2B Runtime Plan](./aiws-cowork-phase2b-runtime-plan.md).

## Scenario 15: Marketplace Update Conflict Review And Safe Resolution

Purpose: confirm that AIWS does not silently overwrite a locally modified draft when a marketplace update is available. The user must be able to review local and remote diffs, then choose one of the safe resolution paths.

Current implementation note: Cowork-facing tools use server-owned IDs. A normal user should see `draft_id`, `update_candidate_id`, and `review_id`; they should not be asked to paste filesystem paths.

Prompt to Cowork after a marketplace/plugin update:

```text
Prepare a marketplace update candidate for this draft:

draft_id: <draft_id>

Call aiws.skills.prepare_update_candidate.

Report:
1. status
2. update_candidate_id, if one was created
3. remote_version
4. whether any filesystem paths were required from the user

Do not review or resolve the conflict yet.
Do not stage, submit, upload, or mutate installed plugin files.
```

Expected candidate answer when a newer installed plugin differs from the draft base:

```text
status: update_candidate_created
update_candidate_id: updcand_<opaque id>
filesystem paths required from user: no
```

Expected answer when the installed plugin still matches the draft base:

```text
status: no_update_available
update_candidate_id: null
```

Prompt to Cowork after an update candidate exists:

```text
Review the marketplace update conflict for this draft:

draft_id: <draft_id>
update_candidate_id: <update_candidate_id>

Call aiws.skills.review_update_conflict.

Report:
1. review_id
2. status
3. local_changed_files
4. remote_changed_files
5. local_non_skill_changed_files
6. remote_non_skill_changed_files
7. whether a pending upload exists
8. local-vs-base diff preview
9. remote-vs-base diff preview
10. the available resolver choices

Do not resolve the conflict yet.
Do not stage, submit, upload, or mutate installed plugin files.
```

Expected review answer:

```text
status: update_conflict
review_id: updrev_<opaque id>
choices:
- keep_local_draft_and_pending_package
- discard_local_changes_and_update
- submit_or_upload_first
local-vs-base diff: present
remote-vs-base diff: present
installed plugin files touched: no
Cowork runtime files touched: no
~/.claude touched: no
```

Prompt to keep the local draft:

```text
Resolve this update conflict by keeping my local draft:

review_id: <review_id>
choice: keep_local_draft_and_pending_package

Report whether anything was mutated.
```

Expected answer:

```text
status: update_skipped
mutated: false
```

Prompt to submit or upload first:

```text
Resolve this update conflict by choosing submit/upload first:

review_id: <review_id>
choice: submit_or_upload_first

Report whether anything was mutated and what the next action is.
```

Expected answer:

```text
status: submit_or_upload_first
mutated: false
next_action: submit or upload the current draft before updating
```

Prompt to discard local changes and update:

```text
Resolve this update conflict by discarding my local draft changes and updating to the remote version:

review_id: <review_id>
choice: discard_local_changes_and_update

Use clear_pending_upload=true only if the review says a pending upload exists.
Use allow_full_plugin_discard=true only if the review says there are local non-skill changes and I explicitly confirm I want to discard the whole local plugin draft.

Report:
1. status
2. whether stale-review protection passed
3. whether pending upload records were cleared
4. whether the draft is now clean
5. installed plugin files touched
6. Cowork runtime files touched
7. ~/.claude touched
```

Expected answer when all gates pass:

```text
status: discarded_local_changes_and_updated
modified: false
cleared_pending_uploads: 0 or more
installed plugin files touched: no
Cowork runtime files touched: no
~/.claude touched: no
```

Expected fail-closed answers:

```text
status: stale_review
mutated: false
```

```text
status: pending_upload_must_be_cleared
mutated: false
```

```text
status: full_plugin_discard_confirmation_required
mutated: false
```

## Automated Scenario AUTO-01: Cowork ZIP Package Builder

Purpose: confirm the fallback ZIP package builder creates the expected Cowork-importable artifacts.

Run from the repo root:

```bash
python -m unittest tests.test_cowork_packaging
```

Expected answer:

```text
Ran 6 tests
OK
```

Key expectations covered by the test:

- `core-aiws-0.3.20.zip` is produced.
- `aiws-productivity-0.2.2.zip` is produced.
- `core-aiws` package includes `.mcp.json`, `bin/aiws-mcp-launcher`, and bundled `servers/aiws-mcp`.
- `aiws-productivity` package is flat-root importable and contains `skills/meeting-followup/SKILL.md`.

## Automated Scenario AUTO-02: Cowork Package Intake Probe

Purpose: confirm the local package-intake probe builds a disposable plugin package and copies it only to the Cowork package upload surface.

Run from the repo root:

```bash
python -m unittest tests.test_cowork_package_intake_probe
```

Expected answer:

```text
Ran 5 tests
OK
```

Key expectations covered by the test:

- Probe plugin IDs are unique and disposable.
- Probe packages contain the expected `intake-probe` skill.
- Existing probe package files are not overwritten.
- Missing or wrong-kind Cowork host records are rejected.
- Symlinked upload roots and symlinked package paths are rejected.

## Automated Scenario AUTO-03: AIWS MCP Lifecycle Regression Tests

Purpose: confirm the implemented lifecycle behavior behind Cowork draft management stays stable.

Run from the repo root:

```bash
python -m unittest tests.test_aiws_mcp
```

Expected answer:

```text
OK
```

Key expectations covered by the test include draft activation requiring an explicit Cowork package output directory, deactivation clearing pending activation state, submit-for-review using the GitHub CLI submitter when `gh` is available, and submit-for-review returning a handoff result when `gh` is unavailable.

## Automated Scenario AUTO-04: Full Repository Test Suite

Purpose: run the maintained automated regression suite before pushing changes that affect runtime, packaging, contracts, or this manual.

Run from the repo root:

```bash
python -m unittest discover -s tests
```

Expected answer:

```text
OK
```

Record the number of tests run in the test report because it changes as new scenarios are automated.

## Automated Scenario AUTO-05: Marketplace Update Conflict Regression Tests

Purpose: confirm the conflict review and resolver safety gates without requiring Cowork UI access.

Run from the repo root:

```bash
python -m unittest \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_prepare_update_candidate_uses_base_snapshot_and_current_installed_plugin \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_prepare_update_candidate_reports_no_update_for_same_installed_plugin \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_prepare_update_candidate_requires_base_snapshot_for_modified_legacy_draft \
  tests.test_aiws_mcp.AiwsMcpSkillTests.test_cowork_runtime_prepares_update_candidate_from_installed_plugin \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_review_update_conflict_reports_local_and_remote_diffs_and_stores_digest_gate \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_stale_review_blocks_without_mutation \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_review_update_conflict_allows_clean_update_without_resolution_choices \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_keep_and_submit_first_are_no_ops \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_discard_adopts_remote_and_marks_draft_clean \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_pending_upload_requires_explicit_clear_and_only_clears_state \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_rejects_pending_upload_state_created_after_review \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_resolve_update_conflict_blocks_local_non_skill_discard_without_confirmation \
  tests.test_aiws_skill_manager.AiwsSkillManagerTests.test_update_candidate_validation_fails_closed_for_wrong_identity_missing_skill_and_binary
```

Expected answer:

```text
Ran 13 tests
OK
```

Key expectations covered by the test:

- Candidate preparation creates a trusted `update_candidate_id` from the installed plugin without user-supplied paths.
- Candidate preparation reports `no_update_available` when the installed plugin still matches the draft base.
- Legacy modified drafts without a base snapshot fail closed before conflict review.
- Review returns local-vs-base and remote-vs-base diff previews.
- Review records store base/current/remote digests.
- Clean updates return `update_allowed` without conflict resolver choices.
- Stale reviews fail closed without mutation.
- Keep-local and submit/upload-first are no-op choices.
- Discard replaces the draft/base with the remote candidate and marks the draft clean.
- Pending upload records block discard unless explicitly cleared.
- Pending upload state created or changed after review makes the review stale.
- Local non-skill changes require explicit full-plugin discard confirmation.
- Wrong plugin identity, missing remote skill, symlinked roots/content, and binary candidate content fail closed.

## Maintenance Checklist

When adding or changing a manual test scenario:

1. Add or update the scenario on this page.
2. Include the exact Cowork prompt or local command.
3. Include expected `PASS`, `FAIL`, and `BLOCKED` signals when they differ.
4. Link the detailed source plan or report.
5. Keep technical-pilot behavior labeled as technical-pilot behavior.
6. Do not document target-state behavior as current behavior.

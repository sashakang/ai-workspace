# Cowork Regular User Draft Submit Report

**Date:** 2026-05-14  
**Result:** PASS, with reviewer-routing caveat  
**Scope:** Regular Cowork user draft, edit, validate, stage, and submit-for-review path for `aiws-productivity:meeting-followup`.

## Summary

The regular Cowork user draft/edit/stage/submit path passed end to end. Cowork started from the installed AIWS marketplace plugins, exposed the skill-management tools, opened a draft from the installed plugin, accepted a confined draft edit, validated and staged the proposal, and submitted it to GitHub for maintainer review.

This proves the regular-user lifecycle behavior through Cowork for this scenario. It does not prove enforceable reviewer routing. The PR body included `Required review role: AI engineer`, but GitHub did not request a reviewer or team because the target repository had no CODEOWNERS or reviewer policy.

## Setup Evidence

- Marketplace `sashakang/ai-workspace` was active.
- `core-aiws@ai-workspace` was installed.
- `aiws-productivity@ai-workspace` was installed.
- `aiws-productivity:meeting-followup` was visible.
- `meeting-followup` invoked successfully.
- On Thursday, May 14, 2026, the skill correctly resolved Friday as May 15, 2026. The earlier date bug from the canonical install/use test did not recur.

Cowork reported these regular-user tools:

- `aiws_skills_create_or_open_draft`
- `aiws_skills_write_draft_file`
- `aiws_skills_stage_proposal`
- `aiws_skills_submit_for_review`

## Draft And Edit Evidence

Draft opened from the installed plugin:

- `draft_id`: `aiws-productivity--meeting-followup--de0e75a572`
- `draft_path`: `/Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-de0e75a572`
- `base_version`: `0.2.1`
- `validation`: `passed`
- `active`: `true`

The draft edit changed only `skills/meeting-followup/SKILL.md` under the draft path. It added a Date Resolution section requiring relative weekdays to be anchored to the current session date, and requiring unresolved dates to be marked unresolved rather than invented when no current date is available.

The write stayed inside the draft under `~/.aiws/plugins/...`. Installed plugin files, installed marketplace files, Cowork runtime files, and `~/.claude` were untouched.

## Stage Evidence

Validate and stage passed:

- `validation_status`: `passed`
- `modified`: `true`
- `proposal_id`: `skillprop_ed458362021141179dbdb85a9df73794`
- no package was built
- no GitHub action occurred at staging
- installed plugin files were untouched

## Submit Evidence

Submit passed:

- `status`: `submitted_for_review`
- `target_repo`: `sashakang/aiws-skill-tests`
- `branch`: `aiws/skill-proposals/skillprop_ed458362021141179dbdb85a9df73794`
- PR: <https://github.com/sashakang/aiws-skill-tests/pull/2>

The PR state was verified with `gh`:

- state: `OPEN`
- draft: `false`
- review requests: `[]`
- CODEOWNERS: `not_detected`
- PR body includes `Required review role: AI engineer`

## Caveat

Reviewer routing is metadata only in this test. AIWS correctly carried the required review role into the PR body and used deterministic branch/PR behavior, but GitHub did not enforce reviewer assignment or approval. The target repository needs CODEOWNERS, branch protection, repository rules, or an equivalent reviewer policy before AI engineer review can be treated as enforced.

Normal Cowork users should not be asked to map GitHub reviewers or teams. AIWS should continue to record required reviewer roles, detect and report missing enforcement such as `CODEOWNERS: not_detected`, and present the missing policy as a caveat until repository policy exists.


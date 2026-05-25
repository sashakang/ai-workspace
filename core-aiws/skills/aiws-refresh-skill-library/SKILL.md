---
name: aiws-refresh-skill-library
description: Refresh a Cowork-installed Drive Skill Library after Drive changed.
---

# AIWS Skill Library Refresh

Use this skill when a user wants Cowork to pick up changes that are already in a Google Drive Skill Library.

Short human prompts are enough:

```text
refresh Test Plugin
sync Test Plugin from Drive
refresh meeting-followup in Test Plugin
```

These prompts mean: the Drive library is the source of truth, and Cowork should verify the Drive files, rebuild or reinstall the plugin artifact if needed, and confirm the installed skill behavior. Do not interpret these prompts as a request to edit or improve the skill content.

If the user says `update Test Plugin skill library`, treat it as refresh/sync unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content.

## Boundaries

First action must be reading the Google Drive folder contents directly:

```text
<Drive root>/skills/<skill-id>/SKILL.md
```

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, or activation tools. Those are not part of the Phase 1 Drive Skill Library refresh path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `test-plugin` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to Drive Skill Library refresh.

Do not judge content quality, approve proposals, or resolve disagreements. Maintainer review happens before refresh, normally by comparing local Markdown copies of canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. The normal path is verification after the maintainer has already edited the canonical file.

If an Approved proposal is present and canonical already matches it, report that canonical is already in sync and continue. `Proposals/Approved/` and `Proposals/Rejected/` are optional archive/status folders, not mandatory gates.

Do not call AIWS marketplace tools, create or open drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, export bridge repositories, upload ZIPs, or change marketplace registrations. Do not use marketplace or materialization results as evidence for or against refresh.

Refresh compares the Drive Skill Library root against the installed Cowork plugin when installed content is available. If installed content already matches Drive canonical content, report that no rebuild is required. Rebuild or guide reinstall of the whole Cowork plugin artifact only when installed content differs, installed visibility is missing, or installed content cannot be confirmed.

For `Test Plugin`, any rebuilt artifact identity is still:

```text
plugin id: test-plugin
plugin display name: Test Plugin
```

Do not generate per-skill plugin identities such as `test-plugin--meeting-followup`. Do not report that a missing `plugins/` folder blocks refresh; a flat `skills/<skill-id>/SKILL.md` Drive folder is the expected Phase 1 source shape.

## Workflow

1. Identify the Drive Skill Library, usually by display name such as `Test Plugin`.
2. If a skill id is named, verify that skill; otherwise verify all skills in `skills/`.
3. Confirm canonical `skills/<skill-id>/SKILL.md` exists and validates.
4. If Submitted or Approved proposal folders are present, compare them only as evidence; do not require them.
5. Use `aiws-validate-skill-library` to validate the library and proposal structure.
6. Compare the installed Cowork plugin content when available.
7. If installed content matches Drive, report no rebuild required.
8. If installed content differs or cannot be verified, rebuild or guide reinstall of the whole Cowork plugin artifact from the Drive library root, preserving the plugin id `test-plugin` for `Test Plugin`.
9. Verify the installed plugin/container when possible. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.

## Output

Report:

```text
AIWS Skill Library Refresh: PASS|FAIL|NEEDS MANUAL ACTION

Library:
Skill(s):
Canonical SKILL.md verified: PASS|FAIL
Proposal sync evidence: PASS|FAIL|not present
Library validation: PASS|FAIL
Cowork refresh/reinstall: PASS|FAIL|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|not verified|optional
```

Use `PASS` when canonical Drive content is verified, validation passes, and Cowork installed content is either already in sync or successfully refreshed. Use `NEEDS MANUAL ACTION` when the user or host must click **Save plugin** or refresh/reinstall outside the current session. Do not fail a successful refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.

---
name: aiws-update-skill-library
description: Apply an approved Drive Skill Library proposal and verify the refreshed skill.
---

# AIWS Skill Library Update

Use this skill when a maintainer has approved a Drive Skill Library proposal by moving or copying the final proposal folder to:

```text
Proposals/Approved/<skill-id>/<proposal-id>/
```

This skill applies an already-approved proposal. It is not a review workflow.

## Boundaries

Do not judge content quality, approve proposals, or resolve disagreements. Google Drive UI owns review and approval.

Only apply:

```text
Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md
```

to:

```text
skills/<skill-id>/SKILL.md
```

Refuse to apply proposals from:

```text
Proposals/Submitted/
Proposals/Rejected/
Proposals/<skill-id>/<proposal-id>/
```

Do not apply runtime artifacts, metadata rewrites, plugin manifests, scripts, packages, ZIPs, bridge exports, GitHub pull requests, or marketplace changes.

## Workflow

1. Confirm the selected proposal path is under `Proposals/Approved/<skill-id>/<proposal-id>/`.
2. Confirm the approved proposal contains `SKILL.md`.
3. Use `aiws-validate-skill-library` to validate the library and proposal structure.
4. Replace canonical `skills/<skill-id>/SKILL.md` with the approved proposal `SKILL.md`.
5. Verify the canonical file now matches the approved proposal content.
6. Use `aiws-validate-skill-library` again after replacement.
7. Refresh or guide Cowork reimport of the Drive skill library.
8. Ask Cowork to invoke the updated skill on a small test input and verify the expected changed behavior.

If direct Drive write access is unavailable, provide exact manual copy/replace instructions and report `NEEDS MANUAL ACTION`. Do not claim the canonical file was updated until it is verified.

## Output

Report:

```text
AIWS Skill Library Update: PASS|FAIL|NEEDS MANUAL ACTION

Library:
Skill:
Proposal:
Approved proposal path:
Canonical SKILL.md updated: PASS|FAIL|NEEDS MANUAL ACTION
Library validation: PASS|FAIL
Cowork refresh/import: PASS|FAIL|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|NEEDS MANUAL ACTION
```

Use `PASS` only when the canonical file update is verified, library validation passes after the update, and Cowork-visible behavior is verified. Use `NEEDS MANUAL ACTION` when the maintainer or host must perform a Drive copy, refresh/import, or skill invocation outside the current session.

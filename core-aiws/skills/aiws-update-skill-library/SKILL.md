---
name: aiws-update-skill-library
description: Verify and refresh a Drive Skill Library after maintainer-applied changes.
---

# AIWS Skill Library Update

Compatibility alias for `aiws-refresh-skill-library`. Prefer the user-facing verb "refresh" for this lifecycle.

Use this skill after a maintainer has reviewed a submitted Drive Skill Library proposal and directly applied the accepted changes to canonical:

```text
skills/<skill-id>/SKILL.md
```

This skill verifies the maintainer-applied update and guides Cowork refresh/reinstall. It is not a review workflow and does not approve proposals.

## Natural User Prompts

Treat short human prompts as sufficient. Examples:

```text
update Test Plugin skill library
refresh Test Plugin
update meeting-followup in Test Plugin skill library
```

For these prompts, default to verification and refresh of the Drive Skill Library. Do not ask what content changes the user wants to make unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content. If the skill id is named in the prompt, use it. If only the library is named, inspect the library and verify all changed or available skills.

If a proposal folder is present and canonical already matches it, report that the canonical file is already in sync with the proposal and proceed to validation and Cowork refresh/reinstall.

## Boundaries

Do not judge content quality, approve proposals, or resolve disagreements. Maintainer review happens before this skill runs, normally by comparing local Markdown copies of the canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. The normal path is verification after the maintainer has already edited the canonical file.

If the maintainer explicitly asks this skill to apply a proposal automatically, apply mode is allowed only from:

```text
Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md
```

Apply mode must refuse:

```text
Proposals/Submitted/
Proposals/Rejected/
Proposals/<skill-id>/<proposal-id>/
```

Do not apply runtime artifacts, metadata rewrites, plugin manifests, scripts, packages, ZIPs, bridge exports, GitHub pull requests, or marketplace changes.

## Workflow

1. Confirm canonical `skills/<skill-id>/SKILL.md` exists.
2. If a Submitted proposal path is provided, compare canonical `SKILL.md` against `Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md` and report whether the accepted changes appear in canonical.
3. If an Approved proposal path is present, compare canonical `SKILL.md` against `Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md` and report whether canonical is already in sync.
4. Use `aiws-validate-skill-library` to validate the library and proposal structure.
5. Refresh or guide Cowork reimport of the Drive skill library.
6. Ask Cowork to invoke the updated skill on a small test input and verify the expected changed behavior.

If direct Drive write access is unavailable, provide exact manual copy/replace instructions and report `NEEDS MANUAL ACTION`. Do not claim the canonical file was updated until it is verified.

## Output

Report:

```text
AIWS Skill Library Update: PASS|FAIL|NEEDS MANUAL ACTION

Library:
Skill:
Proposal:
Submitted proposal path:
Canonical SKILL.md verified: PASS|FAIL|NEEDS MANUAL ACTION
Library validation: PASS|FAIL
Cowork refresh/import: PASS|FAIL|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|NEEDS MANUAL ACTION
```

Use `PASS` only when the canonical file update is verified, library validation passes after the update, and Cowork-visible behavior is verified. Use `NEEDS MANUAL ACTION` when the maintainer or host must perform a Drive copy, refresh/import, or skill invocation outside the current session.

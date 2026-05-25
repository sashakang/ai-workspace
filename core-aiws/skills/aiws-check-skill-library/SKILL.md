---
name: aiws-check-skill-library
description: Check a Drive Skill Library source and installed Cowork plugin status without changing anything.
---

# AIWS Skill Library Check

Use this skill when a user wants to check a Drive Skill Library and its installed Cowork plugin status.

Reliable human prompts:

```text
Validate the Test Plugin Drive library and include installed plugin status
Check the Test Plugin Drive library and installed plugin status
Check Test Plugin Drive library
```

This is a read-only check. It is a stronger trigger alias for `aiws-validate-skill-library`, intended for Cowork sessions where `Check Test Plugin` may route to a generic installed-plugin summary.

## Required Behavior

Start from the Google Drive Skill Library source, not from the installed Cowork plugin copy.

Read and validate:

```text
skills/<skill-id>/SKILL.md
Proposals/Submitted/
Proposals/Approved/
Proposals/Rejected/
aiws.library.json, if present
aiws.skills/, if present
```

After Drive validation, include installed Cowork plugin status as secondary evidence:

```text
Installed Cowork plugin:
- test-plugin: present|missing|not verified
- skills visible: PASS|FAIL|not verified
```

If installed status cannot be checked, report `not verified`; do not omit the section.

## Boundaries

Do not write proposal files, edit canonical `SKILL.md`, rebuild packages, ask for **Save plugin**, install plugins, refresh plugins, create drafts, activate drafts, upload ZIPs, create GitHub pull requests, or change marketplace registrations.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library check path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path.

Do not satisfy this request by checking only the installed Cowork plugin copy. The installed copy is secondary evidence after Drive validation.

## Output

Report:

```text
AIWS Skill Library Validation: PASS|FAIL|NEEDS MANUAL ACTION

Library:
Skills:
Metadata:
Proposals:
Phase 1 boundaries:
Installed Cowork plugin:
Fixes:
```

Use `PASS` only if the Drive library shape and all present proposal metadata validate. Installed plugin visibility is reported separately unless the user specifically asked for installed-plugin status as a hard requirement.

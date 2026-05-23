---
name: aiws-install-drive-skill-library
description: Install or prepare the Cowork install prompt for a Google Drive Skill Library plugin.
---

# AIWS Drive Skill Library Install

Use this skill when a user wants to install a Google Drive Skill Library in Cowork as a plugin-like container.

## Input

Collect the Google Drive folder URL.

## Install

If already running inside Cowork, treat the current user request as the install request and attempt the install now. Do not tell the user to run another prompt in the same Cowork session.

The install instruction is exactly:

```text
Install this Google Drive folder as a plugin:
<drive-folder-url>
```

Do not ask the user to type longer instructions. Do not say "install as standalone skills" or "install individual skills".

If the current host cannot perform the install directly, report `NEEDS MANUAL ACTION` and provide only the exact install instruction above.

## Verify

After the install attempt or manual install, verify:

- the Drive folder appears as a plugin/container
- the skills appear under that plugin/container
- proposal folders such as `Proposals/Submitted`, `Proposals/Approved`, and `Proposals/Rejected` are not installed as runnable skills

If Cowork installed only loose skills, report:

```text
AIWS Drive Skill Library Install: NEEDS RETRY
```

and give the same short prompt again.

## Output

Report:

```text
AIWS Drive Skill Library Install: PASS|FAIL|NEEDS RETRY

Drive folder:
Install prompt:
Plugin/container visible: PASS|FAIL|not verified
Skills visible under plugin/container: PASS|FAIL|not verified
Proposal folders ignored as skills: PASS|FAIL|not verified
```

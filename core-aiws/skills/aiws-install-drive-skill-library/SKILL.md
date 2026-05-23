---
name: aiws-install-drive-skill-library
description: Package a Google Drive Skill Library as a Cowork Save plugin artifact.
---

# AIWS Drive Skill Library Install

Use this skill when a user wants to install a Google Drive Skill Library in Cowork as a plugin-like container.

This is not a direct remote-install API. In Cowork, the working path is:

1. read the Drive folder with the Google Drive integration
2. collect `skills/<skill-id>/SKILL.md`
3. package those skills into one plugin artifact with a plugin manifest
4. present a single **Save plugin** card to the user

Do not stop after producing individual **Save skill** cards.

This flow is not an AIWS marketplace workflow. Do not call, register, inspect, or repair `aiws.marketplaces.*`, `drive_workflow`, `export_cowork_bridge`, or any marketplace registry while installing a Drive Skill Library. A flat `skills/<skill-id>/SKILL.md` Drive folder is valid even if AIWS marketplace indexing would return no results.

Do not tell the user that a `test-plugin` marketplace is empty or missing. Do not mention marketplace in the normal install report. The user-facing objects are:

- Drive Skill Library
- Cowork plugin artifact
- Save plugin card
- installed plugin/container

## Input

Collect the Google Drive folder URL.

## Package And Install

If already running inside Cowork, treat the current user request as the install request. Do not tell the user to run another prompt in the same Cowork session.

Use the Google Drive integration to read the folder URL, then package the library into one Cowork plugin artifact:

- plugin display name: the Drive root folder name, for example `Test Plugin`
- plugin id: a stable slug derived from the Drive root folder name, for example `test-plugin`
- skills: every `skills/<skill-id>/SKILL.md`
- ignored as runtime skills: `Proposals/`, `aiws.library.json`, `aiws.skills/`, and any proposal metadata

The plugin artifact must be a zip-compatible Cowork plugin package with files at the archive root:

```text
.claude-plugin/plugin.json
contracts/<plugin-id>.contract.json
skills/<skill-id>/SKILL.md
```

For `Test Plugin`, use `plugin-id` `test-plugin`. The manifest must include `name`, `description`, `version`, and `author.name`. The contract must include `plugin_id`, `version`, and `public_skills` listing exactly the packaged skill folder ids. Do not put files under an extra top-level wrapper folder inside the archive.

Do not register the Drive folder as a marketplace. Do not search AIWS marketplaces for it. Do not use missing marketplace search results as evidence that the Drive folder cannot be packaged.

Present exactly one **Save plugin** card. If the host first produces individual **Save skill** cards, say that is not the requested result and repackage the same Drive contents as a plugin.

The user-facing fallback prompt, only when a separate Cowork prompt is unavoidable, is exactly:

```text
Install this Google Drive folder as a plugin:
<drive-folder-url>
```

Do not ask the user to type longer instructions. Do not say "install as standalone skills" or "install individual skills".

If the current host cannot read the Drive folder or cannot produce a **Save plugin** artifact, report `NEEDS MANUAL ACTION` and provide the exact fallback prompt above.

## Verify

After the Save plugin step or manual install, verify:

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
AIWS Drive Skill Library Install: PASS|FAIL|NEEDS RETRY|NEEDS MANUAL ACTION

Drive folder:
Install prompt:
Plugin artifact generated: PASS|FAIL|NEEDS MANUAL ACTION
Plugin artifact layout valid: PASS|FAIL|not verified
Save plugin completed: PASS|FAIL|not verified
Plugin/container visible: PASS|FAIL|not verified
Skills visible under plugin/container: PASS|FAIL|not verified
Proposal folders ignored as skills: PASS|FAIL|not verified
```

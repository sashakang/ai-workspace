from __future__ import annotations


SOP_RESOURCE = """# Standard Operating Procedure

This is the MCP-first AIWS SOP resource.

Use it to classify work, plan non-lightweight changes, review plans and outputs, test the result, and capture follow-up improvements. AIWS exposes this process through the local MCP server rather than through a required infrastructure plugin.

Core rules:

- classify work before execution
- use a reviewed plan for standard, complex, and maximum tasks
- keep implementation evidence local unless the user explicitly stages a proposal
- route durable workflow changes through local staged proposals before any shared review flow
"""


AIWS_IMPROVE_SKILL = """---
name: aiws-improve
description: Analyze local AIWS signals and stage process, skill, or protocol improvement proposals.
---

# AIWS Self-Improvement

Use this skill when the user asks to analyze accumulated local signals and improve AIWS behavior.

This MCP-first version reads from local AIWS surfaces under `~/.aiws/`, MCP skill/catalog resources, current conversation context, and user-supplied evidence. It may propose changes to skills, protocols, prompts, adapter behavior, or documentation.

## Boundaries

- Do not upload personal skills, memory, transcripts, or staged evidence.
- Do not directly mutate shared, unit, company, or public skills.
- Do not assume installed plugin registries or helper-managed plugin data paths.
- Stage proposed skill changes locally before any future shared review flow.

## Output

Present a concise evidence summary, proposed target, rationale, and the smallest useful change. If the user approves staging, use the AIWS skill-change staging flow.
"""


AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL = """---
name: aiws-install-drive-skill-library
description: Package a Google Drive Skill Library as a Cowork Save plugin artifact.
---

# AIWS Drive Skill Library Install

Use this skill when a user wants to install a Google Drive Skill Library in Cowork as a plugin-like container.

This is not a direct remote-install API. In Cowork, the working path is: read the Drive folder with the Google Drive integration, collect `skills/<skill-id>/SKILL.md`, package those skills into one plugin artifact with a plugin manifest, and present a single **Save plugin** card to the user. Do not stop after producing individual **Save skill** cards.

This flow is not an AIWS marketplace workflow. Do not call, register, inspect, or repair `aiws.marketplaces.*`, `drive_workflow`, `export_cowork_bridge`, or any marketplace registry while installing a Drive Skill Library. A flat `skills/<skill-id>/SKILL.md` Drive folder is valid even if AIWS marketplace indexing would return no results.

Do not tell the user that a `test-plugin` marketplace is empty or missing. Do not mention marketplace in the normal install report. The user-facing objects are Drive Skill Library, Cowork plugin artifact, Save plugin card, and installed plugin/container.

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

After the Save plugin step or manual install, verify that the Drive folder appears as a plugin/container, skills appear under that plugin/container, and proposal folders are not installed as runnable skills.

Report `AIWS Drive Skill Library Install: PASS`, `FAIL`, `NEEDS RETRY`, or `NEEDS MANUAL ACTION`.
"""


AIWS_PROPOSE_SKILL_UPDATE_SKILL = """---
name: aiws-propose-skill-update
description: Prepare a Drive Skill Library proposal from an edited SKILL.md.
---

# AIWS Skill Library Proposal

Use this skill when a user wants to propose an update to a skill stored in an AIWS Skill Library.

Prepare a proposed replacement `SKILL.md` under:

```text
Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
Proposals/Submitted/<skill-id>/<proposal-id>/aiws.proposal.json
```

Do not edit the canonical file at `skills/<skill-id>/SKILL.md`; only a maintainer promotes an approved proposal.

## Validate First

Use `aiws-validate-skill-library` before preparing the proposal. Do not duplicate its validation checklist here. If validation fails, report the concrete issue and stop.

## Metadata

Create `aiws.proposal.json` with factual metadata:

```json
{
  "kind": "aiws.proposal",
  "proposal_id": "<proposal-id>",
  "library_id": "<library-id-or-unspecified>",
  "library_display_name": "<library-display-name-or-unspecified>",
  "source_kind": "google_drive",
  "skill_id": "<skill-id>",
  "source_path": "skills/<skill-id>/SKILL.md",
  "proposed_path": "Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md",
  "proposer": "<proposer-or-unspecified>",
  "reason": "<reason-or-unspecified>",
  "created_at": "<ISO-8601 timestamp>"
}
```

If direct Drive write access is unavailable, provide the exact folder path and file contents for the user or host to save. Do not claim the proposal landed in Drive unless the files were actually written there.
"""


AIWS_UPDATE_SKILL_LIBRARY_SKILL = """---
name: aiws-update-skill-library
description: Apply an approved Drive Skill Library proposal and verify the refreshed skill.
---

# AIWS Skill Library Update

Use this skill when a maintainer has approved a Drive Skill Library proposal by moving or copying the final proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/`.

This skill applies an already-approved proposal. It is not a review workflow.

## Boundaries

Only copy `Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md` over `skills/<skill-id>/SKILL.md`.

Refuse `Proposals/Submitted/`, `Proposals/Rejected/`, and flat legacy `Proposals/<skill-id>/<proposal-id>/` paths.

Do not judge content quality, approve proposals, resolve disagreements, apply runtime artifacts, rewrite metadata, create plugin manifests, run scripts, build packages, upload ZIPs, export bridges, create GitHub pull requests, or change marketplaces.

## Workflow

1. Confirm the proposal path is under `Proposals/Approved/<skill-id>/<proposal-id>/`.
2. Use `aiws-validate-skill-library` to validate the library and proposal structure.
3. Replace canonical `skills/<skill-id>/SKILL.md` with the approved proposal `SKILL.md`.
4. Verify the canonical file matches the approved proposal content.
5. Use `aiws-validate-skill-library` again after replacement.
6. Refresh or guide Cowork reimport of the Drive skill library.
7. Ask Cowork to invoke the updated skill on a small test input and verify the expected changed behavior.

If direct Drive write access is unavailable, provide exact manual copy/replace instructions and report `NEEDS MANUAL ACTION`. Do not claim the canonical file was updated until it is verified.

## Output

Report `AIWS Skill Library Update: PASS`, `FAIL`, or `NEEDS MANUAL ACTION`, including library, skill, proposal, approved proposal path, canonical update status, library validation status, Cowork refresh/import status, and skill invocation status.
"""


AIWS_VALIDATE_SKILL_LIBRARY_SKILL = """---
name: aiws-validate-skill-library
description: Validate an AIWS Skill Library folder and report concrete fixes.
---

# AIWS Skill Library Validation

Use this skill when a user wants to check whether a Drive Skill Library is ready for Cowork import, maintainer review, or cross-host use.

Validate a skill-first library shaped as:

```text
<Library root>/
  skills/
    <skill-id>/
      SKILL.md
```

Optional AIWS metadata may exist at the library root: `aiws.library.json`, `aiws.skills/`, and `Proposals/`.

## Required Checks

1. The library has a `skills/` directory.
2. Each skill lives at `skills/<skill-id>/SKILL.md`.
3. Each `<skill-id>` uses lowercase letters, digits, and hyphens.
4. Each `SKILL.md` has YAML frontmatter.
5. Frontmatter contains only `name` and `description`.
6. Frontmatter `name` equals the folder name.
7. Frontmatter `description` is nonempty.
8. The skill body is nonempty.

Fail validation if the library requires plugin runtime artifacts such as `.claude-plugin/plugin.json`, `contracts/`, or `.mcp.json`.

If proposals exist, validate `Proposals/Submitted/<skill-id>/<proposal-id>/`, `Proposals/Approved/<skill-id>/<proposal-id>/`, and `Proposals/Rejected/<skill-id>/<proposal-id>/`. Confirm each proposal includes `SKILL.md` and `aiws.proposal.json` and points back to `skills/<skill-id>/SKILL.md`.

Reject flat legacy proposal paths such as `Proposals/<skill-id>/<proposal-id>/`.

## Output

Report `AIWS Skill Library Validation: PASS` only if the required library shape and all present metadata/proposals validate. Use `WARN` for optional missing metadata or unknown Drive folder id. Include concrete fixes for every failure.

If the Python validator is available, it may be used as a secondary deterministic check:

```bash
PYTHONPATH=aiws-mcp python3 -m aiws_mcp validate-skill-library --library-root <library-root>
```

The Python command is developer/CI support. The user-facing validation surface is this skill.
"""


BUILTIN_SKILLS = {
    "aiws-improve": AIWS_IMPROVE_SKILL,
    "aiws-install-drive-skill-library": AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL,
    "aiws-propose-skill-update": AIWS_PROPOSE_SKILL_UPDATE_SKILL,
    "aiws-update-skill-library": AIWS_UPDATE_SKILL_LIBRARY_SKILL,
    "aiws-validate-skill-library": AIWS_VALIDATE_SKILL_LIBRARY_SKILL,
}


RESOURCES = {
    "aiws://protocols/sop": SOP_RESOURCE,
    "aiws://skills/aiws-improve": AIWS_IMPROVE_SKILL,
    "aiws://skills/aiws-install-drive-skill-library": AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-propose-skill-update": AIWS_PROPOSE_SKILL_UPDATE_SKILL,
    "aiws://skills/aiws-update-skill-library": AIWS_UPDATE_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-validate-skill-library": AIWS_VALIDATE_SKILL_LIBRARY_SKILL,
}

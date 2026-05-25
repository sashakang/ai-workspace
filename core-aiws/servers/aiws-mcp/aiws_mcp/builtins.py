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

Before presenting the **Save plugin** card, inspect the generated archive and verify `.claude-plugin/plugin.json`, `contracts/test-plugin.contract.json`, and the packaged `skills/<skill-id>/SKILL.md` files exist at archive root, no wrapper folder exists, manifest and contract ids/versions match, contract `public_skills` equals the packaged skill folder ids, each `SKILL.md` has only `name` and `description` frontmatter, each skill name exactly matches its folder id, and each skill body is non-empty. If any preflight check fails, do not present the card; fix the artifact or report `AIWS Drive Skill Library Install: FAIL` with the exact failing file and field.

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

Report `AIWS Drive Skill Library Install: READY FOR SAVE`, `PASS`, `FAIL`, `NEEDS RETRY`, or `NEEDS MANUAL ACTION`. Use `READY FOR SAVE` when the plugin card is generated and preflighted but the user has not clicked **Save plugin** yet. Use `PASS` only after Cowork accepts the plugin and the installed plugin/container and skills are verified. If Cowork reports `Plugin validation failed`, inspect and report the generated archive entries, manifest JSON, contract JSON, packaged skill frontmatter, and exact Cowork error text if available.
"""


AIWS_PROPOSE_SKILL_UPDATE_SKILL = """---
name: aiws-propose-skill-update
description: Prepare a Drive Skill Library proposal from an edited SKILL.md.
---

# AIWS Skill Library Proposal

Use this skill when a user wants to propose an update to a skill stored in an AIWS Skill Library.

Short human prompts are enough: `propose a meeting-followup update for Test Plugin`, `propose this meeting-followup change for Test Plugin: change the marker line to > meeting-followup update`, and `submit a morning-briefing proposal for Test Plugin`.

These prompts mean: find the Drive Skill Library, read the canonical skill, collect or infer the proposed change, and write a proposal under `Proposals/Submitted/`. Do not interpret them as a request to edit canonical `skills/<skill-id>/SKILL.md`.

First action should be locating and reading the Drive Skill Library contents directly: `<Drive root>/skills/<skill-id>/SKILL.md`.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library proposal path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `test-plugin` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to proposal submission.

Do not create drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, create plugin manifests, upload ZIPs, rebuild Cowork packages, or change marketplace registrations.

Prepare a proposed replacement `SKILL.md` under:

```text
Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
Proposals/Submitted/<skill-id>/<proposal-id>/aiws.proposal.json
```

Do not edit the canonical file at `skills/<skill-id>/SKILL.md`; only a maintainer changes canonical skill content.

Ask for missing information only when the proposal cannot be written safely. Prefer one concise question over a multi-step form.

After writing the proposal, give the maintainer a simple local Markdown diff path. Do not rely on Google Docs compare. Recommend VS Code/VSCodium (`code --diff skills/<skill-id>/SKILL.md Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md`) or Meld (`meld skills/<skill-id>/SKILL.md Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md`). If the files are only in Google Drive, tell the maintainer to open or sync local copies first. After review, the maintainer applies accepted changes directly to `skills/<skill-id>/SKILL.md`. Moving or copying the proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/` or `Proposals/Rejected/<skill-id>/<proposal-id>/` is optional recordkeeping, not a required gate.

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
description: Verify and refresh a Drive Skill Library after maintainer-applied changes.
---

# AIWS Skill Library Update

Compatibility alias for `aiws-refresh-skill-library`. Prefer the user-facing verb "refresh" for this lifecycle.

Use this skill after a maintainer has reviewed a submitted Drive Skill Library proposal and directly applied the accepted changes to canonical `skills/<skill-id>/SKILL.md`.

This skill verifies the maintainer-applied update and guides Cowork refresh/reinstall. It is not a review workflow and does not approve proposals.

Treat short human prompts as sufficient. `update Test Plugin skill library`, `refresh Test Plugin`, and `update meeting-followup in Test Plugin skill library` mean verify/refresh the library by default. Do not ask what content changes the user wants to make unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content. If a proposal folder is present and canonical already matches it, report that canonical is already in sync with the proposal and proceed to validation and Cowork refresh/reinstall. If installed Cowork content already matches Drive canonical content, report that no rebuild is required.

## Boundaries

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. If apply mode is explicitly requested, it is allowed only from `Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md` and must refuse `Proposals/Submitted/`, `Proposals/Rejected/`, and flat legacy `Proposals/<skill-id>/<proposal-id>/` paths.

Do not judge content quality, approve proposals, resolve disagreements, apply runtime artifacts, rewrite metadata, create plugin manifests, run scripts, build packages, upload ZIPs, export bridges, create GitHub pull requests, or change marketplaces. Maintainer review happens before this skill runs, normally by comparing local Markdown copies of the canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

## Workflow

1. Confirm canonical `skills/<skill-id>/SKILL.md` exists.
2. If a Submitted proposal path is provided, compare canonical `SKILL.md` against `Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md` and report whether the accepted changes appear in canonical.
3. If an Approved proposal path is present, compare canonical `SKILL.md` against `Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md` and report whether canonical is already in sync.
4. Use `aiws-validate-skill-library` to validate the library and proposal structure.
5. Refresh or guide Cowork reimport of the Drive skill library, following `aiws-refresh-skill-library` semantics: compare installed Cowork plugin content when available, report no rebuild required if installed content matches Drive, and rebuild or guide reinstall only when installed content differs or cannot be verified.
6. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.

If direct Drive write access is unavailable, provide exact manual copy/replace instructions and report `NEEDS MANUAL ACTION`. Do not claim the canonical file was updated until it is verified.

## Output

Report `AIWS Skill Library Update: PASS`, `FAIL`, or `NEEDS MANUAL ACTION`, including library, skill, submitted proposal path if provided, canonical verification status, library validation status, Cowork refresh/import status, and skill invocation status. Do not fail a successful update/refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.
"""


AIWS_REFRESH_SKILL_LIBRARY_SKILL = """---
name: aiws-refresh-skill-library
description: Refresh a Cowork-installed Drive Skill Library after Drive changed.
---

# AIWS Skill Library Refresh

Use this skill when a user wants Cowork to pick up changes that are already in a Google Drive Skill Library.

Short human prompts are enough: `refresh Test Plugin`, `sync Test Plugin from Drive`, and `refresh meeting-followup in Test Plugin`.

These prompts mean: the Drive library is the source of truth, and Cowork should verify the Drive files, rebuild or reinstall the plugin artifact if needed, and confirm the installed skill behavior. Do not interpret these prompts as a request to edit or improve the skill content.

If the user says `update Test Plugin skill library`, treat it as refresh/sync unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content.

First action must be reading the Google Drive folder contents directly: `<Drive root>/skills/<skill-id>/SKILL.md`. Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, or activation tools. Those are not part of the Phase 1 Drive Skill Library refresh path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `test-plugin` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to Drive Skill Library refresh.

Do not judge content quality, approve proposals, or resolve disagreements. Maintainer review happens before refresh, normally by comparing local Markdown copies of canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. The normal path is verification after the maintainer has already edited the canonical file.

If an Approved proposal is present and canonical already matches it, report that canonical is already in sync and continue. `Proposals/Approved/` and `Proposals/Rejected/` are optional archive/status folders, not mandatory gates.

Do not call AIWS marketplace tools, create or open drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, export bridge repositories, upload ZIPs, or change marketplace registrations. Do not use marketplace or materialization results as evidence for or against refresh.

Refresh compares the Drive Skill Library root against the installed Cowork plugin when installed content is available. If installed content already matches Drive canonical content, report that no rebuild is required. Rebuild or guide reinstall of the whole Cowork plugin artifact only when installed content differs, installed visibility is missing, or installed content cannot be confirmed. For `Test Plugin`, preserve plugin id `test-plugin` and display name `Test Plugin`. Do not generate per-skill plugin identities such as `test-plugin--meeting-followup`. Do not report that a missing `plugins/` folder blocks refresh; a flat `skills/<skill-id>/SKILL.md` Drive folder is the expected Phase 1 source shape.

Workflow: identify the Drive Skill Library, verify named skill or all skills in `skills/`, confirm canonical `SKILL.md` exists and validates, compare Submitted or Approved proposals only as evidence when present, use `aiws-validate-skill-library`, compare installed Cowork plugin content when available, report no rebuild required if installed content matches Drive, otherwise rebuild or guide reinstall of the whole Cowork plugin artifact from the Drive library root while preserving plugin id `test-plugin` for `Test Plugin`, and verify installed plugin/container when possible. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.

Report `AIWS Skill Library Refresh: PASS`, `FAIL`, or `NEEDS MANUAL ACTION`, including library, skills, canonical verification, proposal sync evidence, library validation, Cowork refresh/reinstall, and skill invocation. Do not fail a successful refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.
"""


AIWS_VALIDATE_SKILL_LIBRARY_SKILL = """---
name: aiws-validate-skill-library
description: Validate an AIWS Skill Library folder and report concrete fixes.
---

# AIWS Skill Library Validation

Use this skill when a user wants to check whether a Drive Skill Library is ready for Cowork import, maintainer review, or cross-host use.

Reliable human prompts are: `Validate the Test Plugin Drive library and include installed plugin status`, `Check the Test Plugin Drive library and installed plugin status`, and `Check Test Plugin Drive library`. The shorter `Check Test Plugin` prompt is ambiguous in Cowork and may route to a generic installed-plugin summary.

These prompts mean: inspect the Drive Skill Library, validate canonical skill files and proposal folders, report installed/visible skill status when available, and do not change anything.

For `Check Test Plugin`, the Drive folder is the source of truth. Start with the Drive library root and read `skills/<skill-id>/SKILL.md`, `Proposals/Submitted/`, `Proposals/Approved/`, and `Proposals/Rejected/`. Do not satisfy `Check Test Plugin` by checking only the installed Cowork plugin copy. The installed copy is secondary evidence after Drive validation.

For `Check Test Plugin`, after Drive validation completes, attempt to report installed Cowork plugin visibility when the host exposes it. This is secondary evidence, not the source of truth. If installed status cannot be checked, report `not verified`; do not omit the section.

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

This skill is read-only. Do not write proposal files, edit canonical `SKILL.md`, rebuild packages, ask for Save plugin, install plugins, refresh plugins, create drafts, activate drafts, upload ZIPs, create GitHub pull requests, or change marketplace registrations.

First action must be reading the Drive Skill Library source, not the installed plugin copy. Installed plugin inspection may happen only after Drive canonical skills and proposal folders have been checked.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library check path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `test-plugin` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to checking a Drive Skill Library.

If proposals exist, validate `Proposals/Submitted/<skill-id>/<proposal-id>/`, `Proposals/Approved/<skill-id>/<proposal-id>/`, and `Proposals/Rejected/<skill-id>/<proposal-id>/`. Confirm each proposal includes `SKILL.md` and `aiws.proposal.json` and points back to `skills/<skill-id>/SKILL.md`.

Reject flat legacy proposal paths such as `Proposals/<skill-id>/<proposal-id>/`.

## Output

Report `AIWS Skill Library Validation: PASS` only if the required library shape and all present metadata/proposals validate. Use `WARN` for optional missing metadata or unknown Drive folder id. Include concrete fixes for every failure.

When installed plugin status is available, include it as a separate `Installed Cowork plugin` section. Do not make installed-plugin visibility a library validation failure unless the user specifically asked to check Cowork installation.

For `Check Test Plugin`, always include the `Installed Cowork plugin` section after Drive validation. Use `not verified` when the host cannot expose installed plugin status.

If Drive access is unavailable, report `NEEDS MANUAL ACTION` or `FAIL` for Drive library validation and provide the exact Drive folders/files that must be checked. Do not replace Drive validation with installed-plugin-only validation.

If the Python validator is available, it may be used as a secondary deterministic check:

```bash
PYTHONPATH=aiws-mcp python3 -m aiws_mcp validate-skill-library --library-root <library-root>
```

The Python command is developer/CI support. The user-facing validation surface is this skill.
"""


AIWS_CHECK_SKILL_LIBRARY_SKILL = """---
name: aiws-check-skill-library
description: Check a Drive Skill Library source and installed Cowork plugin status without changing anything.
---

# AIWS Skill Library Check

Use this skill when a user wants to check a Drive Skill Library and its installed Cowork plugin status.

Reliable human prompts: `Validate the Test Plugin Drive library and include installed plugin status`, `Check the Test Plugin Drive library and installed plugin status`, and `Check Test Plugin Drive library`.

This is a read-only check. It is a stronger trigger alias for `aiws-validate-skill-library`, intended for Cowork sessions where `Check Test Plugin` may route to a generic installed-plugin summary.

Start from the Google Drive Skill Library source, not from the installed Cowork plugin copy. Read and validate `skills/<skill-id>/SKILL.md`, `Proposals/Submitted/`, `Proposals/Approved/`, `Proposals/Rejected/`, `aiws.library.json` if present, and `aiws.skills/` if present.

After Drive validation, include installed Cowork plugin status as secondary evidence. If installed status cannot be checked, report `not verified`; do not omit the `Installed Cowork plugin` section.

Do not write proposal files, edit canonical `SKILL.md`, rebuild packages, ask for Save plugin, install plugins, refresh plugins, create drafts, activate drafts, upload ZIPs, create GitHub pull requests, or change marketplace registrations.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library check path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path.

Do not satisfy this request by checking only the installed Cowork plugin copy. The installed copy is secondary evidence after Drive validation.

Report `AIWS Skill Library Validation: PASS`, `FAIL`, or `NEEDS MANUAL ACTION` with Library, Skills, Metadata, Proposals, Phase 1 boundaries, Installed Cowork plugin, and Fixes sections.
"""


BUILTIN_SKILLS = {
    "aiws-improve": AIWS_IMPROVE_SKILL,
    "aiws-check-skill-library": AIWS_CHECK_SKILL_LIBRARY_SKILL,
    "aiws-install-drive-skill-library": AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL,
    "aiws-propose-skill-update": AIWS_PROPOSE_SKILL_UPDATE_SKILL,
    "aiws-refresh-skill-library": AIWS_REFRESH_SKILL_LIBRARY_SKILL,
    "aiws-update-skill-library": AIWS_UPDATE_SKILL_LIBRARY_SKILL,
    "aiws-validate-skill-library": AIWS_VALIDATE_SKILL_LIBRARY_SKILL,
}


RESOURCES = {
    "aiws://protocols/sop": SOP_RESOURCE,
    "aiws://skills/aiws-improve": AIWS_IMPROVE_SKILL,
    "aiws://skills/aiws-check-skill-library": AIWS_CHECK_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-install-drive-skill-library": AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-propose-skill-update": AIWS_PROPOSE_SKILL_UPDATE_SKILL,
    "aiws://skills/aiws-refresh-skill-library": AIWS_REFRESH_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-update-skill-library": AIWS_UPDATE_SKILL_LIBRARY_SKILL,
    "aiws://skills/aiws-validate-skill-library": AIWS_VALIDATE_SKILL_LIBRARY_SKILL,
}

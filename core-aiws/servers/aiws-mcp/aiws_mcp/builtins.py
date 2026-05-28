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
description: Analyze accumulated user signals and propose improvements to workspace instructions, agents, skills, and hooks
---

# Batch Self-Improvement Analysis

This is the shared `aiws-improve` capability owned by `core-aiws`.

Gathers accumulated signals from multiple sources, synthesizes patterns, then runs the unified [Self-Improvement Protocol](../../protocols/self-improvement.md) in batch mode.

**Scope**: This skill is responsible only for evidence gathering and synthesis (Phases 1-3). All decision rules for prompt, skill, protocol, and workflow improvement live in the protocol — do not duplicate them here. Shared-memory refresh is not owned by this skill.

`aiws-improve` is the canonical AIWS capability identity. Hosts may expose it as a slash command, a skill, an MCP prompt, or another native UI affordance. Do not assume `/aiws-improve` is available unless the current host advertises slash-command exposure.

---

## Phase 1: Gather Batch Evidence

Resolve host evidence surfaces first. Prefer the AIWS host evidence contract, for example `aiws.host.surfaces` when exposed by the local MCP runtime. Read all available logical surfaces and skip any that the current host does not provide:

1. **Observations**: host-provided structured correction, frustration, give-up, positive, and improvement markers. Find the most recent `improve_run` marker as cutoff when markers exist.
2. **Project notes or daily logs**: host-provided project memory or session notes for today and yesterday when available.
3. **Session history and transcripts**: host-provided current or recent interaction history when available.
4. **Installed contracts and skill catalog**: host-provided plugin contracts, skill manifests, or AIWS catalog resources.
5. **Current conversation context**.

Present evidence summary:

```
## Evidence Summary (since last aiws-improve run)

**Observations** (from hook signals):
| Signal Type   | Count |
|---------------|-------|
| correction    | N     |
| frustration   | N     |
| give_up       | N     |
| positive      | N     |

**Other sources**: N project notes, N session histories reviewed, N installed contracts or manifests reviewed
- Unique sessions: N
- Unique projects: N
- Date range: YYYY-MM-DD to YYYY-MM-DD
```

If no evidence exists from any source, report "No new signals to analyze" and stop.

---

## Phase 2: Transcript Deep-Dive

For each **high-severity** observation (correction, frustration, give_up):

1. Resolve the related transcript or session context through the host-provided evidence surface when available. If the host provides only a summary, or no transcript surface at all, continue from the observation summary and current context, and mark the missing transcript as an evidence gap.
2. Find context: what was the host agent doing? What did the user ask? Where did it go wrong?
3. Identify root cause: missing rule, bad agent prompt, wrong default, process friction, tool discovery, architecture insight

Present findings:
```
### Finding: <obs_id> (<type>, <date>)
**User said**: "<message excerpt>"
**Context**: <what the host agent was doing>
**Root cause**: <category> - <specific explanation>
**Target**: <file path> : <section/line>
```

---

## Phase 3: Pattern Synthesis

Group findings by root cause across sessions:
- Same correction across multiple sessions → missing rule
- Same frustration pattern → process issue
- Positive patterns → reinforce what works

Present:
```
### Pattern: <descriptive name>
- Sessions: <list of session dates>
- Root cause: <category>
- Evidence: "<quote 1>", "<quote 2>"
- Target file: <path>
- Confidence: HIGH/MEDIUM (see protocol rules)
```

---

## Phase 4: Run Self-Improvement Protocol

Follow the [Self-Improvement Protocol](../../protocols/self-improvement.md) in batch mode with the synthesized findings from Phase 3 as input. Start from Step 3 (Categorize and Decide) — Steps 1-2 are skipped in batch mode. Use the synthesized patterns from Phase 3 as input to Step 3's categorization; formal Learning Entry Format is applied in Step 4.2.

Do not treat `aiws-improve` as the routine shared-memory consolidation trigger. Shared-memory candidate capture happens during end-of-task auto-capture, and shared-memory refresh is handled automatically by the host-side shared-memory bridge.

---

## Phase 5: Update Observation Log

After protocol completion:

1. Append an `improve_run` marker to the host-provided writable observation or improvement-marker surface, if one exists:
   ```json
   {"id":"imp_<8-char-hex>","ts":"<ISO timestamp>","type":"improve_run","severity":"info","message":"Processed observations up to <latest_obs_id>"}
   ```

2. For each applied change, append a verification entry to the same host-provided marker surface, if one exists:
   ```json
   {"id":"verify_<8-char-hex>","ts":"<ISO timestamp>","type":"improvement_applied","severity":"info","message":"Applied: <brief description>. Monitor for recurrence."}
   ```

"""


AIWS_INSTALL_DRIVE_SKILL_LIBRARY_SKILL = """---
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

Do not tell the user that a `<plugin-id>` marketplace is empty or missing. Do not mention marketplace in the normal install report. The user-facing objects are:

- Drive Skill Library
- Cowork plugin artifact
- Save plugin card
- installed plugin/container

## Input

Collect the Google Drive folder URL.

## Package And Install

If already running inside Cowork, treat the current user request as the install request. Do not tell the user to run another prompt in the same Cowork session.

Use the Google Drive integration to read the folder URL, then package the library into one Cowork plugin artifact:

- plugin display name: the Drive root folder name (`<library-display-name>`)
- plugin id: a stable slug derived from the Drive root folder name (`<plugin-id>`)
- skills: every `skills/<skill-id>/SKILL.md` actually present in the Drive folder
- ignored as runtime skills: `Proposals/`, `aiws.library.json`, `aiws.skills/`, and any proposal metadata

The plugin artifact must be a zip-compatible Cowork plugin package with files at the archive root:

```text
.claude-plugin/plugin.json
contracts/<plugin-id>.contract.json
skills/<skill-id>/SKILL.md
```

The artifact is a plugin artifact, not a `.skill` artifact. Name and present it as a `.plugin` file/card so Cowork routes it to the plugin installer. If the host-generated card, filename, or report says `.skill`, **Save skill**, or individual skill install, do not tell the user to click it. Report `AIWS Drive Skill Library Install: NEEDS RETRY`, explain that Cowork produced a skill card instead of a plugin card, and repackage the same Drive contents as a `.plugin` artifact.

Derive `<plugin-id>` as a stable slug from `<library-display-name>` (lowercase, hyphenated). The manifest must include `name`, `description`, `version`, and `author.name`. The contract must include `plugin_id`, `version`, and `public_skills` listing exactly the packaged skill folder ids. Do not put files under an extra top-level wrapper folder inside the archive.

Before presenting the **Save plugin** card, inspect the generated archive and verify:

- `.claude-plugin/plugin.json` exists at archive root
- `contracts/<plugin-id>.contract.json` exists at archive root
- every `skills/<skill-id>/SKILL.md` from the actual Drive folder exists at archive root (data-driven from the Drive listing — do not hard-code skill ids)
- no entry starts with `<plugin-id>/`, `<library-display-name>/`, or another wrapper folder
- `plugin.json.name` equals the derived `<plugin-id>`
- `plugin.json.version` is a non-empty semver-like string
- contract `plugin_id` and `version` match `plugin.json`
- contract `public_skills` equals the packaged skill folder ids
- each packaged `SKILL.md` has only `name` and `description` frontmatter
- each packaged `SKILL.md` frontmatter `name` exactly matches its folder id
- each packaged `SKILL.md` has a non-empty body

If any preflight check fails, do not present the **Save plugin** card. Fix the artifact or report `AIWS Drive Skill Library Install: FAIL` with the exact failing file and field.

Do not register the Drive folder as a marketplace. Do not search AIWS marketplaces for it. Do not use missing marketplace search results as evidence that the Drive folder cannot be packaged.

Present exactly one **Save plugin** card for a `.plugin` artifact. If the host first produces individual **Save skill** cards, a `.skill` artifact, or labels the plugin artifact with a **Save skill** button, say that is not the requested result and repackage the same Drive contents as a plugin. Never report `READY FOR SAVE` while the visible action is **Save skill**.

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

## Self-Improvement Phase

End every install procedure with a short self-improvement checkpoint. Do not mutate Drive content, rebuild packages, edit skills, or change plugin state during this checkpoint. Compare the actual install path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, bad routing, missing validation, artifact-card mismatch, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

## Output

Report:

```text
AIWS Drive Skill Library Install: READY FOR SAVE|PASS|FAIL|NEEDS RETRY|NEEDS MANUAL ACTION

Drive folder:
Install prompt:
Plugin artifact generated: PASS|FAIL|NEEDS MANUAL ACTION
Plugin artifact layout valid: PASS|FAIL|not verified
Plugin artifact preflight: PASS|FAIL|not verified
Save plugin completed: PASS|FAIL|not verified
Plugin/container visible: PASS|FAIL|not verified
Skills visible under plugin/container: PASS|FAIL|not verified
Proposal folders ignored as skills: PASS|FAIL|not verified
Self-improvement:
```

Use `READY FOR SAVE` when the plugin card is generated and preflighted but the user has not clicked **Save plugin** yet. Use `PASS` only after Cowork accepts the plugin and the installed plugin/container and skills are verified. If Cowork reports `Plugin validation failed`, do not repeat the same artifact blindly; inspect and report the generated archive entries, manifest JSON, contract JSON, packaged skill frontmatter, and the exact Cowork error text if available.

"""


AIWS_PROPOSE_SKILL_UPDATE_SKILL = """---
name: aiws-propose-skill-update
description: Prepare a Drive Skill Library proposal from an edited SKILL.md.
---

# AIWS Skill Library Proposal

Use this skill when a user wants to propose an update to a skill stored in an AIWS Skill Library, especially a Google Drive library shaped as:

```text
<Library root>/
  skills/
    <skill-id>/
      SKILL.md
  Proposals/
    Submitted/
      <skill-id>/
        <proposal-id>/
          SKILL.md
          aiws.proposal.json
```

The goal is to place a proposed replacement `SKILL.md` in the library's proposal area without changing the canonical skill file.

Short human prompts are enough (replace `<library-display-name>` and `<skill-id>` with the user's actual library and skill names):

```text
propose a <skill-id> update for <library-display-name>
propose this <skill-id> change for <library-display-name>: <plain-language change description>
submit a <skill-id> proposal for <library-display-name>
```

For example: `propose a meeting-followup update for Test Plugin`.

These prompts mean: find the Drive Skill Library, read the canonical skill, collect or infer the proposed change, and write a proposal under `Proposals/Submitted/`. Do not interpret them as a request to edit canonical `skills/<skill-id>/SKILL.md`.

## Boundaries

First action should be locating and reading the Drive Skill Library contents directly:

```text
<Drive root>/skills/<skill-id>/SKILL.md
```

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library proposal path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `<plugin-id>` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to proposal submission.

Do not create drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, create plugin manifests, upload ZIPs, rebuild Cowork packages, or change marketplace registrations.

## Inputs

Collect or infer:

- library display name (`<library-display-name>`)
- library id, if known
- library root location or Drive folder link, if available
- skill id
- edited `SKILL.md` content or path
- proposer name or account, if available
- short reason for the change

If a value is missing but not required to write the proposal, use `unspecified` in metadata rather than blocking.

Ask for missing information only when the proposal cannot be written safely. Prefer one concise question over a multi-step form.

## Validate First

Use `aiws-validate-skill-library` before preparing the proposal. Do not duplicate its validation checklist here. If validation fails, report the concrete issue and stop.

## Proposal ID

Use a stable, readable proposal id:

```text
proposal-YYYY-MM-DD-<short-topic>
```

Normalize `<short-topic>` to lowercase letters, digits, and hyphens. If no topic is obvious, use `skill-update`.

If the destination already exists, append `-2`, `-3`, and so on instead of overwriting another proposal.

## Write Target

Prepare these files:

```text
Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
Proposals/Submitted/<skill-id>/<proposal-id>/aiws.proposal.json
```

Do not edit:

```text
skills/<skill-id>/SKILL.md
```

Only a maintainer changes the canonical file at `skills/<skill-id>/SKILL.md`. The maintainer may optionally move or copy the proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/` or `Proposals/Rejected/<skill-id>/<proposal-id>/` for recordkeeping, but those archive folders are not required for the normal update path.

## Maintainer Review Handoff

After writing the proposal, give the maintainer a simple local Markdown diff path. Do not rely on Google Docs compare.

Recommended free tools:

- VS Code or VSCodium:
  ```text
  code --diff skills/<skill-id>/SKILL.md Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
  ```
- Meld:
  ```text
  meld skills/<skill-id>/SKILL.md Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
  ```

If the files are only in Google Drive, tell the maintainer to open or sync local copies of the canonical `SKILL.md` and proposed `SKILL.md`, then compare those two files. After review, the maintainer applies accepted changes directly to:

```text
skills/<skill-id>/SKILL.md
```

The maintainer may then optionally move or copy the proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/` or `Proposals/Rejected/<skill-id>/<proposal-id>/` for recordkeeping.

## Proposal Metadata

Write `aiws.proposal.json` as JSON:

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

Keep metadata factual. Do not include private transcript text, credentials, or hidden runtime state.

## Output

Report:

- proposal id
- skill id
- files written or files prepared
- maintainer review path under `Proposals/Submitted/`
- local diff command for VS Code/VSCodium or Meld
- canonical update path under `skills/<skill-id>/SKILL.md`
- optional archive paths under `Proposals/Approved/` and `Proposals/Rejected/`
- explicit note that the canonical skill was not changed

If direct Drive write access is unavailable, provide the exact folder path and file contents for the user or host to save. Do not claim the proposal landed in Drive unless the files were actually written there.

## Self-Improvement Phase

End every proposal procedure with a short self-improvement checkpoint. Do not mutate Drive content, rewrite proposal files, edit canonical skills, rebuild packages, or change plugin state during this checkpoint. Compare the actual proposal path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, missing metadata, failed Drive writes, unclear maintainer handoff, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

"""


AIWS_UPDATE_SKILL_LIBRARY_SKILL = """---
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

Treat short human prompts as sufficient. Examples (replace `<library-display-name>` and `<skill-id>` with the user's actual library and skill names):

```text
update <library-display-name> skill library
refresh <library-display-name>
update <skill-id> in <library-display-name> skill library
```

For example: `update Test Plugin skill library`.

For these prompts, verify/refresh the library by default. Do not ask what content changes the user wants to make unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content. If the skill id is named in the prompt, use it. If only the library is named, inspect the library and verify all changed or available skills.

If a proposal folder is present and canonical already matches it, report that the canonical file is already in sync with the proposal and proceed to validation and Cowork refresh/reinstall. If installed Cowork content already matches Drive canonical content, report that no rebuild is required.

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
5. Refresh Cowork reimport of the Drive skill library, following `aiws-refresh-skill-library` semantics: compare installed Cowork plugin content when available, report no rebuild required if installed content matches Drive, and rebuild/preflight/present a **Save plugin** card when installed content differs or cannot be verified. A `.skill` artifact or **Save skill** card is a retry/failure state, not a valid refresh. Guide manual reinstall only when the current host cannot read Drive, build the artifact, preflight it, or present the **Save plugin** card.
6. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.
7. Run the self-improvement phase.

If direct Drive write access is unavailable, provide exact manual copy/replace instructions and report `NEEDS MANUAL ACTION`. Do not claim the canonical file was updated until it is verified.

## Self-Improvement Phase

End every update procedure with a short self-improvement checkpoint. Do not mutate Drive content, rebuild packages, edit skills, or change plugin state during this checkpoint. Compare the actual update path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, bad routing, unclear approval evidence, stale installed state, missing verification, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

## Output

Report:

```text
AIWS Skill Library Update: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION

Library:
Skill:
Proposal:
Submitted proposal path:
Canonical SKILL.md verified: PASS|FAIL|NEEDS MANUAL ACTION
Library validation: PASS|FAIL
Cowork refresh/import: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|not verified|optional
Self-improvement:
```

Use `PASS` when the canonical file update is verified, library validation passes after the update, and Cowork installed content is either already in sync or successfully refreshed. Use `READY FOR SAVE` when a rebuilt plugin artifact has passed preflight and a **Save plugin** card is presented but the user has not clicked it yet. Use `NEEDS RETRY` when Cowork produced a **Save skill** card or `.skill` artifact instead of the required **Save plugin** card. Use `NEEDS MANUAL ACTION` when the maintainer or host must perform a Drive copy or when the current host cannot read Drive, build the artifact, preflight it, or present the **Save plugin** card. Do not fail a successful update/refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.

"""


AIWS_REFRESH_SKILL_LIBRARY_SKILL = """---
name: aiws-refresh-skill-library
description: Refresh a Cowork-installed Drive Skill Library after Drive changed.
---

# AIWS Skill Library Refresh

Use this skill when a user wants Cowork to pick up changes that are already in a Google Drive Skill Library.

Short human prompts are enough (replace `<library-display-name>` and `<skill-id>` with the user's actual library and skill names):

```text
refresh <library-display-name>
sync <library-display-name> from Drive
refresh <skill-id> in <library-display-name>
```

For example: `refresh Test Plugin`.

These prompts mean: the Drive library is the source of truth, and Cowork should verify the Drive files, rebuild or reinstall the plugin artifact if needed, and confirm the installed skill behavior. Do not interpret these prompts as a request to edit or improve the skill content.

If the user says `update <library-display-name> skill library`, treat it as refresh/sync unless the user explicitly says they want to edit, rewrite, propose, create, or change the skill content.

## Boundaries

First action must be reading the Google Drive folder contents directly:

```text
<Drive root>/skills/<skill-id>/SKILL.md
```

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, or activation tools. Those are not part of the Phase 1 Drive Skill Library refresh path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `<plugin-id>` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to Drive Skill Library refresh.

Do not judge content quality, approve proposals, or resolve disagreements. Maintainer review happens before refresh, normally by comparing local Markdown copies of canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. The normal path is verification after the maintainer has already edited the canonical file.

If an Approved proposal is present and canonical already matches it, report that canonical is already in sync and continue. `Proposals/Approved/` and `Proposals/Rejected/` are optional archive/status folders, not mandatory gates.

Do not call AIWS marketplace tools, create or open drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, export bridge repositories, upload ZIPs, or change marketplace registrations. Do not use marketplace or materialization results as evidence for or against refresh.

Refresh compares the Drive Skill Library root against the installed Cowork plugin when installed content is available. If installed content already matches Drive canonical content, report that no rebuild is required. If installed content differs, installed visibility is missing, or installed content cannot be confirmed, rebuild the whole Cowork plugin artifact from the Drive root and present a single **Save plugin** card in the current Cowork session. Fall back to manual reinstall guidance only when the host cannot read Drive, cannot build the artifact, or cannot present the **Save plugin** card.

Any rebuilt artifact identity must remain stable across refreshes for the same library:

```text
plugin id: <plugin-id>          (the stable slug derived from <library-display-name>)
plugin display name: <library-display-name>
```

Do not generate per-skill plugin identities such as `<plugin-id>--<skill-id>`. Do not report that a missing `plugins/` folder blocks refresh; a flat `skills/<skill-id>/SKILL.md` Drive folder is the expected Phase 1 source shape.

## Workflow

1. Identify the Drive Skill Library by display name (`<library-display-name>`).
2. If a skill id is named, verify that skill; otherwise verify all skills in `skills/`.
3. Confirm canonical `skills/<skill-id>/SKILL.md` exists and validates.
4. If Submitted or Approved proposal folders are present, compare them only as evidence; do not require them.
5. Use `aiws-validate-skill-library` to validate the library and proposal structure.
6. Compare the installed Cowork plugin content when available.
7. If installed content matches Drive, report no rebuild required.
8. If installed content differs or cannot be verified, rebuild the whole Cowork plugin artifact from the Drive library root, preserving the stable `<plugin-id>` derived from `<library-display-name>`.
9. Before presenting the **Save plugin** card, run the same artifact preflight as `aiws-install-drive-skill-library`: verify `.claude-plugin/plugin.json`, `contracts/<plugin-id>.contract.json`, every packaged `skills/<skill-id>/SKILL.md`, no wrapper folder, matching manifest/contract ids and versions, exact `public_skills`, portable skill frontmatter, matching skill folder names, and non-empty skill bodies.
10. Present exactly one **Save plugin** card when rebuild is needed and preflight passes. Do not send the user to plugin management first if the current Cowork session can present the card.
11. If the host-generated card, filename, or report says `.skill`, **Save skill**, or individual skill install, do not tell the user to click it. Report `AIWS Skill Library Refresh: NEEDS RETRY` or `FAIL`, explain that Cowork produced a skill card instead of a plugin card, and repackage the same Drive contents as a `.plugin` artifact.
12. Use manual reinstall guidance only if Drive access, artifact creation, artifact preflight, or **Save plugin** presentation is unavailable in the current host.
13. Verify the installed plugin/container when possible. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.
14. Run the self-improvement phase.

## Self-Improvement Phase

End every refresh procedure with a short self-improvement checkpoint. Do not mutate Drive content, rebuild packages, edit skills, or change plugin state during this checkpoint. Compare the actual refresh path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, bad routing, stale installed state, missing verification, artifact-card mismatch, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

## Output

Report:

```text
AIWS Skill Library Refresh: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION

Library:
Skill(s):
Canonical SKILL.md verified: PASS|FAIL
Proposal sync evidence: PASS|FAIL|not present
Library validation: PASS|FAIL
Cowork refresh/reinstall: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|not verified|optional
Self-improvement:
```

Use `PASS` when canonical Drive content is verified, validation passes, and Cowork installed content is either already in sync or successfully refreshed. Use `READY FOR SAVE` when a rebuilt plugin artifact has passed preflight and a **Save plugin** card is presented but the user has not clicked it yet. Use `NEEDS RETRY` when Cowork produced a **Save skill** card or `.skill` artifact instead of the required **Save plugin** card. Use `NEEDS MANUAL ACTION` only when the current host cannot complete Drive read, artifact build, preflight, or **Save plugin** presentation. Do not fail a successful refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.

"""


AIWS_VALIDATE_SKILL_LIBRARY_SKILL = """---
name: aiws-validate-skill-library
description: Validate an AIWS Skill Library folder and report concrete fixes.
---

# AIWS Skill Library Validation

Use this skill when a user wants to check whether a Drive Skill Library is ready for Cowork import, maintainer review, or cross-host use.

Reliable human prompts are (replace `<library-display-name>` with the user's actual library name):

```text
Validate the <library-display-name> Drive library and include installed plugin status
Check the <library-display-name> Drive library and installed plugin status
Check <library-display-name> Drive library
```

For example: `Validate the Test Plugin Drive library and include installed plugin status`.

These prompts mean: inspect the Drive Skill Library, validate canonical skill files and proposal folders, report installed/visible skill status when available, and do not change anything.

The shorter `Check <library-display-name>` prompt is ambiguous in Cowork and may route to a generic installed-plugin summary.

For `Check <library-display-name>`, the Drive folder is the source of truth. Start with the Drive library root and read:

```text
skills/<skill-id>/SKILL.md
Proposals/Submitted/
Proposals/Approved/
Proposals/Rejected/
```

Do not satisfy `Check <library-display-name>` by checking only the installed Cowork plugin copy. The installed copy is secondary evidence after Drive validation.

For example, do not satisfy `Check Test Plugin` by checking only the installed Cowork plugin copy.

For `Check <library-display-name>`, after Drive validation completes, attempt to report installed Cowork plugin visibility when the host exposes it. This is secondary evidence, not the source of truth. If installed status cannot be checked, report `not verified`; do not omit the section.

Phase 1 validates a skill-first library, not a packaged plugin marketplace:

```text
<Library root>/
  skills/
    <skill-id>/
      SKILL.md
```

Optional AIWS metadata may exist at the library root:

```text
aiws.library.json
aiws.skills/
Proposals/
```

## Validation Checklist

### Required Library Shape

Check:

1. The library has a `skills/` directory.
2. Each skill lives at `skills/<skill-id>/SKILL.md`.
3. Each `<skill-id>` uses lowercase letters, digits, and hyphens.
4. Each `SKILL.md` has YAML frontmatter.
5. Frontmatter contains only `name` and `description`.
6. Frontmatter `name` equals the folder name.
7. Frontmatter `description` is nonempty.
8. The skill body is nonempty.

### Phase 1 Boundaries

Fail validation if the library requires plugin runtime artifacts:

```text
.claude-plugin/plugin.json
contracts/
.mcp.json
```

Runtime capability artifacts like MCP servers, connectors, auth config, scripts, packaged plugins, ZIP uploads, and host tools are outside Phase 1 Skill Library mode.

### Read-Only Boundaries

This skill is read-only. Do not write proposal files, edit canonical `SKILL.md`, rebuild packages, ask for **Save plugin**, install plugins, refresh plugins, create drafts, activate drafts, upload ZIPs, create GitHub pull requests, or change marketplace registrations.

First action must be reading the Drive Skill Library source, not the installed plugin copy. Installed plugin inspection may happen only after Drive canonical skills and proposal folders have been checked.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library check path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `<plugin-id>` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to checking a Drive Skill Library.

### Optional AIWS Metadata

If `aiws.library.json` exists, check:

- it is valid JSON
- `kind` is absent or `aiws.skill_library`
- `id` is lowercase letters, digits, and hyphens
- `display_name`, if present, is text
- `source.kind` is `google_drive` for Phase 1
- for `google_drive`, `source.folder_id` is present if known

If `aiws.skills/*.json` exists, check each file:

- `kind` is absent or `aiws.skill`
- `id` matches the filename stem
- `id` references an existing `skills/<id>/SKILL.md`
- `source_path` points to `skills/<id>/SKILL.md`

### Proposal Folders

If `Proposals/` exists, check:

```text
Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md
Proposals/Approved/<skill-id>/<proposal-id>/SKILL.md
Proposals/Rejected/<skill-id>/<proposal-id>/SKILL.md
```

For each proposal:

- proposal state is exactly `Submitted`, `Approved`, or `Rejected`
- `<skill-id>` references an existing canonical skill
- proposal `SKILL.md` passes the same portable skill checks
- proposal frontmatter `name` equals `<skill-id>`
- `aiws.proposal.json` is valid JSON
- `kind` is absent or `aiws.proposal`
- `proposal_id` matches the folder name
- `skill_id` matches the parent folder
- `source_path` points to `skills/<skill-id>/SKILL.md`

Fail flat legacy proposal paths such as:

```text
Proposals/<skill-id>/<proposal-id>/
```

## Output Format

Report:

```text
AIWS Skill Library Validation: PASS|FAIL

Library:
- name:
- root:
- source kind:

Skills:
- <skill-id>: PASS|FAIL - <reason>

Metadata:
- aiws.library.json: PASS|WARN|FAIL|not present
- aiws.skills/: PASS|WARN|FAIL|not present

Proposals:
- <proposal-id>: PASS|FAIL - <reason>

Fixes:
1. <specific fix>
2. <specific fix>
```

Use `PASS` only if the required library shape and all present metadata/proposals validate. Use `WARN` for optional missing metadata or unknown Drive folder id. Do not fail only because optional metadata is absent.

When installed plugin status is available, include it as a separate section:

```text
Installed Cowork plugin:
- <plugin-id>: present|not verified|missing
- skills visible: PASS|FAIL|not verified
```

Do not make installed-plugin visibility a library validation failure unless the user specifically asked to check Cowork installation.

For `Check <library-display-name>`, always include this section after Drive validation. Always include the `Installed Cowork plugin` section after Drive validation. Use `not verified` when the host cannot expose installed plugin status.

If Drive access is unavailable, report `NEEDS MANUAL ACTION` or `FAIL` for Drive library validation and provide the exact Drive folders/files that must be checked. Do not replace Drive validation with installed-plugin-only validation.

## Self-Improvement Phase

End every validation procedure with a short self-improvement checkpoint. This checkpoint is also read-only: do not write proposal files, edit canonical skills, rebuild packages, or change plugin state. Compare the actual validation path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, missing checks, inconsistent metadata, installed-copy substitution, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

## Developer Check

If the AIWS Python validator is available, it may be used as a secondary deterministic check:

```bash
PYTHONPATH=aiws-mcp python3 -m aiws_mcp validate-skill-library --library-root <library-root>
```

Treat the Python command as CI/developer support. The user-facing validation surface is this skill.

"""


AIWS_CHECK_SKILL_LIBRARY_SKILL = """---
name: aiws-check-skill-library
description: Check a Drive Skill Library source and installed Cowork plugin status without changing anything.
---

# AIWS Skill Library Check

Use this skill when a user wants to check a Drive Skill Library and its installed Cowork plugin status.

Reliable human prompts (replace `<library-display-name>` with the user's actual library name):

```text
Validate the <library-display-name> Drive library and include installed plugin status
Check the <library-display-name> Drive library and installed plugin status
Check <library-display-name> Drive library
```

For example: `Validate the Test Plugin Drive library and include installed plugin status`.

This is a read-only check. It is a stronger trigger alias for `aiws-validate-skill-library`, intended for Cowork sessions where `Check <library-display-name>` may route to a generic installed-plugin summary.

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
- <plugin-id>: present|missing|not verified
- skills visible: PASS|FAIL|not verified
```

If installed status cannot be checked, report `not verified`; do not omit the section.

## Boundaries

Do not write proposal files, edit canonical `SKILL.md`, rebuild packages, ask for **Save plugin**, install plugins, refresh plugins, create drafts, activate drafts, upload ZIPs, create GitHub pull requests, or change marketplace registrations.

Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, activation, host install, or bridge tools. Those are not part of the Phase 1 Drive Skill Library check path.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path.

Do not satisfy this request by checking only the installed Cowork plugin copy. The installed copy is secondary evidence after Drive validation.

For example, do not satisfy `Check Test Plugin` by checking only the installed Cowork plugin copy.

## Self-Improvement Phase

End every check procedure with a short self-improvement checkpoint. This checkpoint is read-only: do not write proposal files, edit canonical skills, rebuild packages, or change plugin state. Compare the actual check path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, missing installed-status evidence, installed-copy substitution, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

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
Self-improvement:
```

Use `PASS` only if the Drive library shape and all present proposal metadata validate. Installed plugin visibility is reported separately unless the user specifically asked for installed-plugin status as a hard requirement.

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

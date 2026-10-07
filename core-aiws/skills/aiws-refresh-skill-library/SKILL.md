---
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

First action must be reading the Google Drive folder contents directly via the host's Google Drive integration — the same surface used by `aiws-install-drive-skill-library` and `aiws-validate-skill-library`:

```text
<Drive root>/skills/<skill-id>/SKILL.md
```

This flow is not an AIWS marketplace workflow. Do not start by calling AIWS marketplace workflow, materialize, resolve, export, draft, or activation tools. Those are not part of the Phase 1 Drive Skill Library refresh path. A flat `skills/<skill-id>/SKILL.md` Drive folder is valid even if AIWS marketplace indexing would return no results. Do not use missing marketplace search results, an empty `<plugin-id>` marketplace, or absent materialized skills as evidence that the library cannot be refreshed — read Drive directly and proceed.

Do not inspect or report AIWS marketplace/materialized state in the normal user-visible path. In particular, do not say that a `<plugin-id>` marketplace exists, is empty, has zero published skills, or has no materialized skills. Those are debug-only implementation details and are not relevant to Drive Skill Library refresh.

Do not judge content quality, approve proposals, or resolve disagreements. Maintainer review happens before refresh, normally by comparing local Markdown copies of canonical and proposed `SKILL.md` files in VS Code/VSCodium or Meld.

Do not modify canonical `skills/<skill-id>/SKILL.md` unless the maintainer explicitly asks for apply mode. The normal path is verification after the maintainer has already edited the canonical file.

If an Approved proposal is present and canonical already matches it, report that canonical is already in sync and continue. `Proposals/Approved/` and `Proposals/Rejected/` are optional archive/status folders, not mandatory gates.

Do not call AIWS marketplace tools, create or open drafts, activate drafts, patch runtime-installed plugin files, create GitHub pull requests, export bridge repositories, upload ZIPs, or change marketplace registrations. Do not use marketplace or materialization results as evidence for or against refresh.

Refresh compares the Drive Skill Library root against the installed Cowork plugin when installed content is available. Installed content means the whole packaged skill folder: `SKILL.md` plus the supporting files selected by the Supporting File Rules in `aiws-install-drive-skill-library`, so a changed, added, or removed packaged file requires a rebuild. If installed content already matches Drive canonical content, report that no rebuild is required. If installed content differs, installed visibility is missing, or installed content cannot be confirmed, rebuild the whole Cowork plugin artifact from the Drive root and present a single **Save plugin** card in the current Cowork session. Fall back to manual reinstall guidance only when the host cannot read Drive, cannot build the artifact, or cannot present the **Save plugin** card.

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
7. If the installed plugin has the same set of packaged files as Drive, with the same content, report no rebuild required.
8. If installed content differs or cannot be verified, rebuild the whole Cowork plugin artifact from the Drive library root, preserving the stable `<plugin-id>` derived from `<library-display-name>`.
9. Before presenting the **Save plugin** card, run the same artifact preflight as `aiws-install-drive-skill-library`: verify `.claude-plugin/plugin.json`, `contracts/<plugin-id>.contract.json`, every packaged `skills/<skill-id>/SKILL.md`, no wrapper folder, matching manifest/contract ids and versions, exact `public_skills`, portable skill frontmatter, matching skill folder names, non-empty skill bodies, every packaged supporting file present at its Drive path, and no file entries beyond the packaged set. Sort supporting files by the Supporting File Rules in `aiws-install-drive-skill-library`; a refused file fails the refresh, and skipped or unpackageable files are listed by path, never dropped silently.
10. Present exactly one **Save plugin** card when rebuild is needed and preflight passes. Do not send the user to plugin management first if the current Cowork session can present the card. End the report with the post-save block from Output.
11. If the host-generated card, filename, or report says `.skill`, **Save skill**, or individual skill install, do not tell the user to click it. Report `AIWS Skill Library Refresh: NEEDS RETRY` or `FAIL`, explain that Cowork produced a skill card instead of a plugin card, and repackage the same Drive contents as a `.plugin` artifact.
12. Use manual reinstall guidance only if Drive access, artifact creation, artifact preflight, or **Save plugin** presentation is unavailable in the current host.
13. Verify the installed plugin/container when possible. Treat live skill invocation as a separate optional check unless the user explicitly asked to invoke the skill.
14. Check for personal copies that shadow library skills: compare the library's skill ids with the skills available in the current Cowork chat. If `anthropic-skills:<skill-id>` exists for a library `<skill-id>`, it shadows the library version. See Personal copy shadowing below.
15. Run mandatory self-improvement as the final phase.

## Output

Report:

```text
AIWS Skill Library Refresh: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION

Library:
Skill(s):
Canonical SKILL.md verified: PASS|FAIL
Proposal sync evidence: PASS|FAIL|not present
Library validation: PASS|FAIL
Supporting files packaged: none|<each skills/<skill-id>/<path>>
Skipped files: none|<each skills/<skill-id>/<path> - script|unknown type|non-skill file>
Unpackageable files: none|<each skills/<skill-id>/<path>>
Cowork refresh/reinstall: PASS|FAIL|READY FOR SAVE|NEEDS RETRY|NEEDS MANUAL ACTION
Skill invocation: PASS|FAIL|not verified|optional
Personal copy shadowing library skill: none|<skill-id list>
```

Use `PASS` when canonical Drive content is verified, validation passes, and Cowork installed content is either already in sync or successfully refreshed. Use `READY FOR SAVE` when a rebuilt plugin artifact has passed preflight and a **Save plugin** card is presented but the user has not clicked it yet. Use `NEEDS RETRY` when Cowork produced a **Save skill** card or `.skill` artifact instead of the required **Save plugin** card. Use `NEEDS MANUAL ACTION` only when the current host cannot complete Drive read, artifact build, preflight, or **Save plugin** presentation. Do not fail a successful refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.

When the status is `READY FOR SAVE`, end the user-facing report with the block below, replacing `<library-display-name>` and `<plugin-id>` with the real values. Do not show it for any other status (`PASS`, `FAIL`, `NEEDS RETRY`, `NEEDS MANUAL ACTION`, or no rebuild needed). The check prompt in the block is for a new chat after restart; never run it in the current session.

```text
After you click Save plugin:
1. Fully quit Claude and reopen it. If Cowork says the plugin "hasn't reached this computer yet",
   the current chat cannot see the new version; this is expected.
2. Start a new chat and type:
   Which skills from <library-display-name> can you see? List them with their plugin prefix.
3. Expected: every skill shows as <plugin-id>:<skill-id>.
```

## Personal copy shadowing

Detect only by matching `anthropic-skills:<skill-id>` against the library's skill ids. Do not match by any other name.

A personal copy overrides the library version, so the user keeps using the stale personal copy after a successful refresh. Claude cannot disable a personal skill. Offer the user this: turn the personal copy off in Cowork's skill panel, then start a new chat to check that the library version is used. Keeping it is legitimate while the user is preparing a new proposal; do not insist.

If the personal copy's content can be read and differs from canonical, warn that turning it off loses those local edits unless they are proposed first (see `aiws-propose-skill-update`). If it cannot be read, say the comparison was not possible. Do not guess.

Shadowing is a warning, not a failure: it does not change `PASS` or `READY FOR SAVE`. Do not delete, edit or rename personal skills, and do not call tools to manage skills.

## Mandatory Self-Improvement

This phase is mandatory and must be the final phase of the procedure. Run the [Self-Improvement Protocol](../../protocols/self-improvement.md) in realtime mode. Do not describe or substitute the protocol here.

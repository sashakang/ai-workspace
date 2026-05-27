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
```

Use `PASS` when canonical Drive content is verified, validation passes, and Cowork installed content is either already in sync or successfully refreshed. Use `READY FOR SAVE` when a rebuilt plugin artifact has passed preflight and a **Save plugin** card is presented but the user has not clicked it yet. Use `NEEDS RETRY` when Cowork produced a **Save skill** card or `.skill` artifact instead of the required **Save plugin** card. Use `NEEDS MANUAL ACTION` only when the current host cannot complete Drive read, artifact build, preflight, or **Save plugin** presentation. Do not fail a successful refresh only because live skill invocation was not run; report `Skill invocation: not verified` or `optional` and offer the separate invocation check.

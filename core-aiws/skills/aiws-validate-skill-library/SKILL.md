---
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

End validation by running the self-improvement phase.

## Self-Improvement Phase

End every validation procedure with a short self-improvement checkpoint. This checkpoint is also read-only: do not write proposal files, edit canonical skills, rebuild packages, or change plugin state. Compare the actual validation path with this procedure and report one concrete follow-up improvement when the run exposed confusing wording, missing checks, inconsistent metadata, installed-copy substitution, or a recurring manual workaround. If nothing actionable was learned, report `No self-improvement action identified`.

## Developer Check

If the AIWS Python validator is available, it may be used as a secondary deterministic check:

```bash
PYTHONPATH=aiws-mcp python3 -m aiws_mcp validate-skill-library --library-root <library-root>
```

Treat the Python command as CI/developer support. The user-facing validation surface is this skill.

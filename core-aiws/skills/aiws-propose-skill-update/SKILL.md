---
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

## Inputs

Collect or infer:

- library display name, such as `Test Plugin`
- library id, if known
- library root location or Drive folder link, if available
- skill id
- edited `SKILL.md` content or path
- proposer name or account, if available
- short reason for the change

If a value is missing but not required to write the proposal, use `unspecified` in metadata rather than blocking.

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

Only a maintainer approves a proposal by moving or copying the final proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/`.

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

If the files are only in Google Drive, tell the maintainer to open or sync local copies of the canonical `SKILL.md` and proposed `SKILL.md`, then compare those two files. Approval is still represented only by moving or copying the final proposal folder to:

```text
Proposals/Approved/<skill-id>/<proposal-id>/
```

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
- approval path under `Proposals/Approved/`
- explicit note that the canonical skill was not changed

If direct Drive write access is unavailable, provide the exact folder path and file contents for the user or host to save. Do not claim the proposal landed in Drive unless the files were actually written there.

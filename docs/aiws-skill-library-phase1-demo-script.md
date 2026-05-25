# AIWS Skill Library Phase 1 Demo Script

## Summary

This script demonstrates the Phase 1 Drive Skill Library user path for `Test Plugin`. The Drive folder is the source of truth. Cowork installs and runs skills from a plugin-like container generated from the Drive folder. AIWS supplies the convention, lifecycle skills, validation, and maintainer handoff.

Use the exact prompts below. They are intentionally written in normal user language.

Demo Drive folder:

```text
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

## 1. Install

Prompt:

```text
Install Test Plugin from this Drive folder:
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Expected:

- Cowork reads the Drive folder.
- Cowork packages one plugin artifact named `Test Plugin` with plugin id `test-plugin`.
- Cowork shows one **Save plugin** card.
- After Save, these skills are visible:
  - `test-plugin:meeting-followup`
  - `test-plugin:morning-briefing`

Do not accept:

- Separate **Save skill** cards as the final result.
- AIWS marketplace, materialize, export, draft, bridge, or missing `plugins/` explanations.

## 2. Use Existing Skill

Prompt:

```text
Use meeting-followup
```

When Cowork asks for meeting details, paste:

```text
Alex and Sam discussed the launch. Alex will send the final checklist tomorrow. Sam will confirm QA status by Friday.
```

Expected first output line:

```text
> meeting-followup update
```

## 3. Propose A Change

Prompt:

```text
Propose this meeting-followup change for Test Plugin: change the marker line to > meeting-followup demo proposal
```

Expected:

- Proposal lands in `Proposals/Submitted/meeting-followup/<proposal-id>/`.
- Proposal folder contains `SKILL.md` and `aiws.proposal.json`.
- Canonical `skills/meeting-followup/SKILL.md` is unchanged.
- Output includes a local Markdown diff command for VS Code/VSCodium or Meld.

## 4. Maintainer Review

Maintainer action:

Compare:

```text
skills/meeting-followup/SKILL.md
Proposals/Submitted/meeting-followup/<proposal-id>/SKILL.md
```

Use VS Code/VSCodium, Meld, or another local Markdown diff tool.

If accepted, the maintainer applies the accepted changes directly to:

```text
skills/meeting-followup/SKILL.md
```

Optional recordkeeping:

```text
Proposals/Approved/meeting-followup/<proposal-id>/
Proposals/Rejected/meeting-followup/<proposal-id>/
```

Approval is represented by maintainer action in Drive/local files, not by chat approval.

## 5. Refresh

Prompt:

```text
Refresh Test Plugin
```

Expected:

- Cowork reads Drive canonical `SKILL.md` files.
- If installed content differs, Cowork rebuilds the whole `Test Plugin` plugin artifact and shows **Save plugin**.
- If installed content already matches Drive, Cowork reports no rebuild is required.
- Plugin id remains `test-plugin`.
- No `aiws-generated-plugin`.
- No `test-plugin--meeting-followup`.
- No AIWS marketplace/materialize/export/draft language.

## 6. Validate Library And Installed Plugin

Prompt:

```text
Validate the Test Plugin Drive library and include installed plugin status
```

Expected sections:

- `AIWS Skill Library Validation`
- `Skills`
- `Metadata`
- `Proposals`
- `Phase 1 boundaries`
- `Installed Cowork plugin`

Expected installed status:

```text
test-plugin: present
skills visible: PASS
```

Use this prompt for the demo. The shorter prompt `Check Test Plugin` is ambiguous in Cowork and may route to a generic installed-plugin summary.

## 7. Use Updated Skill

Prompt:

```text
Use meeting-followup
```

Paste minimal notes again and continue.

Expected:

- Cowork routes to `meeting-followup`.
- The first output line reflects the canonical Drive marker.

## Pass Criteria

The demo passes when:

- Drive folder installs as one Cowork plugin/container.
- Both skills are visible under `Test Plugin`.
- `meeting-followup` runs.
- Proposal lands under `Proposals/Submitted/...`.
- Maintainer can review plain Markdown.
- Refresh updates or confirms installed plugin content from Drive.
- Validation checks Drive source first and installed plugin status second.
- No marketplace, materialize, export, draft, bridge, ZIP upload, or RPM path appears in the normal user flow.

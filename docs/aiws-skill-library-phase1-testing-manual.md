# AIWS Skill Library Phase 1 Testing Manual

## Summary

This manual tests the Phase 1 Drive Skill Library path using human prompts. The Drive folder is the source of truth. Cowork installs and refreshes a plugin-like container generated from the Drive folder.

Demo library:

```text
Test Plugin
```

Drive shape:

```text
Test Plugin/
  skills/
    meeting-followup/
      SKILL.md
    morning-briefing/
      SKILL.md
  Proposals/
    Submitted/
    Approved/
    Rejected/
```

## Test 1: Install

User prompt:

Install Test Plugin from this Drive folder: `<folder-url>`

Expected:

- Cowork reads the Drive folder.
- Cowork packages one plugin artifact for `Test Plugin`.
- Cowork presents one **Save plugin** card.
- It does not present separate **Save skill** cards.
- It does not mention AIWS marketplace, materialize, export, drafts, or missing `plugins/`.

Pass after Save:

- `test-plugin:meeting-followup` is visible.
- `test-plugin:morning-briefing` is visible.

## Test 2: Propose

User prompt:

Propose this meeting-followup change for Test Plugin: change the marker line to `> meeting-followup update`.

Expected:

- Proposal is written under `Proposals/Submitted/meeting-followup/<proposal-id>/`.
- Proposal contains `SKILL.md` and `aiws.proposal.json`.
- Canonical `skills/meeting-followup/SKILL.md` is not changed.
- Output includes a local diff command for VS Code/VSCodium or Meld.

## Test 3: Review

Maintainer action:

Compare the canonical meeting-followup SKILL.md with the submitted proposal in VS Code/VSCodium or Meld.

Expected:

- Maintainer reviews plain Markdown.
- Maintainer applies accepted changes directly to canonical `skills/meeting-followup/SKILL.md`.
- Maintainer may optionally move/copy the proposal folder to `Proposals/Approved/meeting-followup/<proposal-id>/` for recordkeeping.

## Test 4: Refresh

User prompt:

Refresh Test Plugin

Expected:

- First action is reading Drive `skills/<skill-id>/SKILL.md`.
- Cowork validates the Drive library.
- Cowork rebuilds the whole `Test Plugin` plugin artifact from the Drive root.
- Plugin id remains `test-plugin`.
- It does not create draft packages.
- It does not create `test-plugin--meeting-followup`.
- It does not use AIWS marketplace/materialize/export tools.
- It does not require a `plugins/` folder.
- It presents **Save plugin** if user confirmation is needed.

Pass after Save:

- Refresh report is `AIWS Skill Library Refresh: PASS`.
- `test-plugin:meeting-followup` is visible and invocable.
- `test-plugin:morning-briefing` is visible and invocable.
- `meeting-followup` reflects the canonical Drive marker line.

## Test 5: Check

User prompt:

Check Test Plugin

Expected:

- Cowork reports that `Test Plugin` is installed.
- Both skills are visible.
- Proposal folders are not installed as runnable skills.

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
- It does not create or present a `.skill` artifact.
- It does not mention AIWS marketplace, materialize, export, drafts, or missing `plugins/`.

Pass after Save:

- `test-plugin:meeting-followup` is visible.
- `test-plugin:morning-briefing` is visible.

## Test 2: Propose

User prompt:

Propose this meeting-followup change for Test Plugin: change the marker line to `> meeting-followup demo proposal`.

Expected:

- First action is reading Drive `skills/meeting-followup/SKILL.md`.
- Proposal is written under `Proposals/Submitted/meeting-followup/<proposal-id>/`.
- Proposal contains `SKILL.md` and `aiws.proposal.json`.
- Canonical `skills/meeting-followup/SKILL.md` is not changed.
- Output includes a local diff command for VS Code/VSCodium or Meld.
- It does not mention AIWS marketplace, materialize, export, drafts, host install, bridge, or package rebuilds.
- It asks for missing information only when the proposal cannot be written safely.

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
- Plugin id remains `test-plugin`.
- If installed content already matches Drive canonical content, Cowork reports that no rebuild is required.
- If installed content differs from Drive canonical content, Cowork rebuilds and preflights the whole `Test Plugin` plugin artifact from the Drive root.
- It presents one **Save plugin** card in the current Cowork session when rebuilt content needs user confirmation.
- It does not create draft packages.
- It does not create `test-plugin--meeting-followup`.
- It does not create or report `aiws-generated-plugin` as the refreshed plugin identity.
- It does not use AIWS marketplace/materialize/export tools.
- It does not report marketplace state, empty marketplace state, or materialized skill state in the normal user-visible path.
- It does not require a `plugins/` folder.
- It uses manual plugin-management reinstall instructions only if the current host cannot read Drive, build/preflight the artifact, or present the **Save plugin** card.

Pre-click checkpoint:

- If Cowork rebuilt the artifact and is waiting for the user click, refresh report is `AIWS Skill Library Refresh: READY FOR SAVE`.
- Cowork presents one **Save plugin** card for `Test Plugin`.

Final pass:

- Refresh report is `AIWS Skill Library Refresh: PASS` when installed content was already in sync or after Cowork accepts the refreshed plugin.
- `test-plugin:meeting-followup` is visible under `Test Plugin`.
- `test-plugin:morning-briefing` is visible under `Test Plugin`.
- Installed `meeting-followup/SKILL.md`, when inspectable, matches the canonical Drive `SKILL.md`.
- If the refresh did not invoke a skill, invocation status may be reported as `not verified` or `optional`; that is not a refresh failure.

Live invocation check:

User prompt:

Use meeting-followup

Expected:

- Cowork routes to the `meeting-followup` skill.
- If Cowork asks for meeting details, provide minimal notes and continue.
- The first output line reflects the canonical Drive marker. In the current demo, that marker is:

```text
> meeting-followup demo proposal
```

## Test 5: Check

User prompt:

Validate the Test Plugin Drive library and include installed plugin status

Do not use `Check Test Plugin` as the main demo prompt. In Cowork it can route to a generic installed-plugin summary instead of the Drive library validation skill.

Expected:

- First action is reading the Drive `Test Plugin` library source, not the installed plugin copy.
- It checks `skills/meeting-followup/SKILL.md` and `skills/morning-briefing/SKILL.md`.
- It checks `Proposals/Submitted/`, `Proposals/Approved/`, and `Proposals/Rejected/`.
- Cowork reports that `Test Plugin` is installed.
- Both skills are visible.
- Proposal folders are not installed as runnable skills.
- It validates the Drive library and proposal folders without changing anything.
- It reports installed plugin status only as secondary evidence after Drive validation.
- It includes an installed plugin section; if Cowork visibility cannot be checked, that section says `not verified`.
- It does not mention AIWS marketplace, materialize, export, drafts, host install, bridge, or package rebuilds.
- It does not ask for **Save plugin** unless the user asked to refresh or install.

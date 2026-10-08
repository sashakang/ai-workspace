# core-aiws v0.5.6 smoke test

**Release**: `3ff6fb4` on `sashakang/ai-workspace` master, tagged `v0.5.6`.
**Targets**: what changed since 0.5.3: supporting files packaged with skills (v0.5.4), library-root rule, `Accept proposal` apply mode, and the plugin version taken from `aiws.library.json` (v0.5.5, v0.5.6).
**Scope**: a short pass over the new behaviour. The full flow is in [aiws-skill-library-phase1-testing-manual.md](aiws-skill-library-phase1-testing-manual.md).

Run the tests in order: each starts from the state the previous one left. Send each prompt as its own message. Any library works; the prompts use `Test Plugin`, so substitute your library's folder name.

## Pre-conditions

- `core-aiws` updated to 0.5.6 in Cowork (sync the `sashakang/ai-workspace` marketplace, update core-aiws), then a fresh Cowork chat so the new skill text loads.
  - Check: ask `Which version of core-aiws is installed?`, or open `.../cowork_plugins/cache/<...>/core-aiws/.claude-plugin/plugin.json`; `version` is `0.5.6`.
- Google Drive connected with **write** access, and your account can edit the library folder (you act as maintainer).
- `test-plugin` installed from the library (testing manual Step 2).
- Test Plugin library: <https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L>. Its `aiws.library.json` has no `plugin_version` yet, and there is no `Archive/` folder.

## Test 1: Library without a version

```text
Validate the Test Plugin Drive library and include installed plugin status
```

**Pass**: validation passes with `WARN: library has no plugin_version`.

## Test 2: Bump prompt creates the version

```text
Bump plugin version for Test Plugin
```

**Pass**:

- Report line `Plugin version: <none> -> 1.0.1` (or similar wording ending in `1.0.1`). Nothing is validated or refreshed.
- In Drive, the library root has exactly one `aiws.library.json`. Open it: plain JSON (not a Google Doc), all old fields kept, plus `"plugin_version": "1.0.1"`.
- The old file is at `Archive/aiws.library/<today>-unversioned/aiws.library.json`.
- No `aiws.library.json.incoming` is left at the root.

Then:

```text
Refresh Test Plugin
```

**Pass**: `PASS`, no rebuild required, no Save plugin card. A version change alone is not a rebuild: the skill files did not change, so the installed plugin stays at its old version until Test 3.

## Test 3: Direct edit without a bump is caught

Create two files on your computer **now** (after Test 2's bump, so they are newer than `aiws.library.json`) and upload them to Drive under `skills/morning-briefing/` (Drive's web UI can't create `.md` or `.py` files; uploading or the Drive desktop folder both work):

- `references/notes.md` with any text,
- `scripts/helper.py` with any text.

```text
Refresh Test Plugin
```

**Pass**: `AIWS Skill Library Refresh: NEEDS MANUAL ACTION`, the report names `skills/morning-briefing/references/notes.md` as newer than `aiws.library.json` (the script is not packaged, so it is not named), asks for `Bump plugin version for Test Plugin` (the wording may add `past <version>`; either is fine), and shows **no** Save plugin card.

Then send these as two separate messages:

```text
Bump plugin version for Test Plugin
```

```text
Refresh Test Plugin
```

**Pass**:

- The bump reports `1.0.1 -> 1.0.2`; the old file lands in `Archive/aiws.library/<today>-1.0.1/`.
- Refresh: `READY FOR SAVE` at `1.0.2`, `Supporting files packaged:` lists `skills/morning-briefing/references/notes.md`, `Skipped files:` lists `skills/morning-briefing/scripts/helper.py - script`. Click **Save plugin**.

## Test 4: Accept proposal

Create a local user skill `morning-briefing` from the canonical one with any visible change (testing manual Step 3 shows how to create a local skill, Step 7 how to edit it), then:

```text
Propose this morning-briefing change for Test Plugin: use my current local morning-briefing SKILL.md as the proposed content.
```

Note the proposal id from the report. First try accepting while it is still in Submitted:

```text
Accept proposal <proposal-id> for Test Plugin
```

**Pass**: refused, telling you to move the folder from Submitted to Approved yourself. Nothing changes in `skills/`.

In Drive, move `Proposals/Submitted/morning-briefing/<proposal-id>/` to `Proposals/Approved/morning-briefing/` (create that folder). Run the same Accept prompt again.

**Pass**:

- `skills/morning-briefing/` holds exactly one `SKILL.md`, equal to the proposal. `references/` and `scripts/` are untouched.
- The old canonical is at `Archive/morning-briefing/<today>-<proposal-id>/SKILL.md`.
- Report line `Plugin version: 1.0.2 -> 1.0.3`; validation passes; one **Save plugin** card at `1.0.3`. Click it.
- The refresh part may add `Personal copy shadowing library skill: morning-briefing`. That is a warning about your local copy, not a failure.

Run the Accept prompt a third time.

**Pass**: reports the canonical is already in sync, `Plugin version: 1.0.3, already current`, no new bump, no new archive folder. If a Save plugin card appears (possible when Cowork wasn't restarted after the last Save), don't click it.

## Test 5: Link to a folder that is not the library root

```text
Install Test Plugin from this Drive folder: <link to Test Plugin/skills/>
```

**Pass**: `AIWS Drive Skill Library Install: FAIL`, saying the linked folder has no `skills/` directly inside it. No Save plugin card.

## Cleanup

1. Delete `skills/morning-briefing/references/` and `skills/morning-briefing/scripts/`.
2. To restore the original `morning-briefing`, move the archived `SKILL.md` from `Archive/morning-briefing/<today>-<proposal-id>/` back into `skills/morning-briefing/` and trash the accepted one.
3. Send `Bump plugin version for Test Plugin`, then `Refresh Test Plugin`, and click **Save plugin**. Deletions and moves leave no newer file behind, so only a bump ships them; skipping it makes the next refresh stop with `NEEDS MANUAL ACTION`.
4. Remove the local `morning-briefing` user skill via Cowork's skill panel.

Leave `aiws.library.json` and `Archive/` in place; never lower `plugin_version` by hand. The accepted proposal stays in `Proposals/Approved/morning-briefing/`, so run the testing manual's Reset before a full manual run.

## What to send back

For each test: PASS or FAIL, and for any FAIL the full report text and a screenshot of the Drive folder involved.

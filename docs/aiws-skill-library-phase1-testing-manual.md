# AIWS Skill Library Phase 1 Testing Manual

## Summary

This manual exercises the Phase 1 Drive Skill Library path as a 10-step end-to-end demo for `Test Plugin`. The Google Drive folder is the source of truth. Cowork installs and refreshes a plugin-like container generated from that folder. AIWS supplies the install, propose, refresh, and validate skills. AIWS does not run skills.

Key principle: AIWS only enters when the user explicitly proposes a change or asks to install/refresh/validate. Local skill authoring and local skill use are plain Cowork operations with no AIWS involvement.

Every AIWS service procedure in this manual ends with a short self-improvement checkpoint. The checkpoint does not mutate Drive, rebuild packages, or edit skills. It names one actionable follow-up improvement when the run exposed confusing wording, bad routing, missing validation, or a recurring manual workaround. If there is no useful follow-up, it says `No self-improvement action identified`.

Demo library:

```text
Test Plugin
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Demo Drive shape (starting state):

```text
Test Plugin/
  aiws.library.json
  skills/
    morning-briefing/
      SKILL.md
    slack-response-triage/
      SKILL.md
  Proposals/
    Submitted/
    Approved/
    Rejected/
```

Demo skill being built: `schedule-summary`.
Background canonical skills (not touched by the demo): `morning-briefing`, `slack-response-triage`.

## Preconditions

- AIWS plugin (core-aiws ≥ 0.4.23) is installed in Cowork and reachable.
- Google Drive integration is connected and can read the Test Plugin folder.
- The Drive root folder name is exactly `Test Plugin`.
- The tester knows how to author a local Cowork user skill (Cowork's native local-skill mechanism). The manual treats the local-skill location as host-defined and does not pin a filesystem path.
- Both natural prompts (`Use schedule-summary`) and slash commands (`/test-plugin:schedule-summary`) are accepted. Natural prompts are the documented form.

## Reset To Starting State

Cowork can reach the locally synced Google Drive folder for `Test Plugin` and its own installed plugins and user skills. The tester resets the demo by prompting Cowork, not by editing the Drive UI manually.

On macOS the bash sandbox cannot directly write to the user's local filesystem, so Cowork performs Drive-sync deletions via the `Control your Mac` surface (`osascript`). This is expected and acceptable. Other hosts may use a different mechanism; the tester should not interpret the choice of execution surface as a failure.

User prompt:

```text
Reset the Test Plugin demo environment. In the Test Plugin Drive folder, delete skills/meeting-followup/ and skills/schedule-summary/ if present, and empty Proposals/Submitted/, Proposals/Approved/, and Proposals/Rejected/. Keep skills/morning-briefing/, skills/slack-response-triage/, and aiws.library.json untouched. Then uninstall test-plugin from Cowork if installed, and remove the local schedule-summary user skill if present. Show me each deletion before executing.
```

Expected:

- Cowork lists every path it intends to delete and waits for confirmation before each deletion (per standard "never delete without confirmation" behavior).
- On macOS, Drive-sync deletions are executed via `osascript` (Control your Mac). The Cowork transcript should show `osascript` calls performing `rm` or `mv` against paths under the local Drive sync root.
- After confirmations:
  - Drive `Test Plugin/skills/` contains only `morning-briefing/` and `slack-response-triage/`.
  - Drive `Test Plugin/Proposals/Submitted/`, `Approved/`, `Rejected/` are empty.
  - Drive `Test Plugin/aiws.library.json` is unchanged.
  - Cowork reports `test-plugin: not installed`.
  - The local `schedule-summary` user skill is gone.
- Cowork does NOT delete `skills/morning-briefing/`, `skills/slack-response-triage/`, or `aiws.library.json` under any circumstance.
- If AIWS handled the reset, the report ends with a self-improvement checkpoint.

If Cowork cannot reach the local Drive sync path on the current host, fall back to manual deletion in the Drive UI for the Drive operations only; Cowork operations (uninstall, remove local skill) are still prompted.

### Cowork persistence asymmetry — important for reset

Cowork's plugin registry and its local user-skill registry behave differently when a running Cowork process is involved:

- **Plugins (`test-plugin`, `rpm/plugin_*/`, `rpm/manifest.json`)**: filesystem-driven. Removing the rpm/manifest.json entry plus the plugin directory works durably. A running Cowork process may re-create the plugin directory on disk from in-memory state, so file-side deletion is reliable only after Cowork quits OR when the uninstall goes through Cowork's plugin panel.
- **Local user skills (`anthropic-skills:<name>`, `skills-plugin/.../manifest.json`, `skills-plugin/.../skills/<name>/`)**: in-memory-driven. Cowork writes its in-memory skill index back to disk on quit, **overwriting any file-side deletions made while the process was running**. The only reliable way to remove a local user skill is through Cowork's skill panel UI — file-side delete alone does not survive Cowork's next quit cycle.

Implications for reset:

- To remove `test-plugin`: prefer Cowork UI uninstall. File-side cleanup also works if Cowork is quit immediately afterward.
- To remove a local `anthropic-skills:<name>` user skill: use Cowork's skill panel UI. File-side delete will be undone by the next Cowork quit.

## Step 1: Verify AIWS Reachable, Drive Clean, test-plugin Not Installed

User prompt:

```text
Validate the Test Plugin Drive library and include installed plugin status
```

Pass requires all of the following:

- AIWS plugin responds; validation report renders.
- Installed Cowork plugin section reports `test-plugin: not installed` or `test-plugin: missing` (either wording is acceptable).
- `test-plugin:morning-briefing` is NOT visible in Cowork.
- `test-plugin:slack-response-triage` is NOT visible in Cowork.
- `test-plugin:schedule-summary` is NOT visible in Cowork.
- Drive `skills/` contains exactly two entries: `morning-briefing`, `slack-response-triage`.
- Drive `skills/meeting-followup/` is NOT present.
- Drive `skills/schedule-summary/` is NOT present.
- Drive `Proposals/Submitted/` is empty.
- Drive `Proposals/Approved/` is empty.
- Drive `Proposals/Rejected/` is empty.
- `aiws.library.json` (if used) reports `id=test-plugin`, `display_name=Test Plugin`, `source=google_drive`.

The validation output may also include informational sections that are not pass/fail signals:

- `Fixes:` — next-step suggestions, e.g., install `test-plugin`. Expected at this stage; not a failure.
- `Sources:` — Drive links to the validated files. Informational only.
- `Self-improvement:` — one follow-up improvement or `No self-improvement action identified`.

If any assertion fails, run the Reset procedure and re-run Step 1. Do not proceed to Step 2 until Step 1 passes.

## Step 2: Install Test Plugin From Drive

User prompt:

```text
Install Test Plugin from this Drive folder:
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Expected:

- Cowork reads the Drive folder.
- AIWS packages one plugin artifact named `Test Plugin` with plugin id `test-plugin`.
- Cowork presents exactly one **Save plugin** card for a `.plugin` artifact.
- Preflight checks PASS (manifest, contract, archive layout, skill frontmatter).
- Report header is `AIWS Drive Skill Library Install: READY FOR SAVE` while waiting for the click, and `PASS` after Cowork accepts.
- Default `plugin.json` fields when `aiws.library.json` does not specify them: `version=0.1.0`, `author.name` defaults to the active Cowork user's display name (e.g., `Sasha Kang`). Either default may be overridden by an explicit field in `aiws.library.json`.
- The install report may include a `Sources:` section with Drive links. Informational only.
- The install report ends with `Self-improvement:` and either a concrete follow-up or `No self-improvement action identified`.

After clicking Save plugin:

- `test-plugin:morning-briefing` is visible.
- `test-plugin:slack-response-triage` is visible.
- `test-plugin:schedule-summary` is NOT visible (not yet canonical).
- `Proposals/` subfolders are not installed as runnable skills.

Failure modes — do NOT click; report `NEEDS RETRY` or `FAIL`:

- A `.skill` artifact is presented.
- A **Save skill** card is presented for Test Plugin.
- Errors like `Zip must contain exactly one top-level folder` or `Zip must contain exactly one SKILL.md file`.
- The artifact identity is `aiws-generated-plugin`.
- The plugin id is reported as `test-plugin--<skill-id>`.

Regression guard: core-aiws 0.4.21 (`5bd2147`) rejects skill-card Drive library installs. If a Save skill card appears, the guard has regressed.

## Step 3: Author And Use schedule-summary As A Local Skill (No AIWS)

The user authors the skill as a plain local Cowork user skill. No AIWS tool is involved in this step. This step is independent of whether AIWS is installed at all.

How local user skills are registered on Cowork: the plugin's `manifest.json` (under `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<plugin-uuid>/<install-uuid>/manifest.json` on macOS) is the source of truth. Cowork rebuilds the `skills/<name>/` directory from manifest entries on every startup and wipes anything not listed. Writing SKILL.md directly into the plugin's `skills/` directory does **not** survive a restart — no manifest entry, no skill. The durable registration mechanism is a `.skill` artifact installed via the **Save skill** card, which writes both the manifest row (with a generated `skillId` and `creatorType: "user"`) and the SKILL.md.

User prompt:

```text
Create a local Cowork user skill named `schedule-summary` with the following SKILL.md body:

---
name: schedule-summary
description: Summarize my schedule for a given period (today, tomorrow, yesterday, this week, next week, or a specific date range).
---

# Schedule Summary

Use this skill when the user asks for a recap of their calendar over a specific period — for example "what's on my calendar today", "summarize tomorrow", "what did I do yesterday", "what's happening this week".

Always begin the output with this exact debug line so the user can verify which version of the skill is running:

> schedule-summary v1: running

Resolve the period from the user's request:
- today, yesterday, tomorrow
- this week, next week, last week
- explicit dates ("on 2026-06-03", "next Tuesday")
- ranges ("June 3 to June 7")

If the period is ambiguous, ask one short clarifying question before fetching.

If calendar tools are available, fetch events in the requested period in the user's local timezone. If calendar tools are unavailable, ask the user to paste their calendar entries.

Produce a compact summary in the chat:

## Period
The resolved date range in the user's local timezone.

## Events
For each event:
- time (start–end, local timezone)
- title
- attendees if any
- location or call link if present

## Focus blocks
Contiguous gaps ≥ 90 minutes between meetings.

## Notable
- back-to-back meetings with no break
- meetings outside working hours
- declined or tentative events the user has not yet confirmed

Keep the summary compact. Do not invent events, attendees, or details.
```

Expected packaging behavior:

- Cowork writes the SKILL.md content to a working directory, runs `package_skill.py` (from the `skill-creator` plugin) to produce a `schedule-summary.skill` zip, and presents that artifact via `mcp__cowork__present_files`. The resulting card shows a **Save skill** button.
- Cowork does NOT invoke `Use skill-creator` for this — the full skill-creator workflow is a heavy iterative draft/eval loop and is overkill when the SKILL.md body is already in hand. Plain `package_skill.py` + `present_files` is the lighter path.
- No AIWS tool is invoked. No Drive read or write occurs.

After clicking **Save skill** on the card:

- Cowork registers a new entry in `manifest.json` with a generated `skillId` (e.g., `skill_01...`) and `creatorType: "user"`.
- Cowork writes the SKILL.md to the plugin's `skills/schedule-summary/SKILL.md`.
- The skill surfaces as `anthropic-skills:schedule-summary` (the local-skill namespace on this host).
- The registration survives Cowork restart.

Then run:

```text
Use schedule-summary
```

Expected invocation behavior:

- Cowork resolves to the newly registered local user skill.
- First output line: `> schedule-summary v1: running`. This is the version debug marker — testers should treat the line as the primary signal that the v1 skill loaded.
- Output matches the section structure above (compact, chat Markdown — no HTML at this stage).
- `Test Plugin` on Drive is unchanged. `skills/schedule-summary/` does not exist canonically.

## Step 4: User Proposes The New Skill → Maintainer Accepts

This is the first step where AIWS enters.

### 4.1 Submit proposal

User prompt:

```text
Propose this new skill for Test Plugin: schedule-summary. Use my local schedule-summary SKILL.md as the proposed content.
```

Expected:

- AIWS proposal flow runs.
- A folder is created on Drive: `Proposals/Submitted/schedule-summary/<proposal-id>/`. Observed proposal-id convention: `proposal-YYYY-MM-DD-<change-description>`, e.g. `proposal-2026-05-27-add-schedule-summary`.
- That folder contains `SKILL.md` (the user's local content) and `aiws.proposal.json`.
- `aiws.proposal.json` proposer identity defaults to the active Cowork user email (e.g., `owner@example.com`) when not explicitly specified.
- Drive `skills/schedule-summary/` does NOT exist yet (no canonical).
- No package rebuild. No **Save plugin** card. No marketplace/materialize/export language.

### 4.2 Maintainer review

Maintainer action: open `Proposals/Submitted/schedule-summary/<proposal-id>/SKILL.md` locally and read it standalone. There is no canonical file to diff against because this is a brand-new skill.

### 4.3 Maintainer accept

**Role boundary**: Step 4.3 is a deliberate maintainer action. The assistant must NOT auto-execute it immediately after Step 4.1 / Step 4.2. Wait for an explicit maintainer signal (e.g., `accept as maintainer`, `approve`, `do it`) before touching canonical or deleting the proposal folder. In single-user demos where the proposer and the maintainer are the same person, the explicit signal is still required — it's the role transition that matters, not the identity of the actor.

Maintainer action on Drive:

- Create `skills/schedule-summary/SKILL.md` with the accepted content. This is a new file under `skills/`; do not move files out of `Proposals/Submitted/` into `skills/`.
- Delete the entire `Proposals/Submitted/schedule-summary/<proposal-id>/` folder, including both `SKILL.md` and `aiws.proposal.json`. Drive version history preserves the proposal contents if needed later.
- `Proposals/Approved/` and `Proposals/Rejected/` stay empty. No archive movement.

Rationale: Step 1's validation asserts `Proposals/Submitted/` is empty, so the proposal folder must be cleared. `aiws.proposal.json` next to a canonical `SKILL.md` would pollute the canonical folder — the install/refresh flow expects only `SKILL.md` under `skills/<skill-id>/`.

## Step 5: User Refreshes Test Plugin

User prompt:

```text
Refresh Test Plugin
```

Expected:

- AIWS reads Drive canonical `SKILL.md` files first.
- AIWS compares installed Cowork plugin content.
- Installed plugin had 2 skills (`morning-briefing`, `slack-response-triage`); Drive now has 3 (`morning-briefing`, `slack-response-triage`, `schedule-summary`).
- AIWS rebuilds the `.plugin` artifact, bumps `plugin.json.version` to a new non-empty value greater than installed, and preflights. Observed bump convention when adding a new skill: minor bump (e.g., `v0.1.0 → v0.2.0`). The exact bump is not enforced; any version strictly greater than installed satisfies the contract.
- Cowork presents one **Save plugin** card.
- Report header: `AIWS Skill Library Refresh: READY FOR SAVE` or `AIWS Skill Library Update: READY FOR SAVE`. Either label is accepted.
- After Save: report header becomes `PASS`.

After clicking Save plugin:

- `test-plugin:schedule-summary` is visible.
- `test-plugin:morning-briefing` is still visible.
- `test-plugin:slack-response-triage` is still visible.
- Plugin id remains `test-plugin`.

Failure modes — do NOT click:

- A `.skill` artifact or **Save skill** card.
- Per-skill plugin id `test-plugin--schedule-summary`.
- Plugin identity `aiws-generated-plugin`.
- Refresh report mentions marketplace, materialize, export, bridge, draft packages, or a missing `plugins/` folder.

If installed content already matched Drive (it shouldn't in this demo), AIWS reports no rebuild required and the refresh report header is `PASS`.

### Cleanup after refresh

Default policy: once Save plugin completes and the installed `test-plugin:<skill-name>` reflects the canonical content, remove the local `anthropic-skills:<skill-name>` user skill **only if its body is byte-identical to the last submitted proposal** (i.e., the local has not been edited since the user proposed it). The plugin canonical then becomes the single source of truth; Cowork resolution stays unambiguous and there is no risk of "did I edit the local or the canonical" confusion.

Do NOT remove the local skill if:

- the local body has been edited since the last propose (the user is mid-iteration on v.N+1 after v.N was just accepted), or
- there is no record of a recent propose for this skill (the local copy may contain unsubmitted work).

In either case, leave the local override in place. Run the cleanup only after the next propose+accept+refresh cycle confirms the new canonical AND the local matches what was just proposed.

Mechanical check: byte-compare the local user skill's SKILL.md against the SKILL.md inside the most recent `Proposals/Submitted/<skill-id>/<proposal-id>/` (or, if the proposal folder was already deleted, against current canonical). Match → safe to remove. Differ → keep local.

**Mechanism for removal**: per the Cowork persistence asymmetry note at the top of this manual, removing a local user skill requires Cowork's skill panel UI. File-side delete of the `skills-plugin/.../skills/<name>/` directory and the manifest entry is insufficient — Cowork writes its in-memory state back on quit and resurrects the deletion. The tester runs the byte-identity check, then opens Cowork's skill panel and removes the entry.

Observed refresh report fields: `Library:`, `Skill(s):`, `Canonical SKILL.md verified:`, `Proposal sync evidence:`, `Library validation:`, `Cowork refresh/reinstall:`, `Skill invocation:`. The exact field set may vary; the headline `READY FOR SAVE | PASS | FAIL | NEEDS MANUAL ACTION` is the authoritative pass/fail signal.

`Proposal sync evidence` is a useful diagnostic: it reports whether `Proposals/Submitted/<skill>/` content matches canonical and whether `Approved/`/`Rejected/` are empty. If the maintainer has not yet deleted the proposal folder after accepting (Step 4.3 / Step 9), expect a line like `Submitted/<skill> matches canonical` — that's an acceptable transient state, but Step 1 of the next demo run will fail the `Submitted/ empty` assertion until cleanup runs.

Known failure mode (degenerate refresh): if the refresh report says `NEEDS MANUAL ACTION`, `Canonical SKILL.md verified: FAIL`, or `no skills discoverable`, the refresh skill has fallen back to AIWS-internal Drive indexing instead of reading the Drive folder directly through the host's Google Drive integration. This is a skill bug, not a Drive problem. Recover with one of:

1. Retry the same `Refresh Test Plugin` prompt.
2. Re-prompt directively:

```text
Refresh Test Plugin. Read canonical SKILL.md files via the Google Drive integration (the same way the install and validate flows do). Do not rely on AIWS marketplace indexing — this Drive folder is a Skill Library, not a marketplace.
```

3. As a last resort, force a rebuild via the install path: `Install Test Plugin from this Drive folder: <url>`. This regenerates the artifact and presents Save plugin.

## Step 6: User Runs The Skill From The Plugin

User prompt:

```text
Use schedule-summary
```

Expected:

- Cowork resolves the skill. The local user skill from Step 3 may still exist; both copies are now identical in content, so the marker is the same either way.
- First output line: `> schedule-summary v1: running`.
- Section structure matches the canonical SKILL.md (Period / Events / Focus blocks / Notable).
- Output is chat Markdown. No HTML file is produced at this stage.

If the tester wants to verify routing to the plugin specifically, temporarily remove the local user skill and re-run. The marker should still be `> schedule-summary v1: running` because canonical was created from the same content.

## Step 7: User Updates The Local Copy And Uses It (No AIWS)

AIWS does not enter this step. This is plain local iteration.

User action:

- Edit the local Cowork user skill `schedule-summary` to add a new feature. The demo modification adds an HTML-report output mode.
- If no local copy exists (the tester removed it after Step 6), recreate one by copying current canonical from Drive into the local Cowork user-skill location.
- Change the marker line in the local SKILL.md to `> schedule-summary v2: running`.

Suggested v.2 deltas (example):

- Marker becomes `> schedule-summary v2: running`.
- Output instructions change from "Produce a compact summary in the chat" to: "Generate a self-contained HTML file and save it as `schedule_summary_{period-slug}_{YYYYMMDD}.html` in the outputs folder, then present it with a `computer://` link. The HTML keeps the same sections (Period / Events / Focus blocks / Notable) but uses styled cards: events as a chronological card list with start–end time chips, focus blocks highlighted in green, notable items called out with colored badges. Clean modern styling: sans-serif, white cards on light-grey background, subtle shadows."

User prompt:

```text
Use schedule-summary
```

Expected:

- Cowork resolves the local user skill (local overrides same-id plugin skill).
- First output line: `> schedule-summary v2: running` (or the local marker the user wrote).
- Output is now an HTML file at `outputs/schedule_summary_*.html`, presented via a `computer://` link in chat.
- No AIWS tool is invoked. No Drive read or write occurs.
- Drive canonical `skills/schedule-summary/SKILL.md` is unchanged.

Assumption flagged: this step assumes Cowork's skill resolution prefers a local user skill over a same-id plugin skill. If Cowork resolves to the plugin instead, the tester should temporarily uninstall the plugin or rename the local skill to confirm the local copy works, then restore plugin install before Step 8.

## Step 8: User Proposes The Changes

User prompt:

```text
Propose this schedule-summary change for Test Plugin: use my current local schedule-summary SKILL.md as the proposed content.
```

Expected:

- AIWS proposal flow runs.
- A new folder is created on Drive: `Proposals/Submitted/schedule-summary/<proposal-id-2>/`.
- That folder contains `SKILL.md` (the v.2 local content) and `aiws.proposal.json`.
- Drive canonical `skills/schedule-summary/SKILL.md` is unchanged.
- Output includes a local diff command, for example:

```text
code --diff "<drive-local>/Test Plugin/skills/schedule-summary/SKILL.md" "<drive-local>/Test Plugin/Proposals/Submitted/schedule-summary/<proposal-id-2>/SKILL.md"
```

- No package rebuild, no **Save plugin** card, no marketplace/materialize/export language.

## Step 9: Maintainer Accepts (Full Or Partial)

**Role boundary** (same as Step 4.3): Step 9 is a deliberate maintainer action. Do not auto-execute after Step 8. Wait for an explicit maintainer signal.

Maintainer reviews the diff and decides per-change. The accept can be full (canonical is overwritten with the proposed body) or partial (canonical is hand-edited to incorporate accepted parts and reject others).

Maintainer action on Drive:

- Open canonical `skills/schedule-summary/SKILL.md` and the submitted proposal `SKILL.md` side by side in VS Code/VSCodium (`code --diff`) or Meld.
- Edit canonical directly to incorporate accepted parts. Apply maintainer-authored edits where partial acceptance requires rewriting. Leave rejected parts out. Do not move files from `Proposals/Submitted/` into `skills/`.
- Delete the entire `Proposals/Submitted/schedule-summary/<proposal-id-2>/` folder, including both `SKILL.md` and `aiws.proposal.json`. Drive version history preserves the proposal contents if needed later.
- `Proposals/Approved/` and `Proposals/Rejected/` stay empty. No archive movement.

Outcome:

- Canonical `skills/schedule-summary/SKILL.md` now reflects the partial-accept content. The new marker on canonical may be `> schedule-summary v2: running`, or a different marker chosen by the maintainer.

## Step 10: User Refreshes And Verifies Canonical Reached The Installed Plugin

Precondition: the tester has the existing `test-plugin` install from Step 2 / Step 5 and possibly a stale local `schedule-summary` user skill (if Step 5.1 cleanup did not apply because the local was no longer byte-identical to the last proposal).

This step tests the propagation path that Step 2 did not cover: an **existing install** picks up a post-acceptance canonical change.

(Fresh installation against the post-acceptance canonical is mechanically identical to Step 2 and exercises no new contract; it is not part of this demo. A separate "new installer onboarding" verification can run Step 2 against the post-acceptance Drive state if a different tester is available.)

User prompt:

```text
Refresh Test Plugin
```

Expected:

- AIWS reads Drive canonical first.
- AIWS detects that the installed plugin's `schedule-summary` content differs from Drive canonical (v.2 was accepted in Step 9).
- AIWS rebuilds the `.plugin` artifact with a bumped `plugin.json.version` (observed convention: patch bump for a content-only change, e.g. `v0.2.0 → v0.2.1`).
- Preflight passes; Cowork presents one **Save plugin** card.
- Report header: `AIWS Skill Library Refresh: READY FOR SAVE` (or `Update`).

After clicking Save plugin:

- `test-plugin:schedule-summary` in the installed plugin reflects the partial-accepted canonical content.
- Plugin id remains `test-plugin`. No per-skill plugin id.

User prompt:

```text
Use schedule-summary
```

Expected:

- If a local user skill `schedule-summary` still exists, Cowork resolves to local and the canonical update is not observed. To verify the canonical reached the plugin, remove the local user skill via Cowork's skill panel (or wait for Step 5.1 cleanup to run when the local matches the last proposal), then re-run `Use schedule-summary`.
- First output line matches the partial-accepted canonical marker — e.g. `> schedule-summary v2: running` or whatever the maintainer wrote at Step 9.

## Final Pass Criteria

Demo passes when all of the following are true at the end of Step 10:

- Drive `skills/schedule-summary/SKILL.md` reflects the partial-accept content from Step 9.
- Drive `skills/morning-briefing/SKILL.md` is unchanged from starting state.
- Drive `skills/slack-response-triage/SKILL.md` is unchanged from starting state.
- Drive `Proposals/Submitted/`, `Approved/`, `Rejected/` are empty or contain only Step 4 and Step 8 Submitted folders if the maintainer chose to leave them.
- Cowork shows `test-plugin` installed with `test-plugin:morning-briefing`, `test-plugin:slack-response-triage`, and `test-plugin:schedule-summary` visible.
- `Use schedule-summary` (with no overriding local skill) returns the partial-accepted canonical marker.
- No `.skill` artifact, no **Save skill** card, no `test-plugin--<skill-id>` per-skill id, no `aiws-generated-plugin` identity has appeared at any step.
- No marketplace, materialize, export, bridge, or draft language has appeared in any user-visible report.

## Anti-Pattern Guards (Consolidated)

These conditions are FAIL at any step where they appear.

The Save skill / Save plugin discriminator: **Save skill** is the correct surface only when installing a single user skill from a `.skill` artifact (e.g., Step 3 — local user skill registration). **Save plugin** is the correct surface when installing a multi-skill plugin from a `.plugin` artifact (Steps 2 and 5 — Test Plugin install and refresh). The question is always "what's the source artifact"; never "is the button called Save skill or Save plugin".

- A `.skill` artifact or **Save skill** card is presented when the source is `Test Plugin` (a multi-skill Drive library) → FAIL or NEEDS RETRY. Do not click. Repackage as `.plugin` with a **Save plugin** card. core-aiws 0.4.21 commit `5bd2147` enforces this; if it appears, the guard has regressed.
- A `.plugin` artifact or **Save plugin** card is presented when the source is a single SKILL.md being registered as a local user skill (Step 3) → FAIL. Repackage as `.skill` and present **Save skill** instead.
- Errors like `Zip must contain exactly one top-level folder` or `Zip must contain exactly one SKILL.md file` appearing on a `.plugin` install for Test Plugin → FAIL (host routed the multi-skill artifact to the single-skill installer; same root cause as the Save skill / Test Plugin mismatch above).
- Plugin id reported as `test-plugin--<skill-id>` → FAIL.
- Plugin identity reported as `aiws-generated-plugin` → FAIL.
- Refresh/install report references AIWS marketplace, `drive_workflow`, `export_cowork_bridge`, materialize, export, or draft packages → FAIL.
- Refresh report says a `plugins/` folder is required → FAIL.
- An artifact preflight failure (`Plugin validation failed`) without the report including generated archive entries, manifest JSON, contract JSON, packaged skill frontmatter, and exact Cowork error text → FAIL.

## Prompt Style

Use natural user prompts. The AIWS skills are designed to route on these.

Good prompts:

```text
Install Test Plugin from this Drive folder: <url>
Refresh Test Plugin
Validate the Test Plugin Drive library and include installed plugin status
Propose this schedule-summary change for Test Plugin: <plain-language change>
Use schedule-summary
```

Avoid:

- `Call aiws...` or any tool-call-shaped prompt.
- Raw JSON tool arguments.
- Mentions of marketplace, materialize, draft, export, or bridge in the normal user path.
- The shorter prompt `Check Test Plugin` for validation — in Cowork it can route to a generic installed-plugin summary instead of the Drive validation skill. Use the full validate prompt above.

## Notes On Resolution

- AIWS only enters when the user explicitly asks to install, refresh, validate, or propose. Authoring and using a local skill never invoke AIWS.
- Maintainer review uses local Markdown diff (`code --diff` or Meld). Google Docs compare is not part of Phase 1.
- Approved/Rejected folders are optional recordkeeping. This manual instructs the maintainer to leave them empty; testers may add them for audit if desired without changing the pass criteria.
- The local Cowork user-skill location is host-defined. The manual deliberately does not pin a filesystem path because that path can vary by host.
- **Save plugin** and **Save skill** clicks are UI-only — the assistant can produce and present the artifact via `mcp__cowork__present_files`, but the click must come from the user. The assistant cannot complete the install/save itself; it can only verify the post-click state from disk after the user confirms.
- **Role boundaries**: User (proposer), Maintainer (canonical owner), and the running Cowork host are three distinct actors even when the same human is performing all three. The manual gates Step 4.3 and Step 9 on an explicit maintainer signal so the assistant doesn't roll forward through a propose-then-accept on its own initiative.
- **Pushing repo changes from inside a Cowork session**: standard `git push` from the sandbox shell fails (no credentials). Use `mcp__Control_your_Mac__osascript` to invoke `git push` on the macOS host, where the user's `gh auth git-credential` + `osxkeychain` chain resolves the GitHub token. Author commits as `athanasiosbot <athanasiosbot@users.noreply.github.com>` via `git -c user.name=... -c user.email=...` per the existing convention.

## Known Upstream Skill Issues

Issues found during demo runs that are upstream skill bugs, not testing manual gaps. Logged here for the next maintainer of the AIWS plugin skills.

- `aiws-install-drive-skill-library` SKILL.md (observed in core-aiws ≤ 0.4.21) hard-codes a preflight expectation that `skills/meeting-followup/SKILL.md` exists in the demo library. With the current starting state (`morning-briefing` and `slack-response-triage` only), this is stale. The install still succeeded, but the instruction text is wrong and confuses regression testing. Fix: derive expected skill ids from the actual Drive contents instead of hard-coding the demo library.
- `aiws-propose-skill-update` SKILL.md instructs the maintainer to update `contracts/test-plugin.contract.json` on accept. That file is auto-generated by the install/refresh artifact builder from the Drive `skills/` contents; the maintainer must not edit it on Drive. Fix: remove the contract-edit instruction from the maintainer-accept guidance.
- `aiws-refresh-skill-library` SKILL.md does not include the same anti-marketplace guard that `aiws-install-drive-skill-library` does. When run against a Drive library that was never registered as an AIWS marketplace, the refresh skill falls back to AIWS-internal indexing, sees no skills, and reports `NEEDS MANUAL ACTION` even when the host has direct Drive access and the install/validate flows work fine on the same folder. Fix: mirror the install skill's guidance — explicitly read Drive via the host's Google Drive integration and treat empty AIWS marketplace indexing as expected, not as a failure signal.

### SOP: AIWS skills must not hard-code skill names or skill library names

**Standard**. Every AIWS Drive-library skill (`aiws-install-drive-skill-library`, `aiws-refresh-skill-library`, `aiws-validate-skill-library`, `aiws-check-skill-library`, `aiws-update-skill-library`, `aiws-propose-skill-update`) must treat the library display name, library id, plugin id, and skill ids as runtime inputs. Concretely:

- Behavior, preflight checks, output templates, and anti-pattern checks must derive expected skill ids from the actual Drive contents at execution time, never from a hard-coded list.
- Library/plugin id and display name must come from `aiws.library.json` or the Drive root folder name, not from a hard-coded value.
- Example prompts and example file paths in skill descriptions are allowed to use a concrete library name as illustration, but must clearly mark it as an example ("for example, `Test Plugin` …") and the surrounding rules must still hold for any library name the user supplies.

**Audit findings** (against current installed core-aiws). Only `aiws-improve` is clean; every other Drive-library skill violates the SOP somewhere.

Behavior / logic / template violations to fix:

| Skill | Line | Violation | Fix |
|---|---|---|---|
| `aiws-install-drive-skill-library` | 53 | "For Test Plugin, use plugin-id test-plugin" | Derive plugin id from Drive root folder name (slugified) or `aiws.library.json`. |
| `aiws-install-drive-skill-library` | 58 | Preflight: "contracts/test-plugin.contract.json exists … for Test Plugin" | Preflight: `contracts/<plugin-id>.contract.json` derived from runtime plugin id. |
| `aiws-install-drive-skill-library` | 59 | Preflight: "skills/morning-briefing/SKILL.md and skills/meeting-followup/SKILL.md exist" | Preflight: every `skills/<skill-id>/SKILL.md` enumerated from the actual Drive contents at packaging time. |
| `aiws-install-drive-skill-library` | 60 | Wrapper check: "no entry starts with test-plugin/, Test Plugin/" | Wrapper check: no entry starts with `<plugin-id>/` or `<library-display-name>/`. |
| `aiws-install-drive-skill-library` | 61 | "plugin.json.name equals test-plugin" | "plugin.json.name equals the runtime plugin id". |
| `aiws-refresh-skill-library` | 44–48 | "For Test Plugin, any rebuilt artifact identity is plugin id: test-plugin, plugin display name: Test Plugin" | Preserve whatever plugin id and display name the installed `.claude-plugin/plugin.json` already holds. |
| `aiws-refresh-skill-library` | 51 | Anti-pattern check: "test-plugin--meeting-followup" | Anti-pattern check: `<plugin-id>--<skill-id>` (any per-skill plugin id). |
| `aiws-refresh-skill-library` | 62 | "preserving the plugin id test-plugin for Test Plugin" | "preserving the runtime plugin id for the library being refreshed". |
| `aiws-check-skill-library` | 39 | Output template: `test-plugin: present|missing|not verified` | Output template: `<plugin-id>: present|missing|not verified`. |
| `aiws-validate-skill-library` | 168 | Output template: `test-plugin: present|not verified|missing` | Same as above. |

Example-prompt violations to clean up (lower severity; mark explicitly as examples):

- `aiws-check-skill-library` lines 13–18, `aiws-validate-skill-library` lines 13–33, `aiws-refresh-skill-library` lines 13–20 and 55, `aiws-update-skill-library` lines 23–25, `aiws-propose-skill-update` lines 28–30 and 53 — all use "Test Plugin" / "meeting-followup" / "morning-briefing" in example prompts. Rewrite as `<library-display-name>` placeholders, or prefix with "Example (for a Drive library named `Test Plugin`):".

**Why the SOP matters**. The Step 2 install regression we hit during this demo was caused by `aiws-install-drive-skill-library` line 59 expecting `meeting-followup` to exist — a hard-coded skill name from an earlier baseline. When the demo baseline changed, the skill's preflight instruction went stale. Every hard-coded name above is the same class of latent bug.

**Implementation**. The fix happens in the AIWS source repo (Sasha owns this), not by patching the installed plugin extract — the next AIWS plugin release would overwrite local edits.

## Known Cowork Host Issues

Issues found during demo runs that are upstream Cowork behavior, not AIWS or testing manual gaps. Logged here for the next maintainer of Cowork's local-skill registration path.

- Cowork's default routing for the prompt `Create a local Cowork user skill named <name> with the following SKILL.md body: <body>` is unreliable. Observed failure modes during demo runs:
  - Directly writing SKILL.md into `/var/folders/.../claude-hostloop-plugins/<hash>/skills/<name>/` — a temp symlink target. Survives the current session but gets wiped on Cowork restart.
  - Directly writing SKILL.md into the durable plugin path at `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<plugin-uuid>/<install-uuid>/skills/<name>/`. Survives a single restart but is then wiped by the next manifest-driven rebuild because no `manifest.json` row references it.
  - Invoking `Use skill-creator` and walking the full iterative draft/eval loop — overkill when the SKILL.md body is already in hand, and time-consuming enough that the tester gives up before reaching the registration step.

  The correct mechanism is: write the SKILL.md to a working directory, run `package_skill.py` from the `skill-creator` plugin to produce a `<name>.skill` zip, and present it via `mcp__cowork__present_files`. The resulting Save skill card, when clicked, writes both the `manifest.json` entry (with a generated `skillId` and `creatorType: "user"`) and the SKILL.md to the plugin path. Only the manifest-backed registration survives restart.

  Fix: route the natural-language "create a local user skill" prompt to the lightweight package + present flow by default. Either ship a dedicated thin skill for this purpose, or update Cowork's default behavior to prefer `package_skill.py` + `mcp__cowork__present_files` over direct file writes and over the full skill-creator loop.

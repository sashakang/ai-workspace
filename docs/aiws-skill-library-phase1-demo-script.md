# AIWS Skill Library Phase 1 Demo Script

## Summary

Audience-facing walkthrough of the Phase 1 Drive Skill Library user path for `Test Plugin`. The Drive folder is the source of truth. Cowork installs and runs skills from a plugin-like container generated from the Drive folder. AIWS supplies the lifecycle skills (install, propose, refresh, validate) and the maintainer review handoff.

Use the exact prompts below. They are written in natural user language.

For deeper validation, anti-pattern guards, role boundaries, and failure-mode recovery, see the longer **AIWS Skill Library Phase 1 Testing Manual** in the same folder.

Demo Drive folder:

```text
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Starting state on Drive:

```text
Test Plugin/
  aiws.library.json
  skills/
    morning-briefing/SKILL.md
    slack-response-triage/SKILL.md
  Proposals/
    Submitted/   (empty)
    Approved/    (empty)
    Rejected/    (empty)
```

Demo skill being built: `schedule-summary` (added during the demo as a new third skill).

## 1. Install Test Plugin

Prompt:

```text
Install Test Plugin from this Drive folder:
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Expected:

- Cowork packages one plugin artifact named `Test Plugin`, plugin id `test-plugin`, version `0.1.0`.
- One **Save plugin** card for a `.plugin` artifact (NOT a `.skill` artifact, NOT a Save skill card).
- After clicking Save plugin, these skills are visible:
  - `test-plugin:morning-briefing`
  - `test-plugin:slack-response-triage`

## 2. Author A New Local Skill (v.1)

Prompt (with the SKILL.md body inline):

```text
Create a local Cowork user skill named `schedule-summary` with the following SKILL.md body:

---
name: schedule-summary
description: Summarize my schedule for a given period (today, tomorrow, yesterday, this week, next week, or a specific date range).
---

# Schedule Summary

Use this skill when the user asks for a recap of their calendar over a specific period.

Always begin the output with this exact debug line:

> schedule-summary v1: running

Resolve the period from the user's request. If ambiguous, ask one short clarifying question.

If calendar tools are available, fetch events in the requested period. If unavailable, ask the user to paste their calendar entries.

Produce a compact chat-markdown summary with sections: Period, Events, Focus blocks, Notable.

Keep the summary compact. Do not invent events, attendees, or details.
```

Expected:

- Cowork builds a `schedule-summary.skill` artifact and presents one **Save skill** card. (Save skill is correct here — single-skill registration, not a plugin install.)
- After clicking Save skill, `anthropic-skills:schedule-summary` is registered locally with `creatorType: "user"`.

## 3. Use The Local Skill

Prompt:

```text
Give me a summary of today's schedule
```

Expected:

- First chat line: `> schedule-summary v1: running`
- Compact Markdown with Period / Events / Focus blocks / Notable sections.
- No HTML file — pure chat output.

## 4. Propose The Skill To The Team

Prompt:

```text
Propose this new skill for Test Plugin: schedule-summary. Use my local schedule-summary SKILL.md as the proposed content.
```

Expected:

- A folder lands on Drive at `Proposals/Submitted/schedule-summary/proposal-YYYY-MM-DD-add-schedule-summary/` containing `SKILL.md` + `aiws.proposal.json`.
- Drive `skills/schedule-summary/` does NOT exist yet (no canonical until the maintainer accepts).
- Output includes a local Markdown diff command for VS Code/VSCodium or Meld.

## 5. Maintainer Accepts

Maintainer action (this is a deliberate human step — the assistant does not auto-execute it):

- Open the proposed SKILL.md and read it standalone (no canonical to diff against — it's brand new).
- Create `skills/schedule-summary/SKILL.md` on Drive with the accepted content.
- Delete the entire `Proposals/Submitted/schedule-summary/proposal-…/` folder. `Proposals/Approved/` and `Proposals/Rejected/` stay empty.

Signal in chat: `accept as maintainer` (or equivalent) when ready.

## 6. Refresh Test Plugin

Prompt:

```text
Refresh Test Plugin
```

Expected:

- AIWS reads Drive canonical, sees 3 skills now (was 2), rebuilds the `.plugin` artifact with a minor version bump (e.g., `v0.1.0 → v0.2.0`), preflight passes.
- One **Save plugin** card.
- After clicking Save plugin, `test-plugin:schedule-summary` is visible alongside `test-plugin:morning-briefing` and `test-plugin:slack-response-triage`.

Cleanup after refresh (per testing manual policy): if the local `anthropic-skills:schedule-summary` body is byte-identical to the last submitted proposal, remove it via Cowork's skill panel so the plugin canonical becomes the single source of truth.

## 7. Iterate: Update To v.2 With HTML Output

Prompt (with the v.2 SKILL.md body inline):

```text
Create a local Cowork user skill named `schedule-summary` with the following SKILL.md body:

---
name: schedule-summary
description: Summarize my schedule for a given period. Outputs a self-contained HTML report saved to outputs and presented via a computer:// link.
---

# Schedule Summary

Use this skill when the user asks for a recap of their calendar over a specific period.

Always begin the output with this exact debug line:

> schedule-summary v2: running

Resolve the period from the user's request. If ambiguous, ask one short clarifying question.

If calendar tools are available, fetch events. If unavailable, ask the user to paste their calendar entries.

Generate a self-contained HTML file saved as `schedule_summary_{period-slug}_{YYYYMMDD}.html` and present it with a `computer://` link. The HTML has Period, Events, Focus blocks, Notable sections as styled cards.

Do not invent events. 24h time, local timezone.
```

Expected:

- Cowork presents a fresh **Save skill** card with the v.2 body. After save, the local override is at v.2; it takes precedence over the v.1 plugin copy.

## 8. Use The Updated Skill

Prompt:

```text
Give me a summary of tomorrow's schedule
```

Expected:

- First chat line: `> schedule-summary v2: running`
- The chat shows just the marker + a `computer://` link to a `schedule_summary_*_YYYYMMDD.html` file in `outputs/`.
- The HTML report has Period / Events / Focus blocks / Notable as styled cards.

## 9. Propose The v.2 Changes And Accept

Prompt:

```text
Propose this schedule-summary change for Test Plugin: use my current local schedule-summary SKILL.md as the proposed content.
```

Expected:

- New folder at `Proposals/Submitted/schedule-summary/proposal-YYYY-MM-DD-html-output/` with v.2 `SKILL.md` + `aiws.proposal.json`.
- Drive canonical is still v.1; output includes a `code --diff` command between canonical and proposal.

Then maintainer signal (`accept as maintainer`) → overwrite canonical with the v.2 body, delete the proposal folder. `Approved/Rejected` stay empty.

## 10. Final Refresh And Verify

Prompt:

```text
Refresh Test Plugin
```

Expected:

- AIWS sees content-only change in `schedule-summary`, rebuilds with a patch bump (e.g., `v0.2.0 → v0.2.1`), one **Save plugin** card.
- After save, the installed `test-plugin:schedule-summary` reflects the v.2 canonical.

Then remove the local override via Cowork's skill panel (it's still byte-identical to the last proposal → safe to remove) and run:

```text
Use schedule-summary
```

Expected first chat line: `> schedule-summary v2: running` — now sourced from the plugin, not from a local override.

## Pass Criteria

The demo passes when:

- Drive `skills/` contains `morning-briefing`, `slack-response-triage`, `schedule-summary` (the last at the v.2 body).
- Drive `Proposals/{Submitted,Approved,Rejected}/` are empty.
- Cowork shows `test-plugin` installed at the latest patch version with all three skills visible.
- `Use schedule-summary` returns the v.2 marker from the plugin (no local override).
- At no step did a `.skill` artifact or **Save skill** card appear for the `test-plugin` install, and at no step did a `.plugin` artifact or **Save plugin** card appear for the local user-skill registration. The artifact type discriminator was respected throughout.
- No marketplace, materialize, export, draft, bridge, ZIP upload, or RPM path appeared in any user-visible report.

## Where To Go Next

For step-by-step assertions, recovery from degenerate failure modes (e.g., refresh falling back to AIWS-internal marketplace indexing), role boundaries, anti-pattern guards, and the upstream-issue audit, see the full **AIWS Skill Library Phase 1 Testing Manual**.

# core-aiws v0.5.1 — Phase 2 priority-1 smoke-test

**Release**: `cc8037b` on `sashakang/ai-workspace` master, tagged `core-aiws-v0.5.1`.
**Targets**: three fixes that ship in v0.5.1.
**Scope**: minimal regression check. Does not re-run the full Phase 1 testing manual.

## Pre-conditions

- Fresh Cowork session (so v0.5.1 SKILL.md text is loaded, not v0.5.0 cached).
- `core-aiws` plugin reinstalled at v0.5.1.
  - Verify: `cat ~/Library/Application\ Support/Claude/local-agent-mode-sessions/cowork_plugins/cache/<...>/core-aiws/.claude-plugin/plugin.json` — `version` should be `0.5.1`.
- Test Plugin Drive folder reachable: <https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L>
- Drive starting state per the testing manual: `skills/morning-briefing/`, `skills/slack-response-triage/`, empty `Proposals/Submitted|Approved|Rejected/`. Run the reset prompt if needed.

## Test 1 — Refresh anti-marketplace guard (fixes the NEEDS MANUAL ACTION misroute)

**Setup**: `test-plugin` already installed in Cowork from Test Plugin Drive library (per testing manual Step 2 — if not installed, run Step 2 first). Drive state unchanged since install.

**Prompt**:

```text
Refresh Test Plugin
```

**Pass**:

- Report header is `AIWS Skill Library Refresh: PASS` (Drive matches installed, no rebuild) OR `READY FOR SAVE` (rebuild needed).
- `Canonical SKILL.md verified: PASS`
- `Library validation: PASS`
- Report does NOT mention marketplace, materialize, `<plugin-id>` marketplace empty, or "no skills discoverable".
- Report ends with `## Mandatory Self-Improvement` section (or a self-improvement protocol run), not the old inline boilerplate.

**Fail signals** (regression — v0.5.0 behavior leaked through):

- `NEEDS MANUAL ACTION` with `Canonical SKILL.md verified: FAIL` and language about marketplace fallback.
- Report says "no skills discoverable" against a library that visibly has skills on Drive.

If failing, capture the full report and re-run with the directive prompt from testing manual line 330–332.

## Test 2 — Install Source-Shape Validation (new fail-fast guard)

This requires a Drive folder shaped like a packaged plugin tree, NOT a Skill Library. Two options:

**Option A — quick check (no test fixture)**: confirm the normal install still works.

```text
Install Test Plugin from this Drive folder:
https://drive.google.com/drive/folders/1BiEjSTKeD0hyUyHWdLhvP0cp3RX3uo7L
```

Pass: normal install flow per testing manual Step 2. No regression.

**Option B — full check (needs a test fixture)**: create a sibling Drive folder, e.g. `Test Plugin Wrong Shape/`, containing a `.claude-plugin/` subfolder (any content). Then:

```text
Install Test Plugin Wrong Shape from this Drive folder:
<url-to-the-wrong-shape-folder>
```

**Pass (Option B)**:

- Report: `AIWS Drive Skill Library Install: FAIL`.
- Failure message names `.claude-plugin/` (or `contracts/`) as the disqualifier.
- Suggests the Cowork plugin path or the matching Drive Skill Library root as the correct action.
- No `.plugin` artifact built. No Save plugin card.

**Fail signal** (regression): assistant silently packages only the `skills/` subset, presents a Save plugin card. That's the pre-v0.5.1 behavior.

Skip Option B if creating the fixture is more work than it's worth — Option A covers the no-regression case.

## Test 3 — Self-improvement-pointer refactor (cosmetic)

Trivially observable in any service-skill report from Tests 1–2:

**Pass**:

- Reports end with a `## Mandatory Self-Improvement` section that points to `core-aiws/protocols/self-improvement.md`, OR with an actual self-improvement protocol output, depending on host.
- Reports do NOT contain the old multi-line "End every X procedure with a short self-improvement checkpoint…" inline boilerplate.

## What to do with results

- All pass → close Phase 2 priority-1. Confirm `docs/aiws-skill-library-phase1-testing-manual.md` "Known Upstream Skill Issues" retirement notes match observed behavior.
- Test 1 fails → refresh skill still misroutes. Open a Phase 2 follow-up: the SKILL.md text was insufficient; needs stronger host-routing constraint or a runtime check.
- Test 2 (Option B) fails → the install skill's preflight needs to be promoted from prose to a code-side guard in the AIWS packager.
- Test 3 fails → something is reading a cached older skill text; re-verify the v0.5.1 install picked up the new SKILL.md files.

## Capture format (optional)

Append observed behavior to `docs/aiws-skill-library-phase1-testing-manual.md` under a new "v0.5.1 smoke-test results" appendix, or to a fresh `docs/core-aiws-v0.5.1-smoke-test-results.md`. Per `protocols/session-log.md` shape if you want a structured log.

# Session Log Protocol

Deferred capability: this protocol defines the shape of a future centralized `core-aiws` session log. It is not required in v1.

Lightweight structured logging for non-lightweight work executed under `core-aiws`.

## Location

`${CLAUDE_PLUGIN_DATA}/session-logs/sop_session_<YYYYMMDD_HHMMSS>.log`

Example:

`${CLAUDE_PLUGIN_DATA}/session-logs/sop_session_20260326_101530.log`

## Purpose

Session logs are evidence for:

- SOP phase transitions
- gate outcomes
- reviewer votes
- unresolved questions
- self-improvement input

They are not a replacement for Claude session JSONL history.

## Format

```text
=== SESSION START: <ISO timestamp> ===
Skill: <skill name or "ad-hoc">
Task: <brief description>
Complexity: <lightweight|standard|complex|maximum>

=== PHASE TRANSITIONS ===
[HH:MM:SS] PHASE 1: INTAKE — <summary>
[HH:MM:SS] PHASE 2: PLANNING — <summary>
[HH:MM:SS]   GATE 1: <APPROVED | REVISED x N> — <key feedback>
[HH:MM:SS] PHASE 3: USER APPROVAL — <approved/rejected>
[HH:MM:SS] PHASE 4: EXECUTION — <specialist summary>
[HH:MM:SS] PHASE 5: VALIDATION — <summary>
[HH:MM:SS]   GATE 2: <APPROVED | REVISED x N> — <key feedback>
[HH:MM:SS] PHASE 6: TESTING — <summary>
[HH:MM:SS] PHASE 7: DOCUMENTATION — <summary>
[HH:MM:SS] PHASE 8: DELIVERY — <summary>
[HH:MM:SS] PHASE 9: SELF-IMPROVEMENT — <summary>

=== AGENT INVOCATIONS ===
[HH:MM:SS] SPAWN: <role> — <purpose>
[HH:MM:SS] RESULT: <role> — <APPROVE|REQUEST_CHANGES|summary>

=== ISSUE LOG ===
[ISSUE #N]
- Phase: <phase>
- Type: <category>
- What: <brief description>
- Root cause: <brief cause>
- Suggested fix: <brief improvement>

=== SESSION COMPLETE: <ISO timestamp> ===
Duration: <MM:SS>
Outcome: <success|partial|failed|escalated>
```

## Rules

- create the file at session start
- write phase transitions as they happen
- summarize rather than dumping long raw outputs
- log issues when they occur, not only at the end
- close the file before ending the session

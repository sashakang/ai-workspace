---
description: Analyze accumulated user signals and propose improvements to CLAUDE.md, agents, skills, and hooks
---

# Batch Self-Improvement Analysis

This is the shared `/aiws-improve` surface owned by `core-aiws`.

Gathers accumulated signals from multiple sources, synthesizes patterns, then runs the unified [Self-Improvement Protocol](../../protocols/self-improvement.md) in batch mode.

**Scope**: This skill is responsible only for evidence gathering and synthesis (Phases 1-3). All decision rules for prompt, skill, protocol, and workflow improvement live in the protocol — do not duplicate them here. Shared-memory refresh is not owned by this skill.

---

## Phase 1: Gather Batch Evidence

Read all available sources (skip any that don't exist):

1. **Observations**: `${CLAUDE_PLUGIN_DATA}/improve/observations.jsonl` — find the most recent `improve_run` entry as cutoff, filter to newer entries
2. **Daily logs**: Today's + yesterday's from `${CLAUDE_PLUGIN_DATA}/project-memory/current/YYYY-MM-DD.md`
3. **Claude Code native session history** when the host environment makes it available
4. **Installed plugin contracts**: `${CLAUDE_PLUGIN_DATA}/registry/plugins/*.json`
5. **Current conversation context**

Present evidence summary:

```
## Evidence Summary (since last /aiws-improve run)

**Observations** (from hook signals):
| Signal Type   | Count |
|---------------|-------|
| correction    | N     |
| frustration   | N     |
| give_up       | N     |
| positive      | N     |

**Other sources**: N daily log entries, N session histories reviewed
- Unique sessions: N
- Unique projects: N
- Date range: YYYY-MM-DD to YYYY-MM-DD
```

If no evidence exists from any source, report "No new signals to analyze" and stop.

---

## Phase 2: Transcript Deep-Dive

For each **high-severity** observation (correction, frustration, give_up):

1. Read the transcript at the observation's `transcript` path
2. Find context: what was Claude doing? What did the user ask? Where did it go wrong?
3. Identify root cause: missing rule, bad agent prompt, wrong default, process friction, tool discovery, architecture insight

Present findings:
```
### Finding: <obs_id> (<type>, <date>)
**User said**: "<message excerpt>"
**Context**: <what Claude was doing>
**Root cause**: <category> - <specific explanation>
**Target**: <file path> : <section/line>
```

---

## Phase 3: Pattern Synthesis

Group findings by root cause across sessions:
- Same correction across multiple sessions → missing rule
- Same frustration pattern → process issue
- Positive patterns → reinforce what works

Present:
```
### Pattern: <descriptive name>
- Sessions: <list of session dates>
- Root cause: <category>
- Evidence: "<quote 1>", "<quote 2>"
- Target file: <path>
- Confidence: HIGH/MEDIUM (see protocol rules)
```

---

## Phase 4: Run Self-Improvement Protocol

Follow the [Self-Improvement Protocol](../../protocols/self-improvement.md) in batch mode with the synthesized findings from Phase 3 as input. Start from Step 3 (Categorize and Decide) — Steps 1-2 are skipped in batch mode. Use the synthesized patterns from Phase 3 as input to Step 3's categorization; formal Learning Entry Format is applied in Step 4.2.

Do not treat `/aiws-improve` as the routine shared-memory consolidation trigger. Shared-memory candidate capture happens during end-of-task auto-capture, and shared-memory refresh is handled automatically by the host-side shared-memory bridge.

---

## Phase 5: Update Observation Log

After protocol completion:

1. Append an `improve_run` marker to `${CLAUDE_PLUGIN_DATA}/improve/observations.jsonl`:
   ```json
   {"id":"imp_<8-char-hex>","ts":"<ISO timestamp>","type":"improve_run","severity":"info","message":"Processed observations up to <latest_obs_id>"}
   ```

2. For each applied change, append a verification entry:
   ```json
   {"id":"verify_<8-char-hex>","ts":"<ISO timestamp>","type":"improvement_applied","severity":"info","message":"Applied: <brief description>. Monitor for recurrence."}
   ```

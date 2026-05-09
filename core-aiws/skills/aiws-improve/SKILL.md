---
name: aiws-improve
description: Analyze accumulated user signals and propose improvements to workspace instructions, agents, skills, and hooks
---

# Batch Self-Improvement Analysis

This is the shared `aiws-improve` capability owned by `core-aiws`.

Gathers accumulated signals from multiple sources, synthesizes patterns, then runs the unified [Self-Improvement Protocol](../../protocols/self-improvement.md) in batch mode.

**Scope**: This skill is responsible only for evidence gathering and synthesis (Phases 1-3). All decision rules for prompt, skill, protocol, and workflow improvement live in the protocol — do not duplicate them here. Shared-memory refresh is not owned by this skill.

`aiws-improve` is the canonical AIWS capability identity. Hosts may expose it as a slash command, a skill, an MCP prompt, or another native UI affordance. Do not assume `/aiws-improve` is available unless the current host advertises slash-command exposure.

---

## Phase 1: Gather Batch Evidence

Resolve host evidence surfaces first. Prefer the AIWS host evidence contract, for example `aiws.host.surfaces` when exposed by the local MCP runtime. Read all available logical surfaces and skip any that the current host does not provide:

1. **Observations**: host-provided structured correction, frustration, give-up, positive, and improvement markers. Find the most recent `improve_run` marker as cutoff when markers exist.
2. **Project notes or daily logs**: host-provided project memory or session notes for today and yesterday when available.
3. **Session history and transcripts**: host-provided current or recent interaction history when available.
4. **Installed contracts and skill catalog**: host-provided plugin contracts, skill manifests, or AIWS catalog resources.
5. **Current conversation context**.

Present evidence summary:

```
## Evidence Summary (since last aiws-improve run)

**Observations** (from hook signals):
| Signal Type   | Count |
|---------------|-------|
| correction    | N     |
| frustration   | N     |
| give_up       | N     |
| positive      | N     |

**Other sources**: N project notes, N session histories reviewed, N installed contracts or manifests reviewed
- Unique sessions: N
- Unique projects: N
- Date range: YYYY-MM-DD to YYYY-MM-DD
```

If no evidence exists from any source, report "No new signals to analyze" and stop.

---

## Phase 2: Transcript Deep-Dive

For each **high-severity** observation (correction, frustration, give_up):

1. Resolve the related transcript or session context through the host-provided evidence surface when available. If the host provides only a summary, or no transcript surface at all, continue from the observation summary and current context, and mark the missing transcript as an evidence gap.
2. Find context: what was the host agent doing? What did the user ask? Where did it go wrong?
3. Identify root cause: missing rule, bad agent prompt, wrong default, process friction, tool discovery, architecture insight

Present findings:
```
### Finding: <obs_id> (<type>, <date>)
**User said**: "<message excerpt>"
**Context**: <what the host agent was doing>
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

Do not treat `aiws-improve` as the routine shared-memory consolidation trigger. Shared-memory candidate capture happens during end-of-task auto-capture, and shared-memory refresh is handled automatically by the host-side shared-memory bridge.

---

## Phase 5: Update Observation Log

After protocol completion:

1. Append an `improve_run` marker to the host-provided writable observation or improvement-marker surface, if one exists:
   ```json
   {"id":"imp_<8-char-hex>","ts":"<ISO timestamp>","type":"improve_run","severity":"info","message":"Processed observations up to <latest_obs_id>"}
   ```

2. For each applied change, append a verification entry to the same host-provided marker surface, if one exists:
   ```json
   {"id":"verify_<8-char-hex>","ts":"<ISO timestamp>","type":"improvement_applied","severity":"info","message":"Applied: <brief description>. Monitor for recurrence."}
   ```

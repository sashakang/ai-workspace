# Standard Operating Procedure (SOP)

This is the canonical ai-workspace SOP for `core-aiws`.

This is the default process. Skills may follow it as-is, override specific phases, or replace it with their own workflow entirely. **SOP defines the default phase structure and gate requirements; skills define the concrete implementation.** When a skill defines its own workflow, the skill's SKILL.md is authoritative.

---

## Complexity Classification

Before entering the SOP, classify the task. This determines which phases to run.

| Signal | Classification | Path |
|--------|---------------|------|
| Config value, typo fix, simple reply, quick lookup | **Lightweight** | Fast Path: Phase 4 + Phase 8. No gates. |
| New feature, multi-file change, analysis, debugging | **Standard** | Full SOP (all 8 phases) |
| Architecture change, multi-service, system design | **Complex** | Full SOP + signal high complexity to all agents |
| Novel algorithm, cross-cutting architectural decision, performance-critical | **Maximum** | Full SOP + maximum reasoning depth for all agents |

**Canonical complexity enum**: `lightweight | standard | complex | maximum` (use these exact values everywhere: session logs, delegation signals, complexity fields).

**Lightweight conditions** -- ALL must be true:
- Change touches <=1 file OR is a conversational response
- No new logic, no new functions, no new queries
- Risk of error is negligible
- No downstream consumers depend on correctness

If ANY condition is false, use Standard or higher. When in doubt, use Standard.

---

## Phase 1: INTAKE

**[SOP] Entering Phase 1: Intake**

**Owner**: Representative (main agent)

Parse the request. Extract:

- **WHAT** -- artifact, answer, fix, or analysis being requested
- **WHY** -- what decision or action this serves
- **WHO** -- consumer of the output (user, stakeholder, system)
- **URGENCY** -- blocking a decision? Routine? Exploratory?
- **TYPE** -- code | data-analysis | data-extraction | research | documentation | infrastructure | prompt-protocol | other

If the request is clear enough to proceed, move to Phase 2. If genuinely ambiguous, ask one focused clarifying question. Do not over-clarify what is already obvious.

**Exit**: Objective, constraints, and scope are clear. Record framing in the active evidence surface if one is in use.

---

## Phase 2: PLANNING

**[SOP] Entering Phase 2: Planning**

**Owner**: Representative delegates to specialist planners

Design the approach before executing. This prevents wasted work.

### 2.1 Research (Plan Mode)

**Enter plan mode at the start of research.** Call `EnterPlanMode` so the agent operates in read-only mode. The user quick-approves (this is a protocol checkpoint, not a real approval). Conduct all research using read-only tools (Glob, Grep, Read, Task with `readonly: true`).

Spawn research agents to understand the problem space:

| Task Type | Research Agent | What to Research |
|-----------|---------------|-----------------|
| Code | `Explore` | Relevant files, existing patterns, dependencies |
| Data analysis | `Explore` + `data-analyst` | Tables, coverage, metric definitions, prior work |
| Data extraction | `Explore` | Schema, data quality, available tables |
| Infrastructure | `Explore` + `devops-engineer` | Current state, namespace status, configs |
| Documentation | `Explore` | Existing docs, code to document |
| Prompt/Protocol | `Explore` + `prompt-engineer` | Existing protocols, structure, edge cases |

### 2.2 Plan Formulation (Plan Mode)

While still in plan mode, formulate the plan based on research:

- **Approach** -- what will be done, step by step
- **Specialists needed** -- which agents will execute
- **Success criteria** -- how we know it worked
- **Risks** -- what could go wrong
- **Estimated scope** -- files to modify, queries to run, artifacts to produce

Write the plan to the plan file.

### 2.3 Exit Plan Mode

Call `ExitPlanMode`. The plan file should be labeled: **"Draft plan — proceeding to Gate 1 technical review."** The user quick-approves this exit (it is a protocol checkpoint, NOT the real user approval).

> **IMPORTANT**: `ExitPlanMode` during Phase 2 is a protocol checkpoint, NOT user approval. The real user approval happens in Phase 3.

### 2.4 Gate 1: Design Consensus (sub-agent only, no user approval needed)

**HARD GATE: Do NOT proceed to Phase 3 until Gate 1 passes.** Skills that define their own gate structure follow their skill workflow instead.

The Representative NEVER approves their own plan. Independent reviewers must validate.

Default reviewers by task type. Skills with custom gate reviewers override this table.

Spawn reviewers IN PARALLEL based on task type:

| Task Type | Gate 1 Reviewers | What They Validate |
|-----------|-----------------|-------------------|
| Code | `architecture-simplifier` + `code-simplifier` + `prompt-engineer`* | Simplest approach? Minimal changes? Existing patterns? Prompt quality? |
| Data analysis | `data-analyst` | Sound methodology? Right tables? Correct metrics? |
| Data extraction | `data-analyst` | Right data sources? Correct filters? Complete scope? |
| Infrastructure | `devops-engineer` | Correct approach? Safety checks? Rollback plan? |
| Documentation | `code-reviewer` | Accurate? Complete? Consistent? |
| Prompt/Protocol | `prompt-engineer` + `architecture-simplifier` | Clear? Enforceable? No contradictions? |

*`prompt-engineer` participates only when the change involves prompts, skills, or protocol files. Skips for pure code changes.

For this repository's protocol and skill changes, add `ai-engineer` to the Gate 1 review commission in addition to the default Prompt/Protocol reviewers.

For mixed tasks (e.g., code + prompt changes), include reviewers from all applicable task type rows.

**Consensus rules:**
- ALL reviewers must vote APPROVE to proceed
- Any REQUEST_CHANGES -> re-enter plan mode (`EnterPlanMode`), revise the plan, `ExitPlanMode`, and re-submit to Gate 1
- Maximum 3 iterations per gate
- After 3 failures -> escalate to user (see [Escalation Protocol](./escalation.md))

**Contradiction trigger**: Run contradiction resolution only when reviewer slots address the same frozen `element_id` in the current gate pass and either:
- their normalized `next_action` values cannot all be satisfied by one immediate disposition in the current gate pass without violating any slot's explicit verdict constraints
- they disagree on verdict, severity, or diagnosis in a way that produces no single immediate disposition that satisfies all involved slots

Compatible differences do not trigger contradiction resolution.

**Representative-side normalization**: `next_action` is a Representative-side normalization field unless a skill already emits it explicitly. Reviewers keep their existing verdict labels. The Representative derives `next_action` from each slot's verdict and rationale using a closed vocabulary:
- SOP gates: `accept | revise_plan | revise_output | escalate`
- `pass/revise/block` gates: `accept | revise_section | fix_foundation | escalate`
- `pass/flag/block` gates: `accept | disclose_caveat | fix_before_release | escalate`

`next_action` must represent the minimal viable immediate action path implied by that slot's position, not a broader rewrite.

**Contradiction record**: When contradiction resolution is required, the Representative creates one per-element record with:
- `element_id`
- `element_scope`
- `question`
- `conflicting_actions`
- `participating_slots`
- `conference_summary`
- `conference_result`
- `slot_verdicts_after_conference`
- `notes`

Use the canonical format `<artifact>::<section_or_step>::<issue_slug>` for `element_id`.

Derivation order:
1. `artifact`: the concrete file, skill, or deliverable under review
2. `section_or_step`: the smallest named section, gate step, or object where the contradiction exists
3. `issue_slug`: stable kebab-case label taken from the first recorded contradiction on that element in this gate iteration

Freeze the resulting `element_id` for the rest of that gate iteration. If a narrower sub-dispute appears during the conference, absorb it into the same `element_id`; do not create a nested conference.

**Required active slots**: Only the reviewer slots currently in contradiction on that `element_id` in the current gate pass, plus any fallback slot that formally replaces one of them. Uninvolved gate reviewers do not need refreshed verdicts.

**Contradiction-resolution wrapper**: Run one bounded conference wrapper per `element_id` per gate iteration.
- one conference round only
- only required active slots participate
- no nested wrappers
- no reopening the wrapper after fallback
- no new evidence scope beyond the recorded contradiction and supporting rationale already in the record
- mandatory close at the end of the round with exactly one of: `converged`, `strategically_unresolved`, `slot_unavailable`

The wrapper sits inside the current gate iteration and creates no extra retry or iteration budget by itself. Any later revision-and-resubmission still counts toward the existing gate budget.

**Conference result rules**:
- `converged`: every required active slot returns an updated explicit verdict and the Representative-normalized `next_action` values are all satisfiable by one immediate disposition in the current gate pass
- `strategically_unresolved`: every required active slot returns an updated explicit verdict but no single immediate disposition in the current gate pass can satisfy all normalized `next_action` values
- `slot_unavailable`: a required active slot fails to return an updated verdict after normal retry/fallback is exhausted

The Representative owns `element_id` assignment, `next_action` normalization, and final `conference_result`, but must follow these rules.

**Fake consensus guard**: Consensus means actual sub-agent outputs with explicit votes. The main agent reporting approval without spawning reviewers is fabricated consensus and a protocol violation.

**Cursor option**: Gate 1 reviewers (read-only reasoning) can be routed to Cursor CLI per the [Cursor Delegation Protocol](./cursor-delegation.md). Fallback to Claude sub-agents if Cursor fails.

**Exit**: Plan approved by Gate 1 consensus. Record the outcome in the active evidence surface if one is in use. Proceed to Phase 3 for user approval.

---

## Phase 3: USER APPROVAL

**[SOP] Entering Phase 3: User Approval**

**Owner**: Representative (main agent)

**Only after Gate 1 passes**, present the final Gate-1-approved plan to the user for review.

### 3.1 Plan Presentation

Present the plan including:
- The complete Gate-1-approved plan
- Key design decisions and trade-offs
- Estimated scope and risk

**End every user approval request with a gate status line** (last thing before the user decides):
```
[GATE 1: PASSED ✓] architecture-simplifier: APPROVE, code-simplifier: APPROVE
```
or if a gate was skipped (lightweight task):
```
[GATE 1: SKIPPED — lightweight task]
```

### 3.2 User Decision

- **User approves**: Proceed to Phase 4 (Execution)
- **User rejects or requests changes**: Loop back to Phase 2 — re-enter plan mode (`EnterPlanMode`), revise the plan based on user feedback, `ExitPlanMode`, re-run Gate 1, then return to Phase 3 for user approval again

**HARD GATE: Do NOT proceed to Phase 4 until the user explicitly approves the plan.** Skills that define their own gate structure follow their skill workflow instead.

**Exit**: User has approved the plan. Record the approval in the active evidence surface if one is in use. Proceed to Phase 4.

---

## Phase 4: EXECUTION

**[SOP] Entering Phase 4: Execution**

> **CRITICAL**: The Representative NEVER implements directly. All work is delegated to specialist agents. If you are about to write implementation code, SQL, analysis, or any substantive output yourself -- STOP. Delegate to a specialist.

### 4.1 Implementation Source Enforcement

Before proceeding past this phase, verify: **Did the output come from a specialist sub-agent?** If NO, HALT. Re-delegate to the appropriate specialist.

### 4.2 Specialist Selection

| Task Type | Execution Specialists |
|-----------|----------------------|
| Python code (backend, API, scripts) | `backend-python-engineer` |
| SQL / data pipelines | `data-analyst` or `python-data-engineer` |
| Data analysis (methodology, queries, charts) | `data-analyst` |
| Data extraction | `data-analyst` |
| Bug investigation | `code-debugger` |
| Infrastructure / deployment | `devops-engineer` |
| Prompt / protocol writing | `prompt-engineer` |
| Research / exploration | `Explore` |
| General / other | `general-purpose` |

**Support specialists** (invoked during or after execution, not as primary executors):
- `code-tester` -- test generation, after implementation
- `technical-writer` -- documentation updates, after validation

### 4.3 Delegation

When delegating to a specialist, provide:
- **Task description** -- what to do and why
- **Context** -- relevant files, prior research, constraints
- **Success criteria** -- what the output must satisfy
- **Complexity signal** -- lightweight | standard | complex | maximum

### 4.4 Model Selection

Specialists can use downgraded models for efficiency:

| Complexity | Model |
|-----------|-------|
| Lightweight (formatting, simple lookups) | `haiku` |
| Standard (implementation, analysis) | `sonnet` |
| Complex / Maximum (architecture, novel problems) | `opus` (default) |

**Cursor delegation**: For read-only tasks (reviews, exploration, peer challenge), consider routing to Cursor CLI instead of Claude sub-agents to conserve API quota. See [Cursor Delegation Protocol](./cursor-delegation.md).

### 4.5 Parallel Execution

If multiple specialists are needed for independent subtasks, launch them in parallel via agent teams (TeamCreate).

**Exit**: Implementation complete. Proceed to Phase 5.

---

## Phase 5: VALIDATION (Gate 2)

**[SOP] Entering Phase 5: Validation**

**HARD GATE: Do NOT proceed to Phase 6 until Gate 2 passes.** Skills that define their own gate structure follow their skill workflow instead.

All output must be independently reviewed before delivery.

### 5.1 Gate 2: Output Consensus

Default reviewers by task type. Skills with custom gate reviewers override this table.

Spawn reviewers IN PARALLEL based on task type:

| Task Type | Gate 2 Reviewers | What They Validate |
|-----------|-----------------|-------------------|
| Code | `code-reviewer` + `code-simplifier` + `architecture-simplifier` (skip arch for <=2 lines) | Correctness, simplicity, no over-engineering |
| Data analysis | `data-analyst` (different instance than executor) | Methodology sound? Findings valid? Conclusions supported? |
| Data extraction | `data-analyst` + `code-reviewer` | Data correct? Queries right? Results complete? |
| Infrastructure | `devops-engineer` (different instance) | Safe? Correct? Rollback plan? |
| Documentation | `code-reviewer` | Accurate? Clear? Complete? |
| Prompt/Protocol | `prompt-engineer` (different instance) + `architecture-simplifier` | Clear? Enforceable? No contradictions? Edge cases? |

**Gate 2 reviewer checklist** (in addition to domain-specific checks):
- [ ] No hard-coded data in notebooks (all data from real queries)
- [ ] No unused imports or dead code
- [ ] No trivial wrapper functions
- [ ] Output answers the original question

For this repository's protocol and skill changes, add `ai-engineer` to the Gate 2 review commission in addition to the default Prompt/Protocol reviewers.

**Consensus rules:** Same as Gate 1 -- all must APPROVE, max 3 iterations, then escalate.

**Contradiction-resolution protocol**: Apply the same contradiction trigger, contradiction record, Representative-side `next_action` normalization, required-slot rule, bounded conference wrapper, and conference-result rules used in Gate 1. The Gate 2 contradiction step stays inside the current iteration and does not replace explicit reviewer verdicts.

**Gate 2 applies to ALL changes in the default SOP workflow**: additions, modifications, AND deletions. Removing code can have cascading effects. Skills that define their own gate structure follow their skill workflow instead.

**Fake consensus guard**: Same as Gate 1. Actual sub-agent outputs required. No fabricated approvals.

**Cursor option**: Gate 2 reviewers can be routed to Cursor CLI per the [Cursor Delegation Protocol](./cursor-delegation.md). Highest token savings opportunity.

**Exit**: All reviewers APPROVE. Proceed to Phase 6.

---

## Phase 6: TESTING

**[SOP] Entering Phase 6: Testing**

Verify the output works. Testing varies by task type:


| Task Type | Testing Approach |
|-----------|-----------------|
| Code | Run test suite (`pytest`), run linter (`ruff`), verify no regressions |
| Data analysis | Cross-check key findings via independent query or alternative approach |
| Data extraction | Sanity checks: row counts, null rates, date ranges, known benchmarks |
| Infrastructure | Health check endpoint, verify correct version running |
| Prompt/Protocol | N/A (Gate 2 review is sufficient) |
| Documentation | N/A (Gate 2 review is sufficient) |

**If tests fail:**
1. Diagnose: test issue or implementation issue?
2. Loop back to Phase 4 (fix via specialist) -> Phase 5 (re-review) -> Phase 6 (re-test)
3. Maximum 3 fix iterations before escalating

**Exit**: Tests pass. Proceed to Phase 7.

---

## Phase 7: DOCUMENTATION

**[SOP] Entering Phase 7: Documentation**

**Owner**: Representative delegates to `technical-writer`

If the work changed behavior, patterns, or architecture, update relevant documentation.

### 7.1 What to Update

| Task Type | Documentation Target |
|-----------|---------------------|
| Code | README, CLAUDE.md, inline comments for non-obvious logic |
| Data analysis | Methodology notes, metric definitions |
| Data extraction | Schema docs, data dictionary |
| Infrastructure | Deployment docs, runbooks |
| Prompt/Protocol | Referenced protocol files, skill descriptions |

### 7.2 How to Update

- Spawn `technical-writer` to identify and update relevant docs
- Only update existing files (do not create new docs unless explicitly required)
- Documentation changes do NOT require Gate 2 re-review (they were validated during Gate 2)

**Exit**: Documentation updated. Proceed to Phase 8.

---

## Phase 8: DELIVERY

**[SOP] Entering Phase 8: Delivery**

**Owner**: Representative (main agent)

### 8.1 Artifact Delivery

| Task Type | Primary Deliverable |
|-----------|-------------------|
| Code | Summary of changes + file paths + test results |
| Data analysis | Jupyter notebook + findings summary |
| Data extraction | Jupyter notebook + key numbers |
| Infrastructure | Status report + verification evidence |
| Documentation | Updated doc files |
| Prompt/Protocol | File path + purpose + key design decisions + review feedback addressed |

### 8.2 Delivery Note

Gate 2 is fully automatic — once all reviewers APPROVE, proceed through testing and documentation without pausing for user approval.

**Include the gate status line in the delivery summary** (informational, not a gate):
```
[GATE 2: PASSED ✓] code-reviewer: APPROVE, code-simplifier: APPROVE, architecture-simplifier: APPROVE
```
or:
```
[GATE 2: SKIPPED — lightweight task / documentation only]
```

**Do NOT commit, push, or deploy without explicit user instruction.**

**Exit**: User has the deliverable.

---

## Phase 9: SELF-IMPROVEMENT

**In the default SOP workflow, this phase runs after every non-lightweight task.** Skills may define their own self-improvement triggers.

**Lightweight** = single-question lookups, config reads, or tasks with no decision-making or agent delegation. These skip Phase 9.

**[SOP] Entering Phase 9: Self-Improvement**

Follow the [Self-Improvement Protocol](./self-improvement.md) in realtime mode with current session evidence.

The protocol handles: issue review, process assessment, categorization, deduplication, proposal drafting (with user approval), and verification of prior improvements.

**Domain-specific dimensions**: If the task was executed under a domain skill (data-analysis, analytical-research, data-extraction), that skill's domain dimensions are reviewed in Step 1 of the protocol.

**Exit**: Session complete. All learnings captured.

---

## Session Logging

Structured `core-aiws` session logging is an optional future extension, not a v1 requirement.

If introduced later, use [Session Log Protocol](./session-log.md). Until then, rely on Claude Code native session history, observations, and project memory as the evidence surfaces.

---

## Escalation

See [Escalation Protocol](./escalation.md) for triggers, levels, format, and iteration limits.

Quick reference:
- Per consensus gate: 3 iterations max
- Per task: 10 execution iterations max
- Per session: 20 total iterations max
- First failure: try AGENT_SELF_RESOLVE (one attempt only)
- Multiple failures: escalate as AGENT_BLOCKED or NEEDS_HUMAN

---

## Role Taxonomy

### Representative (main agent)
- Understands intent, designs plan, delegates, reviews, presents
- NEVER writes implementation code, SQL queries, or analysis directly
- Exceptions: config values (env vars, paths, timeouts, feature flags), reading/presenting files

### Execution Specialists

| Role | Agent Type | Domain |
|------|-----------|--------|
| Python developer | `backend-python-engineer` | Backend, API, scripts, utilities |
| Data engineer | `python-data-engineer` | SQL, data pipelines, ETL |
| Data analyst | `data-analyst` | Analysis methodology, domain expertise |
| Bug investigator | `code-debugger` | Root cause analysis, minimal fixes |
| DevOps engineer | `devops-engineer` | Infrastructure, deployment, CI/CD |
| Prompt engineer | `prompt-engineer` | Protocol/skill writing, prompt optimization |
| General coder | `general-purpose` | Anything not covered above |

### Review Specialists

| Role | Agent Type | Focus |
|------|-----------|-------|
| Architecture reviewer | `architecture-simplifier` | Simplest approach? Over-engineering? |
| Code simplifier | `code-simplifier` | Can logic be simpler? Redundancy? |
| Code reviewer | `code-reviewer` | Correctness, security, standards |
| Domain reviewer | `data-analyst` | Methodology, findings validity |

### Support Specialists

| Role | Agent Type | When |
|------|-----------|------|
| Test writer | `code-tester` | After implementation, before Gate 2 |
| Technical writer | `technical-writer` | Phase 7 documentation updates |
| Prompt engineer | `prompt-engineer` | Phase 9 self-improvement |
| Explorer | `Explore` | Phase 2 research |

---

## Skill-Specific Overrides

Skills override SOP phases in their own SKILL.md. The SOP provides defaults; each skill's SKILL.md is authoritative for its execution details.

Currently registered skills with SOP overrides:

| Skill | Plugin | Override summary |
|-------|--------|-----------------|
| `/analytical-research` | `data-analysis-aiws` | Custom interview (Phase 1), domain-specific gates (1-3), stakeholder comprehension gate |
| `/data-analyst-forecast` | `data-analysis-aiws` | Custom gates with domain reviewers |

Skills not listed here follow SOP defaults.

---

## Escape Hatches

| Trigger | Behavior |
|---------|----------|
| User says "just do it" | Skip Phase 1 probing, fast-track to Phase 4 |
| Active Loop Mode | Skip verbose presentations, go diagnosis -> action -> next |
| Lightweight classification | Fast Path (see Complexity Classification) |
| User overrides a gate | Log the override, proceed as instructed |

---

## Completion Checklist

**Run this checklist for tasks following the default SOP workflow.**

- [ ] All output came from specialist sub-agents (not self-implemented)
- [ ] Gate 1 passed with actual sub-agent consensus (if applicable)
- [ ] User approved the Gate-1-approved plan (Phase 3) before execution began
- [ ] Gate 2 passed with actual sub-agent consensus (automatic — no user approval needed)
- [ ] Tests pass (if applicable)
- [ ] Required evidence surfaces were updated
- [ ] Phase 9 self-improvement completed (issues reviewed, improvements proposed)
- [ ] Auto-capture protocol executed

---

## What NOT to Do

| Forbidden | Why | Instead |
|-----------|-----|---------|
| Representative writes implementation code | Bypasses specialist expertise + review | Delegate to specialist (Phase 4) |
| Skip Gate 1 (plan review) | Unvalidated approach -> wasted work (in default SOP workflow) | Always get consensus before executing |
| Skip Gate 2 (output review) | Unvalidated output -> errors in delivery (in default SOP workflow) | Always get consensus before delivering |
| Skip Phase 9 (self-improvement) | Misses improvement opportunities (in default SOP workflow) | Run after every non-lightweight task |
| Commit without user approval | User controls git | Present results, wait for instruction |
| Continue past halt condition | Infinite loops waste time | Escalate to user |
| Self-approve your own plan | Confirmation bias | Independent reviewers validate |
| Hard-code data in notebooks | Not traceable or reproducible | All data from real queries (enforced in Gate 2 checklist) |
| Report fake consensus | Undermines entire quality system | Spawn actual reviewers, get actual votes |

# Escalation Protocol

Use this protocol when a task cannot safely or correctly continue within normal SOP loops.

## Triggers

Escalate when any of the following is true:

- a consensus gate fails after 3 iterations
- the required data cannot answer the question
- a contradiction-resolution record ends `strategically_unresolved` or `slot_unavailable`
- scope has materially expanded beyond the approved plan
- an external blocker prevents progress
- ambiguity cannot be resolved from code, docs, or context
- execution iterations reach the configured limit

Contradiction alone is not an escalation trigger. The bounded contradiction-resolution step must run first when SOP or skill rules require it.

## Levels

**AGENT_SELF_RESOLVE**
- one more bounded attempt is reasonable
- use only once per trigger

**AGENT_BLOCKED**
- progress cannot continue without a user decision or missing input

**NEEDS_HUMAN**
- the remaining decision is strategic, policy-sensitive, or otherwise human-owned

## Blocker Report

Use this format:

```md
## Escalation: <brief title>

**Level**: AGENT_SELF_RESOLVE | AGENT_BLOCKED | NEEDS_HUMAN
**Phase**: <SOP phase>
**Trigger**: <what triggered the escalation>

### What happened
<facts only>

### What I tried
- <attempt 1> — <result>
- <attempt 2> — <result>

### Options
1. <option A> — <trade-off>
2. <option B> — <trade-off>
3. Stop here — <what is lost>

### Recommendation
<one sentence>
```

## Limits

- gate iterations: 3
- execution iterations per task: 10
- total iterations per session: 20

## Resolution

After escalation is resolved:

1. note the resolution in the session log
2. identify the SOP phase being re-entered
3. continue without replaying the whole history unless requested

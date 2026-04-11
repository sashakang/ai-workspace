# Self-Improvement Protocol

Unified post-task improvement workflow for the `core-aiws` control plane.

## Mode Detection

Resolve mode first:

- **Realtime mode**: invoked from SOP Phase 9 with current-session evidence
- **Batch mode**: invoked from `/aiws-improve` with synthesized findings

Realtime mode runs all steps. Batch mode starts at Step 3.

## Learning Entry Format

Use this structure for explicit learnings:

```md
### <confidence: HIGH|MEDIUM|LOW> | <category>
- **Finding**: <what was learned>
- **Source**: <evidence source>
- **Target**: <plugin or file target>
- **Status**: captured | proposed | promoted | rejected
```

Supported categories:

- `user-preference`
- `project-pattern`
- `correction`
- `insight`
- `workflow-improvement`

## Step 1: Issue Review

Realtime mode only.

Review:

- agent failures
- methodology errors
- missing checks
- consensus struggles
- unclear instructions
- tool or environment friction

Include any domain-specific dimensions supplied by the calling skill.

## Step 2: Process Assessment

Realtime mode only.

Assess which phases delivered value and which created friction. Use concise phase-by-phase notes rather than verbose narratives.

## Step 3: Categorize and Decide

Classify each finding:

- `methodology-error`
- `unclear-instruction`
- `missing-check`
- `agent-failure`
- `consensus-struggle`
- `data-quality`
- `tooling-friction`

Then decide whether it belongs in:

- project memory
- shared-memory candidate capture
- skill/agent/protocol improvement
- no persistent change

## Step 4: Draft Proposals

For findings with confidence >= MEDIUM:

1. read the target through the installed plugin contract registry at `${CLAUDE_PLUGIN_DATA}/registry/plugins/*.json`
2. check whether the rule already exists
3. draft the smallest possible exact edit
4. present the edit for approval

Do not rely on ad hoc sibling-plugin filesystem discovery.

## Step 5: Apply and Record

For each approved change:

1. apply the edit
2. verify the edited artifact still reads cleanly
3. append a structured result to the current project daily log if relevant
4. run the [Auto-Capture Protocol](./auto-capture.md)

## Step 6: Verify Prior Improvements

Check whether previously applied improvements reduced recurrence:

- scan `${CLAUDE_PLUGIN_DATA}/improve/observations.jsonl`
- scan Claude Code native session history if the host environment makes it available
- report whether the same pattern recurred

## Step 7: Finalize Session Log

If a structured `core-aiws` session log exists, mark it complete and record any improvement proposals or decisions there. Otherwise rely on observations and delivery artifacts.

## Safety Rules

1. never auto-apply prompt, skill, or protocol edits without approval
2. prefer minimal edits
3. use evidence, not speculation
4. use plugin contracts to discover targets
5. do not treat self-improvement as the shared-memory refresh engine
6. shared-memory refresh is automatic through the host-side bridge, not `/aiws-improve`

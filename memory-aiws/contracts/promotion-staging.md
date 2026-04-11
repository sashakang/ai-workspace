# Shared Memory Candidate Outbox

Not every useful fact belongs in shared memory.

Use shared-memory candidate capture only for learnings that are:

- reusable across projects
- useful across multiple sessions
- not owned by a single Claude project
- stable enough to be worth keeping

## V1 producer model

Before a learning is consolidated into canonical shared memory, stage it locally as an immutable candidate event.

Producer surface:

```text
${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/
```

One file represents one candidate. Producers do not refresh shared memory directly.

Examples of eligible shared memory:

- analyst query heuristics that apply across projects
- recurring tool quirks
- durable workflow patterns
- prompt-improvement patterns that apply to multiple plugins

Examples that should stay out of shared memory:

- project-specific investigation details
- dataset or table specific findings
- one-off operational notes
- transient debugging state
- raw transcript excerpts

## Consolidation model

`memory-aiws` and the host-side shared-memory bridge handle:

- eligibility filtering
- quarantine of ineligible candidates
- deduplication
- confidence thresholds
- decay and staleness
- snapshot export and consumer import refresh

V1 operational scopes:

- `global.user-preferences`
- `global.tool-quirks`
- `global.workflow-patterns`
- `global.prompt-improvement-patterns`
- `domains.data-analyst`

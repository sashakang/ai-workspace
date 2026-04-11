# Auto-Capture Protocol

Run this protocol at the end of every non-lightweight task.

## 1. Append to project daily log

Write to the imported project-memory snapshot:

`${CLAUDE_PLUGIN_DATA}/project-memory/current/YYYY-MM-DD.md`

The native Claude project-memory surface remains canonical; approved writes are staged in the imported snapshot and then applied back through the host-side project-memory bridge.

Capture:

- what was done
- key findings or results
- important errors and how they were resolved
- project-specific quirks or conventions discovered
- effective queries, approaches, or workflows worth reuse in this project

## 2. Write shared-memory candidate outbox files

If a learning is clearly reusable across projects or plugins, stage it for `memory-aiws` instead of writing directly into another plugin root.

Use one immutable outbox file per candidate:

`${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/<ISO-ts>--<uuid>.json`

Each candidate file should include:

- `candidate_id`
- `ts`
- `plugin_id`
- `category`
- `scope`
- `summary`
- `evidence`
- `confidence`
- optional `source_project`

Critical-path rule:

- write the outbox file only
- do not wait for shared-memory consolidation or snapshot refresh before returning task results

Shared-memory consolidation and export are handled later by the host-side shared-memory bridge.

## 3. Record user corrections

If the user corrected behavior, assumptions, or workflow:

- append a structured observation to `${CLAUDE_PLUGIN_DATA}/improve/observations.jsonl`
- do not silently mutate durable memory files to “fix” the record

## 4. Propose workflow improvements

If the workflow should change, draft the exact proposed edit and target file, then route it through `/aiws-improve` and SOP review.

## 5. Keep capture scoped

Auto-capture should not:

- create a second project-memory system
- write directly into sibling plugin roots
- treat `/aiws-improve` as the routine shared-memory refresh trigger
- bypass approval for prompt, protocol, or skill changes

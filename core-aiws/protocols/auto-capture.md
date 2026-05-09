# Auto-Capture Protocol

Run this protocol at the end of every non-lightweight task.

## 1. Append to project daily log

Write to the host-provided project log or project-memory surface when one exists.

Hosts may expose this as a file, directory, MCP resource, or native memory bridge. If no writable project surface exists, skip the write and report that no project capture surface was available.

Capture:

- what was done
- key findings or results
- important errors and how they were resolved
- project-specific quirks or conventions discovered
- effective queries, approaches, or workflows worth reuse in this project

## 2. Write shared-memory candidate outbox files

If a learning is clearly reusable across projects or plugins, stage it for `memory-aiws` instead of writing directly into another plugin root.

Use the host-provided shared-memory candidate outbox when one exists. If the host exposes a filesystem outbox, write one immutable file per candidate.

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

- append a structured observation to the host-provided observation or improvement-marker surface, if one exists
- do not silently mutate durable memory files to “fix” the record

## 4. Propose workflow improvements

If the workflow should change, draft the exact proposed edit and target file, then route it through the canonical `aiws-improve` capability and SOP review.
If the current host does not expose slash commands, route it through the canonical `aiws-improve` capability by the host's native mechanism.

## 5. Keep capture scoped

Auto-capture should not:

- create a second project-memory system
- write directly into sibling plugin roots
- treat `aiws-improve` as the routine shared-memory refresh trigger
- bypass approval for prompt, protocol, or skill changes

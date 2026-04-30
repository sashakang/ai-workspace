# AIWS Productivity

`aiws-productivity` is a demo domain plugin that shows how an AIWS plugin should package focused skills without becoming part of the core platform.

It intentionally depends on `core-aiws` for shared process behavior. It does not own memory infrastructure.

## Skills

- `meeting-followup` — turns meeting transcripts or notes into minutes, decisions, action items, unresolved questions, and draft follow-up messages.

## Boundary

`aiws-improve` belongs to `core-aiws`, not this plugin. This plugin exists to demonstrate opt-in domain capability packaging in the AIWS ecosystem.

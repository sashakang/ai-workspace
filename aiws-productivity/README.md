# AIWS Productivity

`aiws-productivity` is a demo domain plugin that shows how an AIWS plugin should package focused skills without becoming part of the core platform.

It intentionally depends on `core-aiws` for shared process behavior. It does not own memory infrastructure.

## Skills

- `meeting-followup` — turns meeting transcripts or notes into minutes, decisions, action items, unresolved questions, and draft follow-up messages.

## Connectors

- `slack` (optional, host-managed) — lets `meeting-followup` read relevant Slack messages, threads, search results, or canvases when the user asks for Slack context. It can send or schedule Slack follow-up messages only after the user approves the exact text and destination.

The plugin must still work without Slack. If the connector is unavailable, produce copy-ready follow-up drafts instead of attempting Slack actions.

## Boundary

`aiws-improve` belongs to `core-aiws`, not this plugin. This plugin exists to demonstrate opt-in domain capability packaging in the AIWS ecosystem.

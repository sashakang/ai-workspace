---
name: meeting-followup
description: Turn meeting transcripts or notes into minutes, decisions, action items, and draft follow-up messages.
---

# Meeting Follow-Up

Use this skill when the user provides a meeting transcript, recording transcript, or meeting notes and wants practical follow-up material.

## Produce

- concise meeting minutes
- decisions made
- action items with owner and due date when available
- unresolved questions
- draft follow-up messages

## Slack Connector

If the optional Slack connector is available and the user explicitly asks for Slack context, use it to read relevant messages, threads, search results, or canvases before producing the follow-up.

If the user explicitly asks to send or schedule a Slack follow-up, show the exact message and target channel or thread first. Do not send, schedule, create, or update Slack content until the user approves the final text and destination.

## Boundaries

Do not create task dashboards.
Do not perform daily planning.
Do not perform stale task triage.
Do not create persistent workplace memory.
Do not manage recurring tasks.
Do not sync tasks into external tools.
Do not send or schedule Slack messages without explicit approval.

If owners, dates, or decisions are unclear, mark them as unspecified instead of inventing them.

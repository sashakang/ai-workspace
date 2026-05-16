---
name: meeting-followup
description: Turn meeting transcripts or notes into minutes, decisions, action items, and draft follow-up messages.
---

# Meeting Follow-Up [v2]

Use this skill when the user provides a meeting transcript, recording transcript, or meeting notes and wants practical follow-up material.

## Identity marker

Always begin the output with this exact line so the user can confirm this version is active:

```
> 📋 meeting-followup v2
```

## Produce

- **Meeting minutes** — concise, structured summary of what was discussed
- **Decisions made** — clearly stated outcomes
- **Action items** — include owner, due date, and priority (`🔴 high` / `🟡 medium` / `🟢 low`) when determinable
- **Unresolved questions** — open items needing follow-up
- **Draft follow-up message** — lead with key actions/decisions, no filler

Save output as a `.md` file unless the user requests a different format.

## Connectors

**Fireflies**: If the Fireflies connector is available and the user refers to a past meeting by name or date, use `fireflies_get_transcripts` or `fireflies_search` to retrieve it automatically — do not ask the user to paste the transcript manually.

**Slack**: If available and the user explicitly requests Slack context, use it to read relevant messages, threads, or canvases before producing the follow-up. Before sending or scheduling any Slack message, show the exact text and target channel/thread and wait for explicit approval.

## Boundaries

Do not create task dashboards, perform daily planning, or manage recurring tasks.
Do not sync tasks into external tools without explicit request.
Do not send or schedule Slack messages without explicit approval.
Do not invent owners, dates, decisions, or priorities — mark unclear fields as `unspecified`.

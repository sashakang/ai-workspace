# Cursor Delegation Protocol

Use Cursor CLI for read-heavy or review-heavy work when it reduces token cost without weakening quality.

## Preferred Uses

- Gate 1 reviews
- Gate 2 reviews
- exploration and read-only research
- peer challenge and diagnosis work

## Keep on Claude

- tasks that need MCP tools
- tasks that need file mutation
- prompt/protocol decisions that depend on full conversation state

## Command Pattern

Use a self-contained prompt file and pass it via Cursor CLI in ask/read-only mode.

Principles:

- include all relevant file content inline
- require an explicit `APPROVE` or `REQUEST_CHANGES` verdict
- fall back to Claude review if Cursor fails or returns an unparseable answer

## Fallback Rules

- one retry at most
- then fall back to Claude review
- do not block the workflow on Cursor availability

## Gate Rule

Cursor can fill a reviewer slot, but it does not change consensus rules:

- every required reviewer slot still needs an explicit verdict
- unparseable output is not an approval

# AIWS Cowork MCP Tool Exposure Blocker

**Date:** 2026-05-20  
**Status:** Open blocker  
**Area:** Cowork runtime / MCP tool exposure  
**Impact:** Blocks end-to-end Cowork validation of proposal staging and submission flows

## Summary

The current Cowork runtime does not expose the AIWS MCP tools required for proposal lifecycle testing:

- `aiws.skills.stage_proposal`
- `aiws.skills.submit_for_review`

This blocks end-to-end Cowork validation of the new backend-aware proposal staging foundation and any later Google Drive proposal flow.

This is a **runtime exposure problem**, not a proven feature-logic failure in the local repo implementation.

## What was observed

Multiple Cowork sessions were inspected for active and deferred tools.

Result:

| Tool | Status |
|---|---|
| `aiws.skills.stage_proposal` | Not exposed |
| `aiws.skills.submit_for_review` | Not exposed |

Observed behavior in session:

- Tool search returned no matching active or deferred tools for either name.
- The connected runtime exposed `core-aiws`, but only `aiws-improve` was visible from that plugin surface.
- No usable proposal staging or review-submission MCP surface was available in Cowork.

## Why this matters

The proposal backend work is now split into two distinct questions:

1. **Repo/runtime logic**  
   This has local implementation and test coverage.

2. **Cowork runtime availability**  
   This is currently blocked because the required MCP tools are not exposed in the tested environment.

Without these tools, Cowork cannot validate:

- GitHub proposal staging through the normal MCP path
- Google Drive proposal staging through the normal MCP path
- non-GitHub submit boundary behavior

## What is already proven elsewhere

The local repo implementation was updated and tested.

Evidence:

- backend-aware proposal staging was implemented in the AIWS MCP runtime
- focused unit tests passed
- full `tests.test_aiws_skill_manager` suite passed

What local tests now cover:

- GitHub proposal staging writes normalized backend metadata
- Google Drive proposal staging writes backend metadata and registers marketplace identity
- marketplace identity collision fails closed
- non-GitHub submit path fails cleanly with an explicit “not implemented yet” boundary

So the current blocker is **not** that the feature code is missing from the repo.

## Reproduction

In a Cowork chat:

1. inspect active and deferred tools
2. search for:
   - `aiws.skills.stage_proposal`
   - `aiws.skills.submit_for_review`
3. verify whether they are callable

Expected:

- both tools are exposed when the AIWS MCP runtime is correctly installed and connected

Actual:

- neither tool is exposed

## Most likely failure points

This is likely one of:

1. **Wrong installed runtime version**
   The Cowork environment may still be using an older packaged `core-aiws`.

2. **MCP server packaging mismatch**
   The shipped build may not include the updated `server.py` / runtime export surface.

3. **Server startup / registration failure**
   The AIWS MCP server may be partially connected or failing before tool registration.

4. **Tool filtering / gating at runtime**
   The server may be connected, but proposal tools may be hidden by environment flags or runtime filtering.

5. **Plugin install/update drift**
   Cowork may be loading a stale plugin copy while source and repo are newer.

## Immediate debugging checklist

1. Confirm the installed `core-aiws` version in the Cowork runtime.
2. Confirm the shipped `aiws_mcp/server.py` in the installed runtime contains:
   - `aiws.skills.stage_proposal`
   - `aiws.skills.submit_for_review`
3. Confirm the AIWS MCP server starts cleanly and fully registers tools.
4. Confirm no runtime feature gate suppresses proposal tools.
5. Confirm Cowork is loading the intended plugin copy, not an older cached copy.

## Current testing status

| Area | Status |
|---|---|
| Repo implementation | Passed locally |
| Local unit tests | Passed |
| GitHub staging metadata logic | Passed |
| Google Drive staging metadata logic | Passed |
| Marketplace collision guard | Passed |
| Cowork MCP tool exposure | Failed |
| Cowork end-to-end proposal testing | Blocked |

## Recommended next step

Treat this as a **runtime/MCP exposure bug** with separate ownership from the Google Drive backend feature work.

Do not continue Cowork functional testing of proposal flows until the missing MCP tools are visible in the runtime.

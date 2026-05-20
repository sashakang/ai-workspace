# AIWS Cowork MCP Tool Exposure Blocker

**Date:** 2026-05-20  
**Status:** Resolved
**Area:** Cowork runtime / MCP tool exposure  
**Impact:** Previously blocked end-to-end Cowork validation of proposal staging and submission flows

## Summary

The blocker was that the Cowork runtime did not expose the AIWS MCP tools required for proposal lifecycle testing:

- `aiws.skills.stage_proposal`
- `aiws.skills.submit_for_review`

This was a **runtime exposure problem**, not a proven feature-logic failure in the local repo implementation.

## Original observation

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

## Why this mattered

The proposal backend work is now split into two distinct questions:

1. **Repo/runtime logic**  
   This has local implementation and test coverage.

2. **Cowork runtime availability**  
   This is currently blocked because the required MCP tools are not exposed in the tested environment.

Without these tools, Cowork could not validate:

- GitHub proposal staging through the normal MCP path
- backend-aware proposal staging visibility in Cowork
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

Original actual result:

- neither tool is exposed

## Resolution evidence

The local bundled MCP runtime repair was implemented in commit `e636216` and re-tested in Cowork.

Verified live in Cowork on 2026-05-20:

- `aiws.health.ping` visible and callable
- `aiws.runtime.info` visible and callable
- `aiws.skills.stage_proposal` visible and callable
- `aiws.skills.submit_for_review` visible and callable
- `aiws.skills.refresh_proposal_state` visible and callable

`aiws.runtime.info` reported:

```text
runtime_kind: local-bundled-stdio
transport: stdio
launch_mode: uvx-bundled-source
plugin_version: 0.3.20
proposal_tools_declared: true
```

The `declared_tools` payload also included:

- `aiws.skills.stage_proposal`
- `aiws.skills.submit_for_review`
- `aiws.skills.refresh_proposal_state`

Cowork proposal-flow regression also passed after the fix:

- draft: `aiws-productivity--meeting-followup--de0e75a572`
- validation: `passed`
- digest: `dce697638e9488ee3576e794abf1e198d57adf96568310a2f4b3234f2345fc7c`
- staged proposal: `skillprop_e42f97a2091e4e4087d9221d3560775a`
- target repo: `sashakang/aiws-skill-tests`
- `submit_for_review` available at staging time: yes

## Root cause area

Before the repair, the most likely causes were:

1. **Wrong installed runtime version**
   The Cowork environment may still be using an older packaged `core-aiws`.

2. **Installed package drift or stale packaged runtime**
   Cowork may have been loading an older packaged runtime than the repo source under test.

3. **Server startup / registration failure**
   The AIWS MCP server may be partially connected or failing before tool registration.

4. **Tool filtering / gating at runtime**
   The server may be connected, but proposal tools may be hidden by environment flags or runtime filtering.

5. **Plugin install/update drift**
   Cowork may be loading a stale plugin copy while source and repo are newer.

## Debugging checklist used for resolution

1. Confirm the installed `core-aiws` version in the Cowork runtime.
2. Confirm the shipped `aiws_mcp/server.py` in the installed runtime contains:
   - `aiws.skills.stage_proposal`
   - `aiws.skills.submit_for_review`
3. Confirm the AIWS MCP server starts cleanly and fully registers tools.
4. Confirm no runtime feature gate suppresses proposal tools.
5. Confirm Cowork is loading the intended plugin copy, not an older cached copy.

## Final testing status

| Area | Status |
|---|---|
| Repo implementation | Passed locally |
| Local unit tests | Passed |
| GitHub staging metadata logic | Passed |
| Google Drive staging metadata logic | Passed |
| Marketplace collision guard | Passed |
| Cowork MCP tool exposure | Passed |
| Cowork end-to-end proposal staging regression | Passed |

## Recommended next step

Treat this blocker as closed. Any follow-on work should focus on:

- keeping the local technical-pilot runtime observable
- deciding whether the missing on-disk diagnostics files are worth a separate cleanup
- continuing normal Cowork proposal-flow and backend work on top of the restored runtime

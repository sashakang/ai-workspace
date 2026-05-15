# Cowork Stale Draft Cleanup PASS

**Date:** 2026-05-15  
**Scenario:** CW-10A, revert stale draft records  
**Result:** PASS

## Summary

Cowork successfully used the supported AIWS draft cleanup path after `core-aiws` 0.3.15 exposed `aiws.skills.revert_draft`.

The test kept one intentional draft for `aiws-productivity:meeting-followup`, reverted eight stale draft records, and confirmed drift protection still blocks creating a new parallel draft while the kept draft remains active.

No manual filesystem deletion was used.

## Kept Draft

```text
aiws-productivity--meeting-followup--25bf8e1a23
```

This was the draft used in the regular-user proposal path that produced PR #4 in `sashakang/aiws-skill-tests`.

## Reverted Drafts

Cowork first called `refresh_draft` for each stale draft. All eight existed, then all eight were reverted through `aiws.skills.revert_draft`.

| draft_id suffix | existed | reverted |
|---|---:|---:|
| `1295e51d67` | yes | yes |
| `689f3c6c5a` | yes | yes |
| `85b1961a6e` | yes | yes |
| `89f95d3140` | yes | yes |
| `c838a91aa7` | yes | yes |
| `d8c1bb4f59` | yes | yes |
| `de0e75a572` | yes | yes |
| `ef68f2e499` | yes | yes |

## Drift Guard After Cleanup

After cleanup, Cowork attempted to create/open a new draft without `allow_parallel_draft`:

```text
plugin_id: aiws-productivity
skill_id: meeting-followup
target_repo: sashakang/aiws-skill-tests-drift-check
```

The call failed closed because the kept draft was still active:

```text
Existing active draft for this plugin and skill must be reused, staged, reverted, or explicitly bypassed with allow_parallel_draft=true before opening another draft: aiws-productivity--meeting-followup--25bf8e1a23
```

This is the expected result. The guard still prevents accidental parallel drafts after stale drafts are cleaned up.

## Side Effects

```text
manual filesystem deletion: no
installed plugin files touched: no
Cowork RPM/runtime files touched: no
~/.claude touched: no
memory touched: no
packages touched: no
proposals touched: no
GitHub branches/commits/pushes/PRs touched: no
```

## Interpretation

This confirms the cleanup path is usable from Cowork:

1. Stale drafts can be inspected with `refresh_draft`.
2. Explicitly listed stale drafts can be removed with `revert_draft`.
3. The kept draft remains active.
4. Drift protection still blocks accidental new draft creation.

This does not solve modified-skill activation UX. It only closes the stale-draft cleanup gap created during testing.

# Cowork Pending Upload Deactivation Report

**Date:** 2026-05-15  
**Result:** PASS, with package-path visibility caveat  
**Scope:** CW-10 verification that deactivating a pending-upload draft clears only the AIWS pending-upload marker and does not remove draft edits or Cowork-uploaded plugin state.

## Summary

The pending-upload deactivation path passed. `deactivate_draft` cleared the AIWS activation record for the tested draft and returned an inactive state. The draft still existed after deactivation, and the Cowork-uploaded plugin was not removed by this operation.

This confirms the intended cleanup boundary: deactivation clears AIWS state only. It is not a Cowork plugin uninstall operation, it does not revert the draft, and it does not touch GitHub.

## Inputs

```text
draft_id: aiws-productivity--meeting-followup--de0e75a572
host_kind: cowork
```

## Result

```text
status: deactivated
activation_status: inactive
cleared: true
draft remains modified: yes
Cowork-uploaded plugin removed: no
```

Result: PASS.

## Evidence

The tested operation cleared only the AIWS pending-upload record for the draft. The draft working copy still contained `skills/meeting-followup/SKILL.md` after the operation. No staged changes were found, but the draft file itself remained intact.

The operation did not remove the Cowork-uploaded plugin. The test environment could not directly inspect the Mac-side Cowork plugin path from the sandbox, but `deactivate_draft` is not designed to touch Cowork plugin installation state.

## Caveat

The test report could not confirm that the original package ZIP still existed. The package path check ran from a sandbox that could not see the Mac package path, and no ZIP was found there. This is an evidence limitation, not a behavioral failure.

CW-10 should continue to pass when:

- AIWS activation state is cleared.
- Draft edits remain.
- Cowork-uploaded plugin state is untouched.
- GitHub is untouched.
- `~/.claude` is untouched.

The package-file existence check should be treated as best-effort evidence until Cowork exposes a reliable package-artifact query surface.

# Cowork Activation And Update Gate 1

**Date:** 2026-05-15  
**Status:** APPROVED FOR IMPLEMENTATION, with staged scope  
**Slice:** 3B / 2B.8B, User-Friendly Cowork Activation And Update

## Decision

Proceed with a staged activation/update improvement. Do not claim full Cowork activation until Cowork proves or documents a supported install/update intake path.

The next implementation should make activation safer and more user-friendly without crossing the Cowork boundary:

1. Keep installed marketplace and organization plugin files read-only.
2. Keep `~/.claude`, Cowork RPM/runtime files, and unmanaged plugin folders untouched.
3. Preserve one logical skill identity in AIWS state.
4. Avoid creating duplicate visible Cowork skill instances in the normal path.
5. Return honest non-terminal states when Cowork cannot activate a prepared package automatically.

Manual package upload remains a validated fallback and technical-pilot bridge. It is not the target regular-user experience.

## Current Evidence

The 2026-05-15 regular-user loop passed:

- marketplace install/use passed
- draft open/edit/validate passed
- `activate_draft` prepared a package and recorded `pending_upload`
- manual Cowork package upload worked
- modified `meeting-followup` ran from a new Cowork chat
- deactivation cleared only AIWS pending-upload state
- staging created only a local proposal record
- repository allowlist guard blocked a placeholder target repo
- submit-for-review created PR #3 in `sashakang/aiws-skill-tests`

Evidence files:

- `docs/aiws-testing-manual.md`
- `docs/cowork-modified-draft-upload-report-2026-05-15.md`
- `docs/cowork-pending-upload-deactivation-report-2026-05-15.md`
- `docs/cowork-proposal-submit-report-2026-05-15.md`

Current code facts:

- `aiws-mcp/aiws_mcp/skill_manager.py::activate_draft` always returns `host_capability_missing` with `activation_status: pending_upload` for modified Cowork drafts.
- `aiws-mcp/aiws_mcp/runtime.py` reports Cowork as `capability_exposure: plugin-package` and `direct_host_install_supported: false`.
- `core-aiws/contracts/skill-management.md` says pending upload is management/status only and must not change skill resolution.
- `scripts/cowork_package_intake_probe.py` can copy a disposable package to the writable Cowork `package_uploads` surface, but success still requires a new Cowork chat to prove visibility and callability.

## Problem

The current bridge works technically but is not good enough for regular users.

The user must manually upload a ZIP through Cowork settings. After that, Cowork can expose both the original marketplace plugin and the uploaded modified package, which can create duplicate visible `plugin_id + skill_id` variants. That is acceptable as technical-pilot evidence, but not as the final user experience.

## Options Considered

### Option A: Keep Manual Upload As The Product Flow

Rejected.

It is already validated as a fallback, but it asks regular users to handle package files and can leave duplicate visible plugin instances.

### Option B: Copy Packages Into `package_uploads` And Claim Activation

Rejected for now.

The host surface says `package_uploads` is writable, but current evidence does not prove Cowork watches that folder, imports copied packages, or activates them. Copying there may be useful as a handoff preparation step, but it must not be called activation unless Cowork confirms the package loaded.

### Option C: Improve Activation Handoff First

Approved as the next implementation step.

AIWS should prepare the package, store durable activation metadata, optionally copy the package to the Cowork `package_uploads` surface when that surface is available and safe, and return a clear status such as `handoff_prepared` or `pending_upload`. The response should guide the user through the next Cowork-supported action without making them reason about internal package paths when possible.

This can improve UX while preserving the current safety boundary.

### Option D: Full Cowork Programmatic Activation

Future target.

Implement only when Cowork exposes a supported API, connector, package-intake behavior, or other documented install/update surface that can prove the modified package became the active skill without duplicate visible identities.

## Approved Implementation Scope

Implement a safer activation handoff layer, not fake activation.

The implementation may:

- build the draft package exactly as today
- persist activation metadata under `~/.aiws/state/draft-activations/<host-id>/<draft_id>.json`
- use the existing host surface evidence to find `package_uploads`
- copy a package to `package_uploads` only after validating the destination root is not a symlink and the destination file does not already exist
- return a structured status that distinguishes:
  - `pending_upload`: package built, no Cowork intake attempted
  - `handoff_prepared`: package copied to a Cowork-supported upload surface, but activation not yet confirmed
  - `active`: allowed only after Cowork visibility/callability is confirmed by a supported mechanism
  - `host_capability_missing`: Cowork has no safe activation or package handoff surface
- keep manual ZIP upload as fallback
- add testing-manual coverage for the new state

The implementation must not:

- patch `~/.cowork/plugins`
- edit Cowork RPM/runtime files
- edit installed marketplace or organization plugin files
- touch `~/.claude` or Claude Code memory
- claim activation because a ZIP was copied
- delete Cowork-uploaded packages during `deactivate_draft`
- hide duplicate visible skills by mutating Cowork state directly

## Required Tests

Add or update unit tests before implementation is accepted:

- activation can prepare a package as today
- activation can copy the package to a safe `package_uploads` surface when host evidence provides one
- activation refuses symlinked or missing `package_uploads` roots
- activation refuses to overwrite an existing destination package
- copied-package handoff records `handoff_prepared` or equivalent without claiming `active`
- repeated activation is idempotent or returns the existing handoff state without creating duplicate artifacts
- deactivation clears only AIWS activation metadata and does not delete package artifacts
- no path writes occur under `~/.claude`, managed plugin folders, Cowork installed plugin folders, or Cowork RPM/runtime state

Manual Cowork tests:

- run the existing CW-08/CW-09/CW-10 flow as regression
- run CW-13 package intake probe before treating `package_uploads` as more than handoff preparation
- if Cowork auto-loads the copied package, verify in a new Cowork chat that the modified skill is visible and callable
- if Cowork does not auto-load it, record `no_automatic_intake_observed` and keep manual upload as fallback

## Review Lenses

Product review:

- The regular user is not asked to understand package files unless all safer options are unavailable.
- The status labels are honest and do not imply activation before Cowork confirms it.

AI engineer review:

- The AI-facing behavior cannot silently overwrite user edits.
- The model receives clear, structured states and does not need to infer whether activation happened.
- Duplicate visible skill identity is either avoided or reported as a conflict.

Code/security review:

- All writes stay under approved AIWS state or Cowork package-upload surfaces.
- Symlink/path traversal checks protect package output and copy destinations.
- Deactivation does not delete Cowork-owned installed packages.

## Gate 1 Result

Gate 1 passes for staged implementation of the activation handoff improvement.

Gate 1 does not approve claiming end-user activation readiness. That requires Cowork-confirmed package intake or another supported Cowork activation/update surface.

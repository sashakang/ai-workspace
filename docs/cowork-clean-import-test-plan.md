# Cowork Manual ZIP Import Fallback Test Plan

**Date:** 2026-05-13  
**Scope:** Validate the fallback Cowork ZIP import path for `core-aiws` and `aiws-productivity`.

This test checks the user-facing Cowork ZIP import flow. Marketplace install is now the primary user journey. Use this plan only when marketplace access is unavailable, when testing Team ZIP upload behavior, or when explicitly validating the fallback path. It does not test memory sync.

## Goal

Confirm that a Cowork user can install AIWS skills through Cowork's supported plugin upload flow and invoke `meeting-followup`, without touching existing Claude Code memory or manually editing Cowork runtime state. This is a fallback to marketplace install, not the preferred path for normal users.

## Safety Rules

- Do not delete, move, or edit `~/.claude`.
- Do not edit Claude Code memory, Claude project memory, or Claude plugin state.
- Do not run memory sync commands.
- Do not edit Cowork RPM files or manifests by hand.
- Do not reconstruct old marketplace entries.
- Do not copy plugin folders directly into Cowork runtime directories.
- Clean up older AIWS plugin installs only through Cowork's own UI, if Cowork provides an uninstall/remove action.

## Test Artifacts

Expected ZIP files:

```text
dist/cowork-import/core-aiws-0.3.16.zip
dist/cowork-import/aiws-productivity-0.2.1.zip
```

If you are testing from a fresh clone of the repository, build them from the repo root:

```bash
python scripts/build_cowork_import.py
```

The command should print:

```text
dist/cowork-import/core-aiws-0.3.16.zip
dist/cowork-import/aiws-productivity-0.2.1.zip
```

For a normal pilot user, the maintainer can provide these ZIP files directly. The pilot user should not need Python for the upload test itself.

## Preconditions

- Cowork is installed and signed in.
- The account has access to Cowork's plugin upload/import UI.
- Existing Claude Code memory is present and remains untouched.

## Test Steps

1. Open Cowork.
2. Open the plugin management area.
3. Remove any previously installed AIWS test plugins through Cowork's own UI, if Cowork provides a remove/uninstall action. Do not edit runtime files, RPM manifests, marketplace records, or `~/.claude`.
4. Record whether cleanup was completed, skipped because there were no old AIWS plugins, or blocked because Cowork did not expose a safe remove action.
5. Find the supported upload/import path. The validated path was:

```text
Organization settings -> Plugins -> Add plugin -> Upload a file
```

6. Upload `core-aiws-0.3.16.zip`.
7. Confirm `core-aiws` appears as installed or active.
8. Upload `aiws-productivity-0.2.1.zip`.
9. Confirm `aiws-productivity` appears as installed or active.
10. Open Cowork's skill, plugin, or capability surface.
11. Confirm `meeting-followup` is visible.
12. Invoke `meeting-followup` with this input:

```text
Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork plugin import install first.
```

## Expected Result

The skill returns meeting follow-up notes that include:

- the decision to validate the Cowork plugin import install path
- an action item for Alice to send the draft by Friday
- an action item for Ben to review after Alice sends the draft
- a short draft follow-up message

## Pass Criteria

Mark the test as `PASS` only if all are true:

- Cowork imports both plugins through its own UI.
- No Cowork runtime state is edited manually.
- `core-aiws` installs successfully.
- `aiws-productivity` installs successfully.
- `meeting-followup` is visible.
- `meeting-followup` can be invoked successfully.
- `~/.claude` remains untouched.
- No memory sync command is run.

## Fail Or Block Criteria

Mark the test as `FAIL` if:

- Cowork rejects either ZIP.
- The plugin appears installed but `meeting-followup` is not visible.
- `meeting-followup` is visible but cannot be invoked.
- The flow requires manual RPM edits, runtime folder copying, or old marketplace reconstruction.

Mark the test as `BLOCKED` if:

- Cowork has no visible upload/import path.
- The account lacks permission to upload plugins.
- Cowork crashes or prevents plugin management before the ZIPs can be tested.

## Evidence To Record

Record:

- Cowork version/build.
- Account type.
- Exact plugin import UI path.
- Exact upload/import action label.
- Whether previous AIWS installs were removed through Cowork UI, absent, or blocked from safe removal.
- Whether both ZIPs were accepted.
- Installed plugin names and IDs, if Cowork shows IDs.
- Whether `meeting-followup` is visible.
- A short summary of the `meeting-followup` output.
- Any error messages.
- Confirmation that `~/.claude` was not touched.
- Confirmation that no memory sync commands were run.

## Report Template

```text
Cowork clean import test result: PASS / FAIL / BLOCKED

Tester:
Date:
Cowork version/build:
Account type:

Previous AIWS installs removed through Cowork UI: yes/no/not applicable
Import UI path:
Import action label:

Artifacts tested:
- core-aiws-0.3.16.zip:
- aiws-productivity-0.2.1.zip:

Installed plugins:
- core-aiws:
- aiws-productivity:

Visible skills:
- meeting-followup visible: yes/no

Invocation proof:
Input:
Output summary:

Safety:
~/.claude touched: no/yes
Memory sync commands run: no/yes
RPM files edited manually: no/yes

Logs/errors:

Result notes:
Open blockers:
```

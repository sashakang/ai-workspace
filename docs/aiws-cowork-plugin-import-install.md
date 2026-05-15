# AIWS Cowork Plugin Import Install

This guide covers the fallback Cowork-supported ZIP import path for Phase 1 validation.

This is not the primary marketplace install path. Marketplace install is now the primary user journey after the user reported that Cowork installed the AIWS marketplace plugins and generated `meeting-followup` nodes correctly.

Use this path when marketplace access is unavailable, when validating Team ZIP upload behavior, or when explicitly testing fallback recovery. This path can count as a clean Cowork-supported fallback install if Cowork performs the plugin import through its own UI or supported import mechanism. It does not count as clean if the tester edits RPM files, reconstructs marketplace entries, copies files into Cowork runtime folders, or restores old plugin state.

Runtime status: passed on 2026-05-11 for a Team account in Cowork build 1.6608.2. See [AIWS Cowork Plugin Import Validation PASS](./aiws-cowork-plugin-import-validation-pass.md).

## Scope

Install only the minimum Phase 1 plugins:

- `core-aiws`
- `aiws-productivity`

The proof of success is that Cowork shows and can invoke the `meeting-followup` skill from `aiws-productivity`.

Do not install `memory-aiws`, `data-analysis-aiws`, or `software-engineer-aiws` in this first import test unless Cowork explicitly requires a dependency. Do not run memory sync commands.

## Safety Rules

- Do not delete, move, or edit `~/.claude`.
- Do not edit Claude Code memory, Claude project memory, or Claude plugin state.
- Do not run `aiws-host-memory bootstrap`, `refresh-shared`, `bootstrap-cowork`, or `refresh-cowork`.
- Do not edit Cowork RPM manifests by hand.
- Do not reconstruct old RPM entries.
- Do not copy plugin folders directly into Cowork runtime directories.

## Import Artifacts

The Phase 1 import artifacts are built under:

```text
dist/cowork-import/
```

Expected files:

```text
core-aiws-0.3.17.zip
aiws-productivity-0.2.1.zip
```

The passing runtime test used the individual plugin ZIPs. Cowork accepted a flat archive root with `.claude-plugin/plugin.json`, `skills/`, `contracts/`, and `README.md`.

## Test Procedure

1. Open Cowork.
2. Find the supported plugin import path. Possible labels may include:
   - Import plugin
   - Upload plugin
   - Install from file
   - Install from zip
   - Install local plugin
   - Developer mode import
3. Import `core-aiws-0.3.17.zip`.
4. Confirm `core-aiws` appears as installed or active.
5. Import `aiws-productivity-0.2.1.zip`.
6. Confirm `aiws-productivity` appears as installed or active.
7. Open the Cowork skill, plugin, or capability surface.
8. Confirm `meeting-followup` is visible.
9. Invoke `meeting-followup` with this input:

```text
Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork plugin import install first.
```

## Evidence To Record

Record:

- Cowork version/build.
- Account type.
- Exact plugin import UI path.
- Exact import action label.
- Whether Cowork accepts individual plugin zips.
- Whether Cowork accepts a multi-plugin bundle.
- Any required archive layout.
- Whether `core-aiws` installs.
- Whether `aiws-productivity` installs.
- Whether `meeting-followup` is visible.
- Whether `meeting-followup` can be invoked.
- Any error text or logs.
- Confirmation that `~/.claude` was not touched.
- Confirmation that no memory sync commands were run.

## Pass Criteria

This import path passes only if all are true:

- Cowork imports the plugins through its own UI or supported import mechanism.
- No Cowork runtime state is edited by hand.
- `core-aiws` imports successfully.
- `aiws-productivity` imports successfully.
- `meeting-followup` is visible in Cowork.
- `meeting-followup` can be invoked.
- Existing Claude Code memory remains untouched.

## Fail Criteria

Mark this path as failed if any are true:

- Cowork has no supported plugin import path.
- Cowork rejects the plugin package format.
- The install requires manual edits to RPM state or Cowork runtime files.
- The install requires restoring old marketplace registration.
- `meeting-followup` is not visible after import.
- `meeting-followup` is visible but cannot be invoked.

## Report Template

```text
Cowork plugin import validation result: PASS / FAIL / BLOCKED

Tester:
Date:
Cowork version/build:
Account type:

Import UI path:
Import action label:
Package format tested:
Archive layout accepted:

Artifacts tested:
- core-aiws:
- aiws-productivity:
- bundle:

Installed plugins:
- core-aiws:
- aiws-productivity:

Visible skills:
- meeting-followup visible: yes/no

Invocation proof:
Input:
Output summary:
Evidence that aiws-productivity/meeting-followup was invoked:

Safety:
~/.claude touched: no/yes
Memory sync commands run: no/yes
RPM files edited manually: no/yes

Logs/errors:

Result notes:
Open blockers:
```

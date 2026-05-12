# AIWS Cowork GitHub Marketplace Runtime Validation Checklist

This checklist is for a developer or tester with direct Cowork access validating the GitHub marketplace-registration path for AIWS.

Current status: this GitHub marketplace-registration path is blocked in Cowork build 1.6608.2 for the tested Personal account. The working Phase 1 install gate is now the Cowork Team plugin import path documented in [AIWS Cowork Plugin Import Install](./aiws-cowork-plugin-import-install.md) and validated in [AIWS Cowork Plugin Import Validation PASS](./aiws-cowork-plugin-import-validation-pass.md).

This checklist remains useful only if the GitHub marketplace path becomes available later. It is not the active prerequisite for Phase 2.

Use this checklist alongside:

- [AIWS Cowork Laptop Test Safety](./aiws-cowork-laptop-test-safety.md)
- [AIWS Cowork GitHub Marketplace Install](./aiws-cowork-fresh-marketplace-install.md)
- [AIWS Cowork Plugin Import Install](./aiws-cowork-plugin-import-install.md)
- [AIWS Skills-Only Cowork Marketplace Architecture](./aiws-skills-cowork-marketplace.md)
- [AIWS Project Development Plan](./aiws-project-development-plan.md)

## Laptop Safety Gate

If the tester has operational Claude Code memory on the same laptop, complete the safety protocol before starting:

- [AIWS Cowork Laptop Test Safety](./aiws-cowork-laptop-test-safety.md)

Pass this gate only when:

- existing Claude Code memory remains untouched
- Claude Code remains operational
- previous Cowork test installs have been moved to a timestamped backup, not deleted
- previous `~/.aiws` test/runtime state has either been moved to backup or explicitly left in place because it may contain active work
- no `aiws-host-memory` memory sync commands have been run for Phase 1

Do not proceed if the only way to get a clean Cowork setup requires deleting or modifying `~/.claude`, Claude project memory, Claude plugin data, or the canonical `memory-aiws` store.

## Scope

Validate only the static Cowork marketplace and plugin install path:

- Add or install the AIWS marketplace through Cowork's marketplace UI.
- Install `core-aiws`.
- Install one domain plugin, starting with `aiws-productivity`.
- Confirm that `meeting-followup` is visible and invocable in Cowork.
- Record the concrete marketplace layout Cowork accepted.

Do not include these in Phase 1 validation:

- MCP setup, MCP tools, or local control-plane behavior.
- Memory sync or shared-memory bridge behavior.
- Draft creation, draft editing, draft activation, or `Modified locally` behavior.
- GitHub submission, pull request creation, or publication workflows.
- Direct writes to `~/.cowork`.
- Cloning repositories as the user install path.
- Symlinking plugin folders.
- Manual copying of marketplace or plugin files into Cowork runtime folders.
- Cleaning, refreshing, importing, exporting, or repairing Claude Code memory.

If the only way to complete the install is cloning, symlinking, manual copying, or editing `~/.cowork` directly, mark the GitHub marketplace path as failed. That may still be useful diagnostic evidence, but it is not a clean Cowork-supported install path.

## Preconditions

Record these before testing:

- Tester:
- Date:
- Cowork app/version or build:
- Operating system:
- Cowork account type: Personal, Team, or Enterprise
- Fresh setup condition: new Cowork profile, cleared plugin state, separate test account, or other clean-state method
- Claude Code memory preservation check completed: yes/no
- Previous Cowork state backed up or absent: yes/no
- Previous `~/.aiws` state backed up, absent, or intentionally left in place: backed up/absent/left in place
- AIWS marketplace repo or local fixture path:
- AIWS branch, tag, commit, or package version:

The current repo docs say read-only validation found the marketplace manifest at:

```text
.claude-plugin/marketplace.json
```

They also say that manifest currently points to root-level plugin source directories such as:

```text
./core-aiws
./aiws-productivity
```

Do not assume Cowork accepts that layout until this runtime test proves it. Also do not assume Cowork requires this alternate shape unless the runtime test proves it:

```text
.claude-plugin/marketplace.json
plugins/
  aiws-productivity/
    .claude-plugin/plugin.json
    skills/
      meeting-followup/
        SKILL.md
```

## Static Artifact Check

Before opening Cowork, inspect the marketplace source used for the runtime test.

Record:

- Exact marketplace repo URL or local fixture path:
- Exact `marketplace.json` path:
- Exact `core-aiws` plugin manifest path:
- Exact `aiws-productivity` plugin manifest path:
- `marketplace.json` includes `name`, `owner`, and `plugins`: pass/fail
- Each tested plugin entry includes `name`, `source`, `version`, and `description`: pass/fail
- Each tested plugin has a matching `.claude-plugin/plugin.json`: pass/fail
- `core-aiws` contract or manifest version inspected:
- `aiws-productivity` contract or manifest version inspected:
- Version alignment across marketplace entries, plugin manifests, and contracts: pass/fail
- `meeting-followup` skill folder path:
- `meeting-followup/SKILL.md` exists: pass/fail
- `SKILL.md` frontmatter includes only `name` and `description`: pass/fail
- Skill folder name matches frontmatter `name`: pass/fail
- Static validation command or script used, if any:
- Static validation output path or copied output:

## Cowork Marketplace Path

Start from the clean Cowork setup recorded above. Use Cowork's supported marketplace flow, not manual filesystem installation.

Record the exact UI path and labels:

- Cowork surface used, such as Personal marketplace or Organization settings:
- Exact menu/settings path:
- Exact button or action label for adding a marketplace:
- Exact text field label for the marketplace repo/path:
- Exact confirmation, install, or enable action label:
- Screenshot or copied Cowork surface text showing the marketplace add path:

For a Personal account, verify whether the documented "Add marketplace from GitHub" action exists and record the exact current label. For a Team or Enterprise account, verify the organization-managed plugin path and record the exact current labels.

## Marketplace Add Result

Attempt to add or install the AIWS marketplace through Cowork.

Record:

- Marketplace repo/path submitted to Cowork:
- Marketplace name shown by Cowork:
- Marketplace owner or scope shown by Cowork:
- Marketplace add result: pass/fail
- Cowork confirmation text:
- Any warning, trust, permission, or duplicate-scope prompt:
- Any error text:
- Screenshot or copied Cowork surface text:
- Runtime log location, if exposed:
- Relevant log excerpt or attached sanitized log:

Pass this step only if Cowork accepts the marketplace through its marketplace UI. Fail this step if the flow requires cloning, symlinking, copying files, or direct `~/.cowork` edits.

## Source Layout Result

Record which plugin source layout Cowork actually accepted.

- Root-level sources accepted, such as `./core-aiws` and `./aiws-productivity`: yes/no/unknown
- `plugins/<plugin-id>` layout required: yes/no/unknown
- Other accepted layout, if any:
- Evidence: marketplace entry, Cowork display text, log line, or screenshot:
- If root-level sources failed, exact failure text:
- If `plugins/<plugin-id>` was required, exact passing fixture path:

This is a required Phase 1 evidence item because the current docs identify root-level sources as the observed repo shape but do not yet have runtime Cowork proof.

## Plugin Install Check

Install `core-aiws` and `aiws-productivity` from the added AIWS marketplace.

Record:

- `core-aiws` visible in Cowork marketplace/plugin list: pass/fail
- `core-aiws` install action label:
- `core-aiws` installed plugin ID shown by Cowork:
- `core-aiws` installed version shown by Cowork:
- `aiws-productivity` visible in Cowork marketplace/plugin list: pass/fail
- `aiws-productivity` install action label:
- `aiws-productivity` installed plugin ID shown by Cowork:
- `aiws-productivity` installed version shown by Cowork:
- Installed plugin IDs after install:
- Cowork confirmation text for each plugin:
- Plugin install screenshot or copied Cowork surface text:
- Runtime logs or errors from plugin install:

Pass this step only if both plugins install through the Cowork marketplace/plugin UI.

## Skill Visibility Check

Open the Cowork skill, plugin, command, or capability surface where installed skills are visible.

Record:

- Exact Cowork UI path used to view installed skills:
- Exact Cowork label for the skills surface:
- Visible skills from `core-aiws`:
- Visible skills from `aiws-productivity`:
- `aiws-productivity/meeting-followup` visible: pass/fail
- Exact visible skill label for `meeting-followup`:
- Any namespace Cowork displays, such as plugin ID, marketplace, owner, or scope:
- Screenshot or copied Cowork surface text showing `meeting-followup`:
- Runtime logs or errors from skill discovery:

For Phase 1, `meeting-followup` must be visible as a starter skill supplied by `aiws-productivity`. If Cowork shows only an unqualified `meeting-followup`, record that exact display and the surrounding plugin or namespace evidence.

## Skill Invocation Check

Invoke `meeting-followup` in Cowork using the normal Cowork skill invocation path.

Use a harmless test input, for example:

```text
Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork marketplace install first.
```

Record:

- Exact Cowork UI path or invocation syntax used:
- Exact visible skill selected:
- Test input used, sanitized if needed:
- Invocation result: pass/fail
- Output summary or copied sanitized output:
- Evidence that Cowork used `aiws-productivity/meeting-followup`, not a different skill:
- Screenshot or copied Cowork surface text showing the invocation:
- Runtime logs or errors from invocation:

Pass this step only if Cowork can run the installed `meeting-followup` skill and return a plausible skill response.

## Installed State Evidence

If Cowork exposes an installed plugin state file or equivalent export, collect a sanitized copy.

Expected current candidate path from the project plan is:

```text
~/.cowork/plugins/installed_plugins.json
```

Do not create, edit, or repair this file as part of Phase 1 validation. Read it only if Cowork created or exposes it.

Record:

- `installed_plugins.json` available: yes/no
- Exact path or export surface:
- Sanitized copy attached or pasted: yes/no
- Contains `core-aiws`: yes/no
- Contains `aiws-productivity`: yes/no
- Contains versions or source refs: yes/no
- Sensitive fields removed: yes/no/not applicable

Sanitize tokens, local usernames if needed, private repo credentials, machine-specific secrets, and unrelated installed plugins. Keep plugin IDs, versions, source refs, marketplace identifiers, and timestamps when safe.

## Logs And Errors

Collect logs or copied error text for the whole attempt.

Record:

- Marketplace add logs/errors:
- Plugin install logs/errors:
- Skill discovery logs/errors:
- Skill invocation logs/errors:
- Cowork app log path or export method, if known:
- Any network, auth, trust, schema, manifest, version, duplicate, or layout errors:
- Whether the same error reproduces from a fresh setup:

If a step fails, preserve the first meaningful error. Later cascading errors are useful, but the first failure usually explains the real blocker.

## Pass/Fail Criteria

Phase 1 passes only if all of these are true:

- A fresh Cowork setup can add or install the AIWS marketplace through Cowork's intended marketplace path.
- The install path does not require cloning, symlinking, manual copying, or direct writes to `~/.cowork`.
- Cowork accepts a documented marketplace source layout, and the accepted layout is recorded as root-level sources, `plugins/<plugin-id>`, or another specific shape.
- `core-aiws` installs from that marketplace path.
- `aiws-productivity` installs from that marketplace path.
- Installed plugin IDs are recorded.
- `meeting-followup` is visible in Cowork as a skill from `aiws-productivity`.
- `meeting-followup` can be invoked in Cowork.
- Runtime evidence is collected: UI labels/path, screenshots or copied surface text, logs/errors, and sanitized installed state if available.

Phase 1 fails if any of these are true:

- Cowork cannot add the AIWS marketplace through its marketplace UI.
- Cowork requires manual cloning, symlinking, file copying, or direct `~/.cowork` writes to complete the install.
- Cowork cannot install `core-aiws`.
- Cowork cannot install `aiws-productivity`.
- `meeting-followup` is not visible after install.
- `meeting-followup` is visible but cannot be invoked.
- The accepted source layout cannot be determined.
- Required evidence is missing or based only on repo inspection rather than Cowork runtime behavior.

Mark as blocked, not passed, if Cowork access, account permissions, network access, marketplace permissions, or organization policy prevents a clean runtime test.

## Validation Report Template

Use this format when reporting results back into the repo or issue tracker.

```text
Phase 1 Cowork runtime validation result: PASS / FAIL / BLOCKED

Tester:
Date:
Cowork version/build:
Account type:
Fresh setup method:

Marketplace repo/path:
AIWS branch/tag/commit:
marketplace.json path:
core-aiws plugin manifest path:
aiws-productivity plugin manifest path:

Cowork marketplace UI path:
Marketplace add action label:
Plugin install surface/path:
Skill visibility surface/path:
Skill invocation path/syntax:

Accepted source layout:
Root-level sources accepted: yes/no/unknown
plugins/<plugin-id> required: yes/no/unknown
Evidence for layout result:

Installed plugin IDs:
- core-aiws:
- aiws-productivity:

Visible skills:
- core-aiws:
- aiws-productivity:
- meeting-followup visible: yes/no

Invocation proof:
Input:
Output summary:
Evidence that aiws-productivity/meeting-followup was invoked:

installed_plugins.json:
Available: yes/no
Sanitized copy attached: yes/no
Path/export surface:

Logs/errors:
Marketplace add:
Plugin install:
Skill discovery:
Skill invocation:

Pass/fail notes:
Open blockers:
```

# Cowork Registry Alignment Gate 1

**Date:** 2026-05-15  
**Status:** APPROVED FOR IMPLEMENTATION  
**Scope:** Read-only Cowork installed-skill registry alignment and duplicate identity handling.

## Decision

Implement a read-only Cowork registry-alignment slice before attempting more activation UX work.

The immediate problem is now clear: after a modified `aiws-productivity:meeting-followup` package was uploaded, Cowork could run the updated skill, but AIWS metadata could not resolve it. The live skill invocation loaded from a Cowork hostloop cache path, while AIWS `resolve` and `discover_installed_plugins` still operate from AIWS-owned catalog/search roots or explicitly supplied plugin roots.

The next implementation must make this mismatch visible and structured. It must not try to fix it by editing Cowork RPM/plugin folders, deleting duplicate uploads, patching hostloop caches, or pretending the active instance is known when Cowork has not provided that signal.

## Evidence

Runtime evidence from `core-aiws` 0.3.9 is recorded in [Cowork Activation Handoff 0.3.9 Runtime Report](./cowork-activation-handoff-039-runtime-report-2026-05-15.md).

Key observations:

- `activate_draft` safely returned `host_capability_missing` and wrote a `pending_upload` record.
- Manual Cowork upload of the prepared package worked.
- `meeting-followup` was visible and ran successfully after upload.
- The loaded `SKILL.md` contained the expected test edit.
- Cowork had duplicate visible `aiws-productivity` instances.
- The live skill invocation loaded from a hostloop path:

```text
/var/folders/ts/qdbqrt412bnb972vcvtqd4x40000gs/T/claude-hostloop-plugins/29e408ad64584ef3/skills/meeting-followup
```

- `aiws_skills_resolve` could not resolve the same installed skill in AIWS metadata.

Code evidence:

- `aiws-mcp/aiws_mcp/runtime.py::resolve_skill` resolves only AIWS catalog records.
- `aiws-mcp/aiws_mcp/skill_manager.py::discover_installed_plugins` scans explicit/default plugin search roots for `.claude-plugin/plugin.json`.
- The existing installed-plugin discovery already fails closed with `ambiguous_installed_plugin` when multiple matching plugin roots are found.
- `create_or_open_draft` can disambiguate by explicit `source_plugin_root`, but that is not a normal-user UX.

## Source Of Truth Order

For the next slice, use this order of trust:

1. Cowork plugin-management/tool output when available for user-visible installed plugins and enabled/visible state.
2. AIWS host surfaces for writable/read-only boundaries and host identity.
3. AIWS-owned draft, activation, and proposal state under `~/.aiws`.
4. Explicitly supplied trusted plugin roots for maintainer or diagnostic flows.
5. Cowork hostloop paths only as runtime evidence, not durable source of truth.

Hostloop paths are temporary runtime caches. They can prove what ran in a specific session, but they must not become a durable registry or draft source.

## Approved Implementation

Add a read-only Cowork registry-alignment operation or extend the existing installed-plugin discovery response so AIWS can report installed Cowork skill instances as structured evidence.

The response should be able to represent:

- logical identity: `marketplace`, `plugin_id`, `skill_id`
- installed instance identifiers when Cowork exposes them
- source plugin root when safely known
- whether the instance is visible in Cowork
- whether AIWS can resolve the skill through its catalog
- whether the same logical skill has duplicate visible installed instances
- whether the runtime-loaded path is known only as session evidence
- whether a caller must choose an explicit source before draft/edit work can continue

This slice is diagnostic and registry-alignment work. It may read known Cowork/AIWS surfaces, but it must not mutate:

- Cowork RPM/runtime folders
- installed marketplace or organization plugin files
- uploaded plugin files
- hostloop cache directories
- `~/.claude`
- memory roots
- GitHub state
- proposal records, unless a later explicit proposal operation is called

If a small AIWS-owned observation cache is needed, it must live under an AIWS-owned path such as `~/.aiws/hosts/<host-id>/shared-cache/` or `~/.aiws/state/`, and the response must make clear that the cache is an observation, not Cowork's source of truth. Prefer a read-only response first.

## Duplicate Handling

If exactly one installed instance matches a logical skill, AIWS may report it as the default candidate.

If multiple instances match the same `plugin_id + skill_id`, AIWS must return a structured ambiguous state such as:

```text
duplicate_visible_identity
```

or reuse the existing:

```text
ambiguous_installed_plugin
```

It must not silently choose one instance unless Cowork provides a reliable active/loaded signal or the caller pins a concrete `source_plugin_root` or installed instance ID.

The user-facing explanation should be simple:

```text
Cowork has more than one installed copy of this skill. The updated copy works, but AIWS cannot safely tell which copy should be treated as the managed source. Clean this up through Cowork's plugin UI or choose the exact source explicitly.
```

AIWS must not delete or disable Cowork uploads in this slice.

## Not Approved

This Gate 1 does not approve:

- direct writes to Cowork installed plugin folders
- hostloop cache patching
- automatic duplicate cleanup
- claiming a modified draft is active before Cowork confirms it
- using hostloop paths as long-term source roots
- asking normal users to inspect RPM paths
- adding another manual-ZIP step as the final product UX

## Required Tests

Add focused tests before or with implementation:

- one installed Cowork-style plugin instance resolves as a single candidate
- duplicate installed instances return an ambiguous/duplicate state
- explicit source pinning disambiguates without changing installed files
- hostloop paths are reported as ephemeral runtime evidence only
- missing Cowork plugin evidence returns a structured unavailable/not-found result, not a guessed source
- the operation performs no writes outside approved AIWS-owned state, and preferably no writes at all
- existing `discover_installed_plugins` ambiguity behavior remains intact

## Gate 1 Review

Product review: PASS. The plan protects normal users from being asked to reason about RPM paths, while still surfacing the real duplicate-install problem.

Architecture review: PASS. The plan keeps Cowork as install/update owner and AIWS as draft/proposal/diagnostic owner.

AI engineering review: PASS. The response must give AI agents explicit ambiguity and source evidence instead of letting them infer the active skill from whichever file path they happen to see.

Security review: PASS. The plan avoids arbitrary filesystem scanning, installed-plugin mutation, hostloop mutation, and private-state exposure.

Gate result: **approved for a read-only implementation slice.**

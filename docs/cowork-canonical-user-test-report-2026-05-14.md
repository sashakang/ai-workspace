# Cowork Canonical User Test Report

**Date:** 2026-05-14  
**Result:** PASS  
**Scope:** Canonical Cowork marketplace install, skill use, user-driven update, and AIWS host-surface boundary check.

## Summary

The canonical Cowork user path passed. Cowork installed the AIWS marketplace `sashakang/ai-workspace`, installed and activated `core-aiws` and `aiws-productivity`, exposed `meeting-followup`, invoked the skill successfully, and kept the skill visible after the user updated the marketplace and plugins through the Cowork UI.

This validates the normal user path for install, use, and update. It does not validate direct runtime installation by AIWS. That path is unsupported by design: Cowork owns install and update through marketplace/package upload, while AIWS prepares, stages, validates, materializes to AIWS-owned roots, and packages artifacts for Cowork-supported install surfaces.

## Installed Marketplace And Plugins

- Marketplace installed and active: `sashakang/ai-workspace`.
- `core-aiws` installed with plugin ID `core-aiws@ai-workspace`.
- `aiws-productivity` installed with plugin ID `aiws-productivity@ai-workspace`.
- Cowork `list_plugins` did not expose plugin-level versions.
- The `aiws-improve` skill reported `v1.0.0`, but plugin-level versions were not visible through the Cowork plugin listing.

## Skill Visibility And Invocation

- `meeting-followup` was visible as `aiws-productivity:meeting-followup`.
- `meeting-followup` was callable.
- The skill generated meeting notes with the expected decision and action items.

Finding: the skill output had a date normalization defect. The test date was Thursday, May 14, 2026, so "Friday" should normalize to May 15, 2026. The output instead used Friday, 2026-05-16. This is a skill/model output issue, not an install, visibility, package, or update blocker.

## Cowork Update Check

- The marketplace and installed plugins were updated by the user through the Cowork UI.
- `meeting-followup` remained visible after the update.
- The update path did not require a repo clone, terminal command, manual RPM/runtime edit, direct write to installed Cowork plugin folders, or `~/.claude` edit.

## Host Surface Check

The initial `aiws.host.surfaces` call failed because `host_kind` was omitted. Retrying with `host_kind: cowork` passed.

Host result:

```text
host_id: cowork-db8a0e250a1c
host_kind: cowork
capability_exposure: plugin-package
direct_host_install_supported: false
```

Surface evidence:

- `host_identity`: file writable at `~/.aiws/hosts/cowork-db8a0e250a1c/host.json`.
- `staged_skill_changes`: directory writable at `~/.aiws/hosts/cowork-db8a0e250a1c/staged-writes/skills`.
- `materialized_skills`: directory writable at `~/.aiws/hosts/cowork-db8a0e250a1c/shared-cache/skills`.
- `skill_adapter`: directory writable at `~/.aiws/hosts/cowork-db8a0e250a1c/adapter`.
- `skill_catalog`: MCP resource read-only at `aiws://skills`.
- `installed_plugins`: directory read-only at `~/.cowork/plugins`.
- `package_uploads`: directory writable at `~/.cowork/packages`.

## Product Boundary Confirmed

The tested boundary is:

- Cowork owns plugin install, plugin update, and activation through marketplace or package upload.
- AIWS owns source validation, staged changes, proposal records, AIWS-local materialization/cache output, adapter output, and package preparation.
- AIWS must not directly write into Cowork installed plugin folders or mutate Cowork runtime/RPM state.
- The canonical Cowork user path must not require repo cloning, terminal usage, manual RPM/runtime edits, direct `~/.cowork/plugins` edits, or `~/.claude` edits.

## Follow-Up

- Track the `meeting-followup` Friday date normalization issue as a skill/model output finding.
- Keep direct runtime install marked unsupported unless Cowork exposes and documents a supported local runtime install capability.
- Keep package upload as the bridge for AIWS-prepared artifacts that need Cowork-owned installation.

# Cowork Native Custom Marketplace Source Request

**Date:** 2026-05-23
**Status:** Open product/integration blocker
**Owner:** Cowork integration track

## Summary

AIWS can now publish a Cowork-shaped marketplace projection from a governed Google Drive release, but Cowork native plugin tools do not expose any way to register, browse, sync, or install from that custom source. This blocks first-class Cowork visibility for AIWS-compatible domain plugins.

The immediate requested capability is a Cowork-native custom marketplace source flow that can consume:

```text
repository: sashakang/ai-workspace
branch: master
path: generated/cowork-drive-bridge
marketplace: aiws-cowork-drive-bridge
```

Longer term, Cowork should support AIWS Drive marketplaces directly or through an equivalent provider API.

## Current Evidence

The generated bridge artifact exists in `sashakang/ai-workspace` under `generated/cowork-drive-bridge/` and contains:

- `.claude-plugin/marketplace.json`
- `.aiws-bridge/provenance.json`
- `productivity/.claude-plugin/plugin.json`
- `productivity/skills/meeting-followup/SKILL.md`

The bridge marketplace validates locally as:

```text
marketplace: aiws-cowork-drive-bridge
plugin: productivity
version: 0.2.4
skill: meeting-followup
```

The native Cowork plugin tools available in the test session were:

- `mcp__plugins__list_plugins`
- `mcp__plugins__search_plugins`
- `mcp__plugins__suggest_plugin_install`

Observed limitation:

- no tool accepts `repository`
- no tool accepts `branch`
- no tool accepts `path`
- no tool accepts `source` or `ref`
- no tool can register or browse a custom Git marketplace
- search is limited to Cowork's fixed marketplace backend

Native visibility test result:

- marketplace `aiws-cowork-drive-bridge`: not visible
- plugin `productivity` version `0.2.4`: not visible
- skill `meeting-followup`: not visible

## Required Cowork Capability

Cowork should expose a native marketplace source operation that can register or browse a custom marketplace source.

Minimum API shape:

```json
{
  "repository": "sashakang/ai-workspace",
  "branch": "master",
  "path": "generated/cowork-drive-bridge"
}
```

Minimum resulting behavior:

1. Cowork reads `.claude-plugin/marketplace.json` from the supplied path.
2. Cowork lists marketplace `aiws-cowork-drive-bridge` in the native plugin marketplace surface.
3. Cowork lists plugin `productivity` version `0.2.4`.
4. Cowork lists skill `meeting-followup` under `productivity`.
5. Cowork can install `productivity` through its native plugin install path.
6. Cowork can later update `productivity` when the same bridge path publishes a newer version.

## Required Tooling Surface

Any of these would unblock the flow:

- `plugins.register_marketplace_source`
- `plugins.list_marketplace_sources`
- `plugins.sync_marketplace_source`
- `plugins.search_plugins` with source parameters
- equivalent native UI flow that is observable from tools

The operation must be Cowork-native. AIWS-only marketplace registration does not satisfy this requirement because first-class plugin status requires Cowork Directory/catalog visibility and Cowork-owned install/update.

## Acceptance Test

From a fresh Cowork session:

```text
Register or browse the custom Git marketplace source repository sashakang/ai-workspace, branch master, path generated/cowork-drive-bridge.
Then search native Cowork plugins for Productivity.
Report marketplace name, plugin id, plugin version, skill id, and install/update availability.
```

PASS only if:

- marketplace `aiws-cowork-drive-bridge` is visible through Cowork native plugin tools or UI
- plugin `productivity` version `0.2.4` is visible
- skill `meeting-followup` is visible
- install is initiated through Cowork's native plugin path
- no AIWS Drive workflow, AIWS materialized cache, ZIP upload, or direct installed-plugin edit is used

## Non-Goals

- Do not make AIWS write directly into Cowork installed plugin directories.
- Do not use ZIP upload as the normal user path.
- Do not treat AIWS materialization as native Cowork installation.
- Do not require users to inspect `~/.aiws` paths.
- Do not register the generated bridge as a second AIWS backend-of-record for `checkout-main/productivity`.

## Why This Matters

The bridge projection already provides a Cowork-compatible artifact with provenance back to the governed AIWS Drive release. The remaining gap is Cowork ownership of discovery, install, update, and activation. Without a Cowork-native custom marketplace source flow, AIWS-compatible plugins cannot become first-class Cowork plugins from the tested session.

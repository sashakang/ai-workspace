# Phase 1 Install Test — BLOCKED

**Date:** 2026-05-11  
**Tester:** Sasha Kang  
**Repo:** sashakang/ai-workspace  
**Status:** ❌ BLOCKED — clean install path not available in current Cowork build

---

## Environment

| Field | Value |
|---|---|
| Cowork / Claude Desktop version | 1.6608.2 |
| Account type | Personal (tengu_team_discovery = false) |
| OS | macOS |
| Session ID | 3581ad1d-5821-4080-b19b-b01a25310587 |

---

## Target Scenario

1. Add marketplace `sashakang/ai-workspace` via Cowork UI
2. Install `core-aiws` then `aiws-productivity` through the plugin browser
3. Verify `meeting-followup` skill is visible and invocable

---

## UI Path Attempted

Settings → Plugins → marketplace controls

**Finding:** No functional "Add marketplace from GitHub" input field was found. User confirmed: "I can't enter the repo URL." The field either does not exist in this build, is disabled, or does not accept input. No error text was produced — the action was simply not possible.

---

## Local Config Edits Attempted

Two files were modified in an attempt to register the marketplace:

**1. `cowork_settings.json` — `extraKnownMarketplaces` field**
```
Path: .../3581ad1d-.../cowork_settings.json
Added: "ai-workspace": { "source": { "source": "github", "repo": "sashakang/ai-workspace" } }
```
Result: No effect on plugin browser after app restart.

**2. `cowork_plugins/known_marketplaces.json`**
```
Path: .../3581ad1d-.../cowork_plugins/known_marketplaces.json
Added: "ai-workspace" entry matching the format of existing marketplaces
```
Result: No effect on plugin browser after app restart.

**Why these edits had no effect:**  
The Cowork plugin browser uses the RPM system (`rpm/manifest.json` + `rpm/plugin_*/`), not the local `cowork_plugins/` config. The RPM system uses server-assigned marketplace IDs (e.g., `marketplace_01DqsDz3URSQoArVumWHMeZ7`). Registering a marketplace requires a backend API call that the local config files cannot replicate. The `extraKnownMarketplaces` field appears to serve the legacy `cowork_plugins` system only, which is no longer what the plugin browser reads from.

---

## Relevant Feature Flags (GrowthBook)

| Flag | Value | Notes |
|---|---|---|
| `tengu_plugin_official_mkt_git_fallback` | `true` | Git fallback for **official** marketplaces only — does not cover personal repos |
| `tengu_skills_dashboard_enabled` | `false` | Skills dashboard disabled |
| `tengu_claudeai_mcp_connectors` | `true` | — |
| `tengu_team_discovery` | `false` | Confirms Personal account |

---

## Pre-Test State

All 5 ai-workspace plugins were already installed before the test began (installed 2026-05-06T20:00:12Z via RPM system):

- `core-aiws` → plugin_01DDSTE7crN3GNZvBGNNPgEj
- `aiws-productivity` → plugin_01Nw5odsxnP26iWF48mkD1aN
- `memory-aiws` → plugin_012tcm8rxqyqbhKWimTbq9Hn *(was installed as dependency)*
- `data-analysis-aiws` → plugin_01BBFBHgcrF5FRyjLRiQHL9T
- `software-engineer-aiws` → plugin_01GLQtyB3JCZDpYMLrsEyYXF

These were uninstalled to create the clean state for this test.

---

## Backup

Pre-test RPM manifest backed up at:
```
.../3581ad1d-.../rpm/manifest.json.bak
```
Contains the original 9-plugin state (4 knowledge-work-plugins + 5 ai-workspace).

---

## Safety Confirmations

| Check | Status |
|---|---|
| `~/.claude` modified | ✅ NOT touched |
| `~/.claude/memory` modified | ✅ NOT touched |
| `~/.claude/projects` modified | ✅ NOT touched |
| Memory sync commands run | ✅ NONE run |
| Git clone used | ✅ NOT used |
| Symlinks created | ✅ NONE created |

---

## Files Modified During Test

| File | Change | Reversible |
|---|---|---|
| `rpm/manifest.json` | Removed 5 ai-workspace plugin entries | Yes — backup at `manifest.json.bak` |
| `rpm/plugin_01DDSTE7crN3GNZvBGNNPgEj/` | Directory deleted | Via restore from backup + re-download |
| `rpm/plugin_01Nw5odsxnP26iWF48mkD1aN/` | Directory deleted | Via restore from backup + re-download |
| `rpm/plugin_012tcm8rxqyqbhKWimTbq9Hn/` | Directory deleted | Via restore from backup + re-download |
| `rpm/plugin_01BBFBHgcrF5FRyjLRiQHL9T/` | Directory deleted | Via restore from backup + re-download |
| `rpm/plugin_01GLQtyB3JCZDpYMLrsEyYXF/` | Directory deleted | Via restore from backup + re-download |
| `cowork_settings.json` | Added `ai-workspace` to `extraKnownMarketplaces` | Reversible |
| `cowork_plugins/known_marketplaces.json` | Added `ai-workspace` entry | Reversible |

---

## Conclusion

The clean installation path via Cowork UI is **not available** in build 1.6608.2 for Personal accounts. The marketplace registration flow requires a backend API call that has no exposed UI control. Custom/personal GitHub marketplaces cannot be added through any available interface.

**Recommendation:** File with Anthropic — "Add marketplace from GitHub" UI flow is non-functional or absent for Personal accounts in v1.6608.2. The feature may be gated to Team/Enterprise or scheduled for a future release.

**Next step (your decision):** Restore the original RPM state from `manifest.json.bak` to return to working pre-test configuration.

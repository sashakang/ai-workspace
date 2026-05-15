# Cowork Registry Alignment Gate 1

**Date:** 2026-05-15  
**Status:** APPROVED AND REDUCED
**Scope:** Small read-only check for installed skill copies.

## Simple Plan

Before AIWS edits, activates, or stages a Cowork skill, it needs one basic safety check:

```text
How many installed copies of plugin_id:skill_id can Cowork/AIWS see?
```

If there is one copy, AIWS can treat it as the source for draft/edit work.

If there is more than one copy, AIWS must stop and report that the skill is ambiguous. It must not guess which copy the user means.

If there is no copy, AIWS reports that the skill is not installed or not discoverable.

## Why This Exists

The `core-aiws` 0.3.9 test proved that a manually uploaded modified `aiws-productivity:meeting-followup` package can run in Cowork. It also showed a problem: Cowork could run the updated skill, but AIWS metadata could not resolve the same skill, and duplicate `aiws-productivity` installs were visible.

That is risky because a user could edit one copy while Cowork runs another.

## Approved Implementation

Add a read-only operation:

```text
aiws.skills.inspect_installed_skill(plugin_id, skill_id, search_roots?, source_plugin_root?)
```

Expected behavior:

- zero matching skill copies -> `installed_skill_not_found`
- one matching skill copy -> `ok`
- more than one matching skill copy -> `duplicate_visible_identity`
- explicit `source_plugin_root` -> use that source if it contains the requested skill

The response should include the matching instance paths for diagnostics, but the normal user-facing message should stay simple:

```text
Cowork has more than one installed copy of this skill. AIWS cannot safely choose which copy to manage.
```

## Boundaries

This check must not:

- delete Cowork uploads
- edit Cowork RPM/runtime folders
- patch hostloop caches
- touch `~/.claude`
- touch memory
- touch GitHub
- stage or submit proposals

Hostloop paths may be mentioned only as evidence of what ran in one session. They are not durable source paths.

## Required Tests

The implementation needs tests for:

- one installed copy returns `ok`
- duplicate installed copies return `duplicate_visible_identity`
- no matching skill returns `installed_skill_not_found`
- explicit source pinning returns `ok` when the source contains the skill
- the runtime wrapper exposes the same behavior without writing memory or `~/.claude`

Gate result: **approved for the small read-only duplicate/source check.**

## Gate 1 Addendum: Default Cowork Install Roots

**Date:** 2026-05-15
**Status:** APPROVED FOR NEXT IMPLEMENTATION

The first runtime test of `aiws.skills.inspect_installed_skill` on `core-aiws` 0.3.10 partially passed. The tool worked when Cowork supplied the explicit RPM plugin root, but default discovery returned `installed_skill_not_found` because the RPM install path was not in the default search roots.

The next implementation is intentionally narrow: add known Cowork and Claude local-agent session install roots to default discovery so a normal Cowork user does not need to know or pass `source_plugin_root`.

Approved behavior:

- keep `inspect_installed_skill(plugin_id, skill_id)` read-only
- add Cowork RPM/plugin install roots and Claude local-agent session RPM roots to default search roots when they are safely discoverable
- preserve current status behavior:
  - zero copies -> `installed_skill_not_found`
  - one copy -> `ok`
  - multiple copies -> `duplicate_visible_identity`
- keep explicit `source_plugin_root` as a diagnostic/maintainer override
- do not scan arbitrary filesystem locations
- do not mutate Cowork RPM/runtime folders, hostloop caches, installed plugins, `~/.claude`, memory, GitHub, drafts, activations, or proposals

The implementation should prefer concrete known roots, for example:

```text
<COWORK_HOME>/rpm
<COWORK_HOME>/plugins
~/.cowork/rpm
~/.cowork/plugins
~/Library/Application Support/Claude/local-agent-mode-sessions/*/rpm
~/Library/Application Support/Claude/local-agent-mode-sessions/*/*/rpm
~/Library/Application Support/Claude/local-agent-mode-sessions/*/*/*/rpm
```

and keep the existing environment override:

```text
AIWS_PLUGIN_SEARCH_ROOTS
```

For tests and unusual host layouts, the local-agent session root may be overridden with:

```text
AIWS_CLAUDE_LOCAL_AGENT_SESSIONS_ROOT
```

Required tests:

- default discovery includes a Cowork RPM root under `COWORK_HOME`
- default discovery includes a bounded Claude local-agent session RPM root
- `inspect_installed_skill` finds one skill from that RPM root without explicit `source_plugin_root`
- duplicate RPM plugin roots still return `duplicate_visible_identity`
- missing roots are ignored safely
- no writes occur

Gate result: **approved for default Cowork RPM/plugin and local-agent session RPM root discovery.**

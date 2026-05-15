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

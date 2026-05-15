# Cowork Installed Skill Inspection PASS

**Date:** 2026-05-15  
**Scenario:** 9A, inspect installed copies of `aiws-productivity:meeting-followup`  
**Result:** PASS

## Summary

Cowork successfully ran the installed-copy inspection without an explicit `source_plugin_root`.

The tool found the actual Cowork session RPM install for `aiws-productivity:meeting-followup`, selected it automatically, and did not mutate any state.

## Result

```text
status: ok
instance_count: 1
selected_instance: present
duplicate copies found: no
anything mutated: no
```

Selected instance:

```text
plugin_id: aiws-productivity
skill_id: meeting-followup
base_version: 0.2.1
origin_marketplace: rpm
origin_ref: cowork-upload
base_commit: uploaded
runtime_evidence: installed_plugin_root
skill_root: .../rpm/plugin_01UbGZsu5hJezcVifsV8C75U/skills/meeting-followup
skill_file: SKILL.md present
```

Discovery searched seven roots across two local-agent session trees and found one matching plugin instance.

## Interpretation

This confirms the `core-aiws` 0.3.12 discovery fix works for the current Cowork runtime shape. AIWS can now find the installed Cowork session RPM copy without asking the user for a filesystem path.

The safety check is now usable in the normal Cowork path:

- one installed copy means AIWS can proceed against the selected source
- duplicate installed copies still fail closed with `duplicate_visible_identity`
- no installed copy still returns `installed_skill_not_found`

This does not solve activation UX. It removes the immediate source-selection ambiguity before draft/edit/activate/stage work continues.

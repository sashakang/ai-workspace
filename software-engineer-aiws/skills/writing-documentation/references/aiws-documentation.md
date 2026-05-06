# AIWS Documentation

Use this reference when documenting AIWS plugins, skills, contracts, MCP behavior, memory, or host adapters.

## Platform Model

AIWS is a composable workspace. The shared foundation lives in `core-aiws`; shared memory lives in `memory-aiws`; domain plugins add opt-in workflows.

When documenting AIWS behavior, keep these boundaries clear:

- `core-aiws`: SOP, self-improvement, process protocols, and skill-management rules.
- `memory-aiws`: shared memory contracts, canonical memory files, import/export behavior, and promotion staging.
- domain plugins: skills, agents, references, bootstrap guidance, and domain-specific contracts.
- `aiws-mcp`: local skill control plane for search, resolve, materialize, get, stage, and list operations.
- `~/.aiws/`: local runtime root for personal skills, host cache, adapters, indexes, locks, staged writes, and host identity.

## Skill Documentation Rules

- Skill folder name must match the `name` field.
- `SKILL.md` frontmatter contains only `name` and `description` for AIWS skill-creator compatibility.
- Skill names use lowercase letters, digits, and single hyphens.
- Keep `SKILL.md` focused on trigger, workflow, references, boundaries, and validation.
- Move detailed patterns into `references/` files linked directly from `SKILL.md`.
- Do not add `README.md`, changelogs, quick references, or installation guides inside a skill folder.
- Scripts must be optional support assets, not hidden policy.

## Contract And Marketplace Rules

When adding or changing a plugin:

- update `.claude-plugin/plugin.json`
- update the plugin contract under `contracts/`
- list exposed skills in `public_skills`
- list dependencies explicitly
- add the plugin to the marketplace when it should be installable
- keep marketplace, plugin, and contract versions aligned
- run the existing release validation gate

## Memory Boundaries

Document memory as advisory context unless a contract says otherwise.

- Project memory is local to the active project context.
- Shared memory stores reusable cross-project patterns and preferences.
- Personal or shared writes must not be implied unless the workflow explicitly stages or writes them.
- Do not copy raw transcripts or sensitive evidence into docs unless the user explicitly asks and the target scope is appropriate.

## Host Compatibility

When documenting host behavior, distinguish host kind from host identity.

- host kind: `claude-code`, `cowork`, or `codex`
- host id: the local state boundary under `~/.aiws/hosts/<host-id>/`
- materialized skill cache: `~/.aiws/hosts/<host-id>/shared-cache/skills/`
- generated adapters: `~/.aiws/hosts/<host-id>/adapter/`

Avoid documenting undocumented host install paths as if they are stable.

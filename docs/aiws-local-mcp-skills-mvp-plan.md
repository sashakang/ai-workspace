# AIWS Local MCP Skills MVP

## Summary

Build `aiws-mcp`, a local Python stdio MCP server that becomes the AIWS skills control plane. It replaces the plugin/helper-first skills model with one local MCP runtime that discovers, validates, materializes, and stages skills while preserving compatibility with Claude Code, Cowork, and Codex through generated host adapters.

This MVP is local-only: no remote company sync, remote downloads/uploads, shared memory migration, or script execution. Existing plugin/helper code stays intact during this slice.

Gate 1 status: passed, including the later host-path simplification.

- Architecture reviewer: approved
- Prompt/protocol reviewer: approved
- Implementation reviewer: approved after revisions for MCP tool I/O, host identity, integrity hashing, and materialization write boundaries

## Key Changes

- Add a new `aiws-mcp` Python package with CLI entrypoint `aiws-mcp`.
- Use `~/.aiws/` as the canonical runtime root for personal skills, materialized cache, host adapter outputs, staged skill-change proposals, indexes, locks, and host identity state.
- Use Agent Skills-compatible bundles with required `SKILL.md`, `name`, and `description`; optional `references/`, `assets/`, inert `scripts/`, and AIWS-only `agents/`.
- Implement internal validation:
  - `name`: 1-64 chars, lowercase letters/numbers/hyphens, no edge or consecutive hyphens
  - `description`: 1-1024 chars
  - safe relative entrypoint paths only
- Add MCP-first built-ins:
  - `aiws.sop`
  - `aiws.improve`
  - `aiws://protocols/sop`
  - `aiws://skills/aiws-improve`
- Adapt SOP/improve away from plugin-era assumptions like `CLAUDE_PLUGIN_DATA`, installed plugin registries, and helper-managed paths.
- Use `aiws-improve` as the only canonical improve identity; generate `/aiws-improve` where the host supports slash invocation. Do not generate `/improve`.
- Add reference skill `meeting-followup` for transcripts/notes to minutes, decisions, action items, and draft follow-up messages only.

## Interfaces And Runtime Behavior

MCP tools:

```text
aiws.skills.search({query?, scopes?, host_kind?, limit?})
  -> {results: [{skill_id, name, description, scope, version, source, supported_hosts, scripts_supported, materialized}]}

aiws.skills.resolve({skill_id, scope?, version?, host_kind?})
  -> {status, manifest?, reason?, candidates?}

aiws.skills.materialize({skill_id, scope?, version?, host_kind, host_id?})
  -> {status, manifest, cache_path, adapter_path, integrity_hash}

aiws.skills.list_local({scope?, host_kind?})
  -> {skills: [...]}

aiws.skills.get({skill_id, scope?, version?, include_content?})
  -> {manifest, entrypoint_content?, references?}

aiws.skills.stage_change({skill_id, target_scope, base_version?, summary, rationale, diff?, bundle_path?, evidence?})
  -> {proposal_id, proposal_path, status: "staged"}

aiws.skills.list_staged_changes({target_scope?, skill_id?})
  -> {proposals: [...]}
```

Catalog sources:

```text
~/.aiws/personal/skills/
bundled aiws-improve and SOP resources
bundled meeting-followup
already-materialized local cache entries
contract-only remote fixture records
```

Duplicate shared skill IDs fail closed unless scope/version is pinned. Remote fixture records are metadata only in MVP.

Materialization writes only under:

```text
~/.aiws/hosts/<host-id>/shared-cache/skills/
~/.aiws/hosts/<host-id>/adapter/
```

It never writes directly into `~/.claude`, `~/.cowork`, `~/.codex`, project repos, or host config files.

Integrity:

- Each materialized bundle gets `sha256:<digest>`.
- Digest is computed from sorted relative file paths plus file bytes.
- Symlinks are rejected.
- Digest is verified after copying into cache and before writing adapter output.

## Host Compatibility

Host identity:

```text
~/.aiws/hosts/<host-id>/
├── host.json
├── shared-cache/skills/
├── adapter/
└── staged-writes/skills/
```

`host-id` is the visible local identity/state boundary. `host-kind` is stored in `host.json` and tells AIWS which adapter format to generate.

`host.json`:

```json
{
  "host_id": "my-claude-code",
  "host_kind": "claude-code",
  "config_root": "/Users/example/.claude"
}
```

- `--host-kind`: `claude-code`, `cowork`, or `codex`
- optional `--host-id`
- default config roots:
  - `claude-code`: `$CLAUDE_HOME`, else `~/.claude`
  - `cowork`: `$COWORK_HOME`, else `~/.cowork`
  - `codex`: `$CODEX_HOME`, else `~/.codex`
- if `--host-id` is omitted, derive `host-id = <host-kind>-<sha256(canonical_resolved_host_config_root)[:12]>`
- persist identity in `~/.aiws/hosts/<host-id>/host.json`
- later commands may use `--host-id` alone
- if `--host-id` is supplied alone and `host.json` does not exist, fail clearly and ask for `--host-kind`
- if supplied CLI values conflict with existing `host.json`, fail closed

Adapters:

- Claude Code: generate `adapter/.claude/skills/<skill-id>/SKILL.md`.
- Cowork: generate `adapter/aiws-generated-plugin/.claude-plugin/plugin.json` and `adapter/aiws-generated-plugin/skills/<skill-id>/SKILL.md`.
- Codex: generate `adapter/skills/<skill-id>/SKILL.md` and `adapter/aiws-codex-export.json`; do not hard-code undocumented Codex install paths.

## Privacy And Promotion

- `stage_change` writes immutable local proposal files under `~/.aiws/hosts/<host-id>/staged-writes/skills/`.
- No upload happens in MVP.
- Raw transcripts or evidence are copied only when explicitly supplied by the user.
- Personal skills and staged evidence are not sent to remote APIs.

## Test Plan

- Clean-machine MCP availability for SOP and `aiws-improve` without `core-aiws`, `memory-aiws`, domain plugins, or helper scripts.
- Built-in skills pass the same validator as user skills.
- SOP/improve built-ins contain no legacy plugin-path assumptions.
- Host ID derivation, `host.json` persistence, conflict handling, and missing-first-registration errors.
- Skill validation rejects invalid frontmatter and unsafe paths.
- Materialization rejects path traversal, symlinks, and bad integrity.
- Duplicate skill IDs fail closed unless scope/version is pinned.
- MCP tool handlers cover search, resolve, materialize, list, get, stage, and list-staged.
- Claude Code, Cowork, and Codex adapter outputs are generated in the expected shape.
- `meeting-followup` stays inside its defined scope and avoids Anthropic Productivity overlap.
- Staged skill proposals are immutable.
- Privacy invariant: no remote calls/uploads from personal skills or staged evidence in MVP.

## Assumptions

- Existing plugin/helper code and tests remain intact.
- Current plugin/helper documentation may be marked legacy/current-state where touched.
- `skills-ref` is optional later; MVP uses the internal validator.
- Remote company gateway, memory migration, public catalog downloads, and script execution are later phases.

# aiws-host-memory

`aiws-host-memory` is the host-side helper for the `ai-workspace` plugin family.

It owns:

- plugin install mapping/config
- `core-aiws` registry bootstrap
- automatic Claude global `SessionEnd` hook setup
- shared-memory refresh orchestration
- host-local consumer snapshot fan-out

It does not own:

- canonical shared-memory content
- producer-side candidate authoring
- plugin-local workflow behavior

## Install

```bash
pipx install "aiws-host-memory @ git+https://github.com/sashakang/ai-workspace.git@master#subdirectory=aiws-host-memory"
aiws-host-memory bootstrap
aiws-host-memory doctor
```

If you already have an older helper installed, reinstall it and rerun `aiws-host-memory bootstrap`. That migrates the managed hook from `Stop` to `SessionEnd`.

The helper requires only the infrastructure plugins:

- `core-aiws`
- `memory-aiws`

Domain plugins stay manual opt-in. When they are installed, the helper discovers them from the workspace marketplace metadata and includes them in the registry and shared-memory import flow automatically.

Claude Code remains the reference host. Cowork support is same-machine only in v1 and uses explicit refresh commands. Claude owns canonical shared memory. Cowork reads from and writes through that Claude-owned canonical store, but `refresh-cowork` rebuilds Cowork imports only.

## Commands

- `bootstrap` — discover or confirm infrastructure plugins, include any installed optional domain plugins, write helper config, populate the registry, bootstrap canonical memory, and upsert the managed `SessionEnd` hook
- `refresh-shared` — run the host-side shared-memory refresh
- `doctor` — report setup problems and repair guidance
- `status` — show current config and last refresh status
- `bootstrap-cowork` — bind a Cowork runtime to an already bootstrapped Claude canonical memory store, populate the Cowork registry, and build Cowork imports
- `refresh-cowork` — read Cowork outboxes, consolidate into the Claude-owned canonical store, and rebuild Cowork imports only
- `doctor-cowork` — validate Cowork config and the stored Claude canonical root
- `status-cowork` — show Cowork config and last Cowork refresh state

## Cowork v1

Cowork uses these runtime roots by default:

- helper config: `~/.cowork/aiws-host-memory/config.json`
- helper state: `~/.cowork/aiws-host-memory/state.json`
- installed plugins: `~/.cowork/plugins/installed_plugins.json`
- plugin data: `~/.cowork/plugins/data/<plugin-id>/`

Cowork bootstrap requires a bootstrapped Claude `memory-aiws` install. If Claude lives outside the default `~/.claude`, point the helper at it explicitly:

```bash
aiws-host-memory --claude-home /path/to/.claude bootstrap-cowork
```

Cross-host visibility is eventual, not immediate:

- Claude writes become visible in Cowork after `refresh-cowork`
- Cowork writes become visible in Claude after Claude’s normal `refresh-shared` path runs

## Optional plugin overrides

For local development or non-standard installs, both `bootstrap` and `bootstrap-cowork` accept explicit plugin mappings:

```bash
aiws-host-memory bootstrap \
  --plugin-root lawyer-aiws=/path/to/lawyer-aiws \
  --plugin-data lawyer-aiws=/path/to/plugin-data/lawyer-aiws-ai-workspace
```

For Cowork, the same flags apply, and `--memory-plugin-root` / `--memory-plugin-data` can be used to point Cowork at a non-standard Claude `memory-aiws` install when install metadata is not enough.

The legacy `--data-analysis-plugin-root` and `--data-analysis-plugin-data` flags still work for compatibility.

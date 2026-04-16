# aiws-host-memory

`aiws-host-memory` is the host-side helper for the `ai-workspace` Claude plugin family.

It owns:

- plugin install mapping/config
- `core-aiws` registry bootstrap
- automatic global `SessionEnd` hook setup
- shared-memory refresh orchestration
- consumer snapshot fan-out

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

## Commands

- `bootstrap` — discover or confirm infrastructure plugins, include any installed optional domain plugins, write helper config, populate the registry, bootstrap canonical memory, and upsert the managed `SessionEnd` hook
- `refresh-shared` — run the host-side shared-memory refresh
- `doctor` — report setup problems and repair guidance
- `status` — show current config and last refresh status

## Optional plugin overrides

For local development or non-standard installs, `bootstrap` also accepts explicit plugin mappings:

```bash
aiws-host-memory bootstrap \
  --plugin-root lawyer-aiws=/path/to/lawyer-aiws \
  --plugin-data lawyer-aiws=/path/to/plugin-data/lawyer-aiws-ai-workspace
```

The legacy `--data-analysis-plugin-root` and `--data-analysis-plugin-data` flags still work for compatibility.

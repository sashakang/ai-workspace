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

## Commands

- `bootstrap` — discover or confirm plugin installs, write helper config, populate the registry, bootstrap canonical memory, and upsert the managed `SessionEnd` hook
- `refresh-shared` — run the host-side shared-memory refresh
- `doctor` — report setup problems and repair guidance
- `status` — show current config and last refresh status

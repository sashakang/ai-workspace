# Shared Memory Export Snapshot Contract

`memory-aiws` owns the canonical shared-memory store and export format, but dependent plugins consume imported local snapshots and do not execute refresh themselves.

## Canonical owner

`memory-aiws`

## Export purpose

The export snapshot provides a stable, versioned representation of shared memory for other plugins to import into their own `${CLAUDE_PLUGIN_DATA}` runtime area.

## V1 runtime surfaces

```text
${memory_sk_plugin_data}/
├── store/
│   ├── entries.json
│   └── events.jsonl
├── state/
│   ├── refresh.lock
│   └── processed-candidate-ids.jsonl
├── memory/
│   ├── MEMORY.md
│   ├── global/
│   │   ├── user-preferences.md
│   │   ├── tool-quirks.md
│   │   ├── workflow-patterns.md
│   │   └── prompt-improvement-patterns.md
│   └── domains/
│       └── data-analyst/
└── exports/
    └── latest/
        ├── entries.json
        └── rendered/
```

The repo `memory/` tree remains the taxonomy seed and rendered-format template, not the live machine store.

## Export metadata

V1 export metadata should capture at least:

- snapshot version
- generated timestamp
- source plugin id
- included paths
- committed candidate ids or their equivalent dedupe fence

## Consumer rule

Dependent plugins must read only their imported snapshot, not the live `memory-aiws` plugin root.

## Refresh rule

Snapshot publication is executed by the host-side shared-memory bridge using the `memory-aiws` consolidator/exporter. It must publish via temp generation plus atomic swap.

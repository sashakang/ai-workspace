# Plugin Registry Contract

`core-aiws` uses a local plugin registry to reason about installed plugins without ad hoc sibling-plugin filesystem inspection.

## Runtime location

```text
${CLAUDE_PLUGIN_DATA}/registry/plugins/
```

Expected file pattern:

```text
${CLAUDE_PLUGIN_DATA}/registry/plugins/<plugin_id>.json
```

Each file must conform to [`plugin-contract.schema.json`](./plugin-contract.schema.json).

## Purpose

The registry is the discovery surface for:

- shared `/aiws-improve`
- shared process tooling
- future host-side validation and bootstrap helpers

It allows `core-aiws` to answer:

- which plugins are installed
- which public skills and agents they expose
- what memory surfaces they read and write
- which files are valid `/aiws-improve` targets

## Population model

V1 assumption:

- a host-side bootstrap or refresh step copies each installed plugin contract into the registry path
- `core-aiws` reads the local registry snapshot at runtime
- `core-aiws` does not discover sibling plugins by walking arbitrary plugin roots

## Naming rules

- one contract file per plugin
- filename should match `plugin_id`, for example `data-analysis-aiws.json`
- the contract payload remains authoritative; filename is only a convenience

## Minimum v1 behavior

For v1, `core-aiws` may assume:

- missing registry entries mean the plugin is not available for `/aiws-improve` targeting
- stale registry entries are a bootstrap or refresh problem, not a runtime inference problem
- registry reads are local-only and read-only

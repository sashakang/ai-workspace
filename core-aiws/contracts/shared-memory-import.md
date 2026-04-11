# Shared Memory Import Contract

Shared cross-plugin memory is owned by `memory-aiws`, but dependent plugins should read a local imported snapshot rather than the `memory-aiws` runtime root directly.

## Canonical shared-memory owner

`memory-aiws`

## Canonical shared-memory store

Canonical durable shared memory lives under:

```text
${memory_sk_plugin_data}/shared-memory/
```

`${memory_sk_plugin_data}` means `${CLAUDE_PLUGIN_DATA}` resolved for `memory-aiws`.

## Runtime import surface

Each dependent plugin reads its imported snapshot from:

```text
${CLAUDE_PLUGIN_DATA}/shared-memory/
```

In a dependent plugin, this path is a local imported snapshot, not the canonical shared-memory store.

## Why this import exists

- avoids direct sibling-plugin runtime reads
- keeps plugin contracts explicit
- makes refresh behavior and versioning visible

## V1 export model

`memory-aiws` publishes:

- a versioned shared-memory snapshot
- metadata describing snapshot version and generation time

Dependent plugins consume only the imported local snapshot.

## V1 read contract

- runtime reads happen only against `${CLAUDE_PLUGIN_DATA}/shared-memory/`
- missing or stale snapshots are a bootstrap or refresh problem
- plugins must not infer availability by reading the live `memory-aiws` root directly

## V1 write contract

- dependent plugins do not write directly into the canonical store or the imported snapshot
- reusable shared-memory candidates are staged locally in immutable outbox files first
- canonical consolidation and snapshot publication are owned by `memory-aiws` and executed by the host-side shared-memory bridge

## Producer staging surface

Producer plugins stage reusable candidates under:

```text
${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/
```

One file represents one candidate event.

"Staging" means:

- write the candidate locally in the producer plugin
- do not mutate canonical shared memory directly
- let the host-side bridge consolidate the candidate into `memory-aiws` later

Producers must not wait for shared-memory refresh on the critical path.

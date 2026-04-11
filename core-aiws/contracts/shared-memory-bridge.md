# Shared Memory Bridge Contract

Shared cross-plugin memory is owned by `memory-aiws`, but refresh and import are executed by a host-side bridge rather than by the plugin package itself.

## Purpose

The bridge exists to:

- run automatic post-response shared-memory refresh
- invoke the `memory-aiws` consolidator/exporter
- regenerate consumer-local imported snapshots
- keep runtime reads isolated from sibling plugin roots

## Normal trigger

V1 normal trigger:

- one host-side post-response hook

This hook is the routine refresh path for shared memory.

## Recovery trigger

If producer outbox files exist when the bridge starts, run one replay refresh before marking the bridge ready.

## Canonical store

The bridge consolidates shared memory into:

```text
${memory_sk_plugin_data}/shared-memory/
```

`${memory_sk_plugin_data}` means `${CLAUDE_PLUGIN_DATA}` resolved for `memory-aiws`.

## Producer surface

Each producer plugin stages reusable candidates under:

```text
${CLAUDE_PLUGIN_DATA}/shared-memory/outbox/
```

Each file is immutable and contains exactly one candidate event.

Staging means the producer records a proposed shared-memory item locally and leaves canonical consolidation to the bridge.

## Consumer surface

Each consumer plugin reads only its imported local snapshot:

```text
${CLAUDE_PLUGIN_DATA}/shared-memory/
```

For consumer plugins, this path is not the canonical store. It is a bridge-managed imported snapshot.

## Locking and fencing

The bridge owns a fenced lease lock under the `memory-aiws` runtime area:

```text
${memory_sk_plugin_data}/state/refresh.lock
```

The lock record must include at least:

- `owner_id`
- `lease_generation`
- `acquired_ts`
- `last_heartbeat_ts`

Rules:

- the refresher must verify the current `lease_generation` before every mutating phase
- a stale lease may be stolen only by incrementing `lease_generation`
- a refresher that loses lease ownership must abort without commit

## Idempotent refresh

To keep replay safe, the bridge must maintain a processed-candidate ledger in the `memory-aiws` runtime area and skip already-committed candidate ids on replay.

Minimum guarantees:

- canonical store and exports are generated in temp locations first
- active exports and consumer imports are swapped atomically
- processed candidate ids are committed atomically with the snapshot publish
- outbox cleanup happens only after successful commit
- a crash after publish but before cleanup must not duplicate memory on replay

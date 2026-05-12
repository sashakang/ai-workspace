# AIWS Cowork Laptop Test Safety

Use this before testing a fresh Cowork marketplace install on a laptop that already has operational Claude Code memory.

The goal is to prove the Cowork install path without damaging Claude Code memory, breaking the existing Claude Code setup, or confusing the test with stale Cowork install state.

## Safety Rules

- Do not delete, rename, overwrite, or repair `~/.claude`.
- Do not delete or modify Claude project memory, Claude session history, Claude plugin data, or `memory-aiws` canonical memory.
- Do not run `aiws-host-memory bootstrap`, `refresh-shared`, `bootstrap-cowork`, or `refresh-cowork` as part of Phase 1 fresh marketplace install testing.
- Do not clean memory paths while testing the marketplace install.
- Treat Cowork cleanup as reversible: move old Cowork/AIWS test state into a timestamped backup folder instead of deleting it.

Phase 1 is only the fresh Cowork marketplace install. Memory sync testing is a later phase.

## Preflight Snapshot

Before changing anything, record the state:

```bash
date
test -d ~/.claude && echo "Claude home exists"
test -d ~/.claude/projects && echo "Claude project memory exists"
test -d ~/.cowork && echo "Cowork home exists"
test -d ~/.aiws && echo "AIWS runtime exists"
```

If Claude Code is open, leave it operational. Do not change Claude Code settings or plugin state for this Cowork install test.

## Backup Existing Test State

Create a timestamped backup folder:

```bash
backup_root="$HOME/aiws-cowork-test-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_root"
```

If previous Cowork state exists, move it aside:

```bash
test -d ~/.cowork && mv ~/.cowork "$backup_root/cowork"
```

If previous AIWS test/runtime state exists and you are not using it for other active work, move it aside:

```bash
test -d ~/.aiws && mv ~/.aiws "$backup_root/aiws"
```

Do not move `~/.claude`.

If you are unsure whether `~/.aiws` contains active work, do not move it. Record that the test is not fully clean and continue only if that is acceptable.

## Fresh Cowork Test

After the backup step, install or open Cowork and run the Phase 1 checklist:

- [AIWS Cowork Runtime Validation Checklist](./aiws-cowork-runtime-validation-checklist.md)

The test passes only if Cowork can add the AIWS marketplace and install `core-aiws` plus `aiws-productivity` through Cowork's own marketplace flow without manual file copying, symlinks, repo cloning, or direct edits to `~/.cowork`.

## Restore Path

If you need to restore the previous Cowork or AIWS state, close Cowork first, then move the backup back:

```bash
mv "$backup_root/cowork" ~/.cowork
mv "$backup_root/aiws" ~/.aiws
```

Only run a restore command for a backup path that exists. Do not restore over newly created state until you have either moved the new state aside or confirmed you no longer need it.

Claude Code memory should not need restoration because this protocol never moves or edits `~/.claude`.

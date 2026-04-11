# Project Memory Bridge Contract

Claude-native project memory is canonical, but plugins should not depend on its live filesystem path directly at runtime.

## Canonical project memory surface

```text
~/.claude/projects/<project>/memory/
```

Claude Auto memory and Autodream operate on that native surface.

## Runtime import surface

Plugins consume an imported local snapshot:

```text
${CLAUDE_PLUGIN_DATA}/project-memory/current/
```

Typical imported contents:

- `MEMORY.md`
- recent daily logs such as `YYYY-MM-DD.md`
- relevant topic files

## Why this bridge exists

- keeps plugin runtime behavior independent from Claude internal project path details
- makes testing and bootstrap more explicit
- gives one place to stage approved durable writes before write-back

## V1 read contract

- plugins read project memory only from `${CLAUDE_PLUGIN_DATA}/project-memory/current/`
- plugins must not assume Autodream scans plugin-local copies
- imported snapshots are read-only from the plugin's point of view unless an explicit write-back step is running

## V1 write-back contract

Plugins may prepare durable project-memory writes only through an explicit staged-write flow.

Recommended local staging surface:

```text
${CLAUDE_PLUGIN_DATA}/project-memory/staged-writes/
```

Recommended staged artifacts:

- proposed daily-log append
- proposed topic-file creation or update
- proposed `MEMORY.md` update

V1 rule:

- staging is plugin-local
- write-back to native project memory happens only through a host-side bridge or approved bootstrap helper
- Autodream continues to operate on the native project-memory surface after write-back

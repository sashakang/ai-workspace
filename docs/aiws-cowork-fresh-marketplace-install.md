# AIWS Cowork GitHub Marketplace Install

This guide covers the primary Cowork marketplace path for installing AIWS from a fresh Cowork setup.

For architecture and project scope, see [AIWS Skills-Only Cowork Marketplace Architecture](./aiws-skills-cowork-marketplace.md) and [AIWS Project Development Plan](./aiws-project-development-plan.md).

Current status: the Personal marketplace path is now the primary journey. The user reported that Cowork installed the marketplace plugins and generated `meeting-followup` nodes correctly. The older Team ZIP import path remains a fallback and diagnostic path; see [AIWS Cowork Plugin Import Install](./aiws-cowork-plugin-import-install.md) and [AIWS Cowork Plugin Import Validation PASS](./aiws-cowork-plugin-import-validation-pass.md).

Phase 2 proceeds from marketplace-installed Cowork plugins by default. Use manual ZIP import only when marketplace access is unavailable or when explicitly testing the fallback path.

If you are testing on a laptop with existing Claude Code memory, complete [AIWS Cowork Laptop Test Safety](./aiws-cowork-laptop-test-safety.md) first. The Cowork install test must not delete, move, refresh, or repair Claude Code memory.

## What You Install

Install these from the AIWS marketplace:

- `core-aiws`, the core AIWS plugin.
- One domain plugin. For the Phase 1 starter path, use `aiws-productivity`.

The proof that the install worked is simple: Cowork should show the starter skill `meeting-followup`, supplied by `aiws-productivity`.

## Personal Marketplace Path

Use this path when you are installing AIWS for your own Cowork account.

1. Open Cowork.
2. Go to the Personal plugin marketplace area.
3. Add the AIWS marketplace from GitHub:

```text
sashakang/ai-workspace
```

4. Install `core-aiws`.
5. Install one domain plugin, starting with `aiws-productivity`.
6. Open the Cowork skill or plugin surface and confirm that `meeting-followup` is visible.
7. Invoke `meeting-followup` with a harmless test prompt and confirm that Cowork generates the expected nodes.

The exact current Cowork labels and menu path should still be recorded for each validation run because Cowork UI text may vary by account type or build.

## Team Or Enterprise Path

Use this path when an organization manages plugins for a team.

1. Ask the Cowork organization owner or admin to connect the AIWS marketplace repo through the organization-managed plugin settings.
2. Have the admin make `core-aiws` available to the relevant users.
3. Have the admin make one domain plugin available, starting with `aiws-productivity`.
4. In Cowork, install or enable the available plugins if your organization requires a user-level install step.
5. Confirm that `meeting-followup` is visible in your Cowork skill or plugin surface.

Fallback Team import path: `Organization settings -> Plugins -> Add plugin -> Upload a file` accepts individual plugin ZIPs with `.claude-plugin/plugin.json` at archive root. Use this path only when marketplace install is unavailable or when explicitly validating the fallback.

## Runtime Evidence To Collect

Collect this from a fresh Cowork install before marking Phase 1 complete:

- The Cowork marketplace add UI label and exact menu or settings path.
- Whether Cowork accepts the current root-level marketplace sources such as `./core-aiws` and `./aiws-productivity`, or requires a `plugins/<plugin-id>` layout.
- The installed plugin IDs after installing `core-aiws` and `aiws-productivity`.
- The visible Cowork skill IDs after install, including `meeting-followup`.
- Direct proof that `meeting-followup` can be invoked in Cowork.
- A sanitized `installed_plugins.json` if Cowork exposes one.
- Runtime logs or errors from the marketplace add, plugin install, skill visibility check, and `meeting-followup` invocation.

## Phase 1 Scope

Phase 1 includes only:

- Adding or installing the AIWS marketplace through Cowork's marketplace path.
- Installing `core-aiws`.
- Installing one domain plugin, starting with `aiws-productivity`.
- Verifying that `meeting-followup` is visible in Cowork.

Phase 1 does not include:

- Local MCP setup or control-plane behavior.
- Memory sync.
- Skill draft editing or modified local skill activation.
- GitHub submission or pull request workflows.
- Direct writes to `~/.cowork`.
- Cloning repositories.
- Creating symlinks.
- Manual file copying.

If a step requires cloning, copying files, symlinking, or editing Cowork local files directly, it is not the Phase 1 non-dev install path.

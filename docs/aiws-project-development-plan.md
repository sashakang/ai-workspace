# AIWS Project Development Plan

Updated: 2026-05-12

## Product Direction

AI Workspace is a local-first system for managing reusable AI skills across hosts. The product goal is to make skills discoverable, installable, editable, validated, and promotable without tying the workflow to one AI provider or one host application.

The primary host goal is Cowork. Claude Code may be used as an intermediate implementation target when it reduces delivery risk for Cowork, especially where Claude Code already provides working plugin, memory, or marketplace behavior that can be adapted. Codex remains an important development and validation host, but it is not the primary product target for the next cycle.

The first user journey to optimize is a clean Cowork-supported install of AIWS skills. The intended GitHub marketplace registration path is still the target product path, but it is currently blocked in Cowork build 1.6608.2 for the tested Personal account. The working path today is the Cowork Team import flow: `Organization settings -> Plugins -> Add plugin -> Upload a file`. That flow accepted individual ZIPs for `core-aiws` and `aiws-productivity`; `meeting-followup` was visible and invocable. Skill creation, editing, promotion, and richer team workflows now build on top of this proven Cowork-supported import path while GitHub marketplace registration remains tracked separately as blocked.

Customer constraints have loosened around GitHub use, but the user experience should still stay Cowork-first. Normal users should stage and submit skill improvements through friendly Cowork UI actions. GitHub is the backend review and source-control system: repo maintainers and skill maintainers review, comment on, and merge pull requests in GitHub. Branches, commits, remotes, and tokens should remain backend details unless the user explicitly asks for them.

There is an urgent current-user need from a group of Cowork users who need practical skills management now. The plan should therefore treat Team ZIP import as the first usable install gate, then immediately deliver a narrow Cowork skills-management MVP before broader memory sync or MCP alignment work. GitHub marketplace registration should not block Phase 2.

Memory sync across hosts is a required infrastructure capability. It should be implemented as one shared infrastructure layer, not as separate memory systems per host. Hosts may expose different adapters or local surfaces, but AIWS should preserve one coherent memory model.

## Product Boundaries

AIWS owns:

- skill discovery, validation, materialization, installation, and staged changes
- host adapter contracts for Cowork, Claude Code, and Codex
- shared memory contracts and host-to-host memory sync rules
- reusable process capabilities such as SOP and `aiws-improve`
- project documentation, acceptance criteria, and release readiness

AIWS does not own the Discord MCP implementation. Discord MCP is global infrastructure and should live outside this repository. This project may use Discord as the team communication medium, but the product should treat it as an external communication surface, similar to GitHub, Slack, or another host-provided connector.

## Architecture View

The current repository contains both the existing plugin/helper architecture and the newer MCP-first target architecture. The development plan should make that transition explicit rather than hiding it.

Current working surfaces:

- `core-aiws` provides shared SOP, protocols, and `aiws-improve`.
- `memory-aiws` defines shared-memory contracts and, in the current Claude/Cowork v1 bridge, owns the canonical shared-memory store under Claude plugin data.
- `aiws-host-memory` provides host-side bootstrap and refresh support for Claude Code and Cowork.
- Domain plugins such as `aiws-productivity`, `data-analysis-aiws`, and `software-engineer-aiws` provide skills and references.

Target control-plane surface:

- `aiws-mcp` becomes the local control plane for skill search, resolve, materialization, staged changes, host surfaces, and adapter output.
- `~/.aiws/` becomes the local runtime root for personal skills, host cache, staged writes, indexes, and host identity state.
- Host-specific installs and exports are adapter-owned operations, not direct writes from core skill logic.

Cowork-specific architecture is tracked in `docs/aiws-skills-cowork-marketplace.md`. Target-state local memory and host adapter architecture is tracked in `docs/aiws-target-architecture.md`.

### State Model

Use three explicit states when planning implementation:

- Current state: Cowork fresh install is marketplace/plugin based. Shared memory is bridge-managed, with Claude Code currently owning the canonical `memory-aiws` plugin-data store and Cowork using imported snapshots.
- Transitional state: Cowork can use Claude Code as a validation or implementation proving ground, but the product must keep memory semantics in `memory-aiws` contracts and host bridges rather than in Claude-specific assumptions.
- Target state: `~/.aiws/` is the local runtime root for personal memory, host caches, staged writes, indexes, locks, and host identity. Cowork, Claude Code, and Codex are adapters over the same AIWS runtime contract.

## Feature Development Plan

### Phase 1: Cowork Install Gate

Deliver the simplest credible Cowork user journey: start from a clean Cowork setup, install `core-aiws` plus one domain plugin through a Cowork-supported plugin install mechanism, and confirm that a starter skill is available in Cowork. The proven path is Team ZIP import through `Organization settings -> Plugins -> Add plugin -> Upload a file`. The GitHub marketplace registration path remains a target path but is currently blocked. Phase 1 does not include local MCP control-plane behavior, memory sync, direct writes to `~/.cowork`, GitHub submission, or managed draft lifecycle work.

The developer should validate the concrete Cowork marketplace artifact shape from `docs/aiws-skills-cowork-marketplace.md`. Current read-only repo validation found the marketplace manifest at:

```text
.claude-plugin/marketplace.json
```

That manifest currently points to root-level plugin source directories such as `./core-aiws` and `./aiws-productivity`. Do not treat the `plugins/<plugin-id>` layout below as the only proven current repo shape. It is an example, target, or alternate marketplace shape until direct Cowork runtime testing confirms which layout Cowork accepts:

```text
.claude-plugin/marketplace.json
plugins/
  aiws-productivity/
    .claude-plugin/plugin.json
    skills/
      meeting-followup/
        SKILL.md
```

`marketplace.json` must include `name`, `owner`, and `plugins`; each plugin entry must include `name`, `source`, `version`, and `description`; and each plugin must have a matching `.claude-plugin/plugin.json`. The Phase 1 validation gates are marketplace and plugin manifests, plugin contracts, skill folders using Codex `skill-creator` compatibility rules, and version alignment across marketplace entries, plugin manifests, and contracts. Skill folders must include `SKILL.md` with only `name` and `description` frontmatter, and the skill folder name must match the frontmatter `name`. MCP config validation is part of the later control-plane and release-readiness work, not the Cowork install gate.

Current status: the GitHub marketplace registration path is blocked in Cowork build 1.6608.2 for the tested Personal account. A Cowork-supported Team import path has runtime proof: `Organization settings -> Plugins -> Add plugin -> Upload a file` accepted individual ZIPs for `core-aiws` and `aiws-productivity`, and `meeting-followup` was visible and invocable. See `docs/aiws-phase1-blocked.md` and `docs/aiws-cowork-plugin-import-validation-pass.md`.

Expected developer evidence for the proven Team import path:

- the exact plugin ZIP artifacts used for validation
- the inspected plugin manifest paths used by those ZIPs
- the Cowork import UI label and exact menu or settings path used
- the archive layout Cowork accepts
- proof that Cowork imports the plugin packages through its supported UI
- the installed plugin IDs
- the visible Cowork skill IDs, including `core-aiws` and `aiws-productivity/meeting-followup`
- proof that `meeting-followup` can be invoked in Cowork
- a sanitized `installed_plugins.json` if Cowork exposes one
- runtime logs or errors from the Cowork import and skill invocation attempt
- validation command output or equivalent logs for manifests, contracts, skill folders, and version alignment
- a screenshot, copied Cowork surface text, or other direct proof that `meeting-followup` is visible and usable in Cowork

Acceptance criteria:

- From a clean Cowork setup, a user can install AIWS through a Cowork-supported path without manual runtime edits.
- A user can install `core-aiws` plus one domain plugin from that supported path.
- A starter skill, starting with `meeting-followup`, is visible and usable in Cowork after the install.
- The install path does not require manual file copying, symlinks, or repo cloning by a normal user.
- Duplicate skill identity behavior is clear and fails closed when scope is ambiguous.
- The flow is documented for a non-dev user.

Blocked path:

- GitHub marketplace registration through a Personal account is blocked in Cowork build 1.6608.2 because no functional `Add marketplace from GitHub` input was available. This is recorded in `docs/aiws-phase1-blocked.md` and must not be treated as a Phase 2 dependency.

### Phase 2: Urgent Cowork Skills-Management MVP

After the Cowork-supported install/import path is reliable, immediately deliver the smallest Cowork skills-management MVP that lets current users edit or open a draft, validate it, activate the modified local skill, stage a proposed improvement, and submit it for maintainer review from Cowork. This lifecycle work follows the installed Cowork plugin package directly; it does not depend on GitHub marketplace registration, memory sync, or the MCP control plane being complete.

For this urgent MVP, staging means calling the contract-owned `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)` operation to write a local proposal record with provenance, the concrete backend review repository, and review notes under `~/.aiws/state/skill-proposals/`. `target_scope` is the Cowork/user-facing destination label and policy scope; `target_repo` is the concrete repository used later by submit-for-review. Staging must not be silently treated as PR submission. Submission is a separate explicit Cowork UI action that may create or update a GitHub pull request behind the scenes. Normal users should see statuses such as `Draft`, `Modified locally`, `Ready to submit`, `Submitted for review`, `Changes requested`, and `Merged`, not raw git mechanics.

GitHub is now an acceptable collaboration backend for the customer experiment. The product boundary is still clear: Cowork owns the normal user workflow for staging and submitting; GitHub owns maintainer review, comments, approvals, and merges. Direct push is not part of the normal user flow. Pull requests are created by an explicit submit action and should target the appropriate unit, company, public, or personal skills repository based on the selected target scope.

Lifecycle behavior must preserve one user-facing skill identity. If a modified draft is active, Cowork should show the same skill with `Modified locally` status; the draft replaces the installed version in the UI/runtime, while the installed package remains available internally as fallback/cache. AIWS must not create a second visible skill with the same identity. Organization-managed plugins are read-only for members. User edits become personal drafts or proposals derived from the installed variant; AIWS must not mutate the managed plugin in place.

Editable draft files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>
```

The path matches `aiws-mcp/aiws_mcp/skill_manager.py`: marketplace and plugin values are slug-normalized, and `origin-repo-sha10` is `sha256(origin_repo)[:10]`. The suffix prevents origin repository collisions. It does not change the user-facing identity, which remains `plugin_id + skill_id`, and must not create duplicate visible skills.

The authoritative draft registry lives under:

```text
~/.aiws/state/skill-drafts/
```

When updating from GitHub and an active modified draft exists, AIWS fails closed and offers only:

```text
keep local modified skill active
discard local changes and update
submit/upload first
```

Acceptance criteria:

- A user can create or open a draft of an installed skill.
- AIWS validates the draft against skill compatibility rules.
- A modified local skill can be activated without becoming a confusing duplicate.
- The user can stage a proposed improvement through an explicit local proposal-record operation with provenance and review notes.
- The user can explicitly submit a staged proposal from Cowork for maintainer review without using GitHub UI directly.
- Repo maintainers and skill maintainers can review and merge the resulting proposal in GitHub.
- Duplicate skill identity fails closed when scope is ambiguous.
- Managed marketplace or organization plugin files are never mutated in place.

### Phase 3: Shared Memory Sync Foundation

Make memory sync a single shared infrastructure layer across hosts. For the current v1 bridge, Claude Code may own the canonical `memory-aiws` plugin-data store while Cowork reads imported snapshots and stages candidate writes through the bridge. Claude Code can be used as an intermediate validation host or implementation target if that helps delivery, but it must not define the product semantics. The target canonical layer remains `~/.aiws/`, `memory-aiws`, and the shared memory contract.

Current helper commands and visibility rules must be documented and tested as they exist today. Claude Code uses `aiws-host-memory bootstrap` and `aiws-host-memory refresh-shared`. Cowork v1 uses `aiws-host-memory bootstrap-cowork` to bind a Cowork runtime to an already bootstrapped Claude canonical memory store, and `aiws-host-memory refresh-cowork` to read Cowork outboxes, consolidate into the Claude-owned canonical store, and rebuild Cowork imports only.

Expected Cowork roots are:

```text
~/.cowork/aiws-host-memory/config.json
~/.cowork/aiws-host-memory/state.json
~/.cowork/plugins/installed_plugins.json
~/.cowork/plugins/data/<plugin-id>-ai-workspace/
```

Cross-host visibility is eventual. Claude writes become visible in Cowork after `refresh-cowork`. Cowork writes become visible in Claude after Claude's normal `refresh-shared` path runs. Cowork must not create a second canonical store.

Acceptance criteria:

- AIWS has one documented memory sync contract across Cowork, Claude Code, and Codex that distinguishes current bridge behavior, transitional behavior, and target `~/.aiws/` ownership.
- Host-specific adapters expose memory surfaces without inventing separate memory semantics.
- For the same-machine v1 path, a Cowork staged write can be consolidated through the existing bridge and later become visible through the documented refresh path.
- Broader remote, company, or gateway-backed sync is explicitly deferred until the later gateway/memory-sync implementation.
- Sync behavior is clear about what is immediate, eventual, local-only, or unsupported.

### Phase 4: MCP Control Plane Alignment

Align the Cowork install, skill lifecycle, and memory paths with `aiws-mcp` so AIWS has one control-plane direction after the supported Cowork install/import path and initial lifecycle constraints are proven. Managed lifecycle behavior, including materialization state, staged skill changes, host surfaces, and future draft flows, moves behind `aiws-mcp` or an equivalent host adapter. This phase must not retroactively make Phase 1 depend on local MCP.

The concrete control-plane boundary is the local Python stdio MCP server `aiws-mcp` described in `docs/aiws-local-mcp-skills-mvp-plan.md`. It owns these tool surfaces:

```text
aiws.skills.search
aiws.skills.resolve
aiws.skills.materialize
aiws.skills.list_local
aiws.skills.get
aiws.skills.stage_change
aiws.skills.list_staged_changes
aiws.host.surfaces
```

`aiws.skills.stage_change` is the legacy host-local staged-write surface and is not the Cowork skill proposal flow. Cowork-facing proposal staging uses `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)` from the `core-aiws` skill-management contract and writes under `~/.aiws/state/skill-proposals/`.

Host identity is the boundary between the shared AIWS runtime and each host. Each host persists `~/.aiws/hosts/<host-id>/host.json`; `host-kind` is `claude-code`, `cowork`, or `codex`; and if `--host-id` is omitted, the default identity is derived from `host-kind` plus the hash of the canonical resolved host config root. Later commands may use `--host-id` alone. Missing host registration, conflicting CLI values, or duplicate shared skill IDs without pinned scope/version must fail closed.

Materialization may write only under:

```text
~/.aiws/hosts/<host-id>/shared-cache/skills/<scope-id>/<skill-id>/<version>/
~/.aiws/hosts/<host-id>/adapter/
```

It must not write directly into `~/.claude`, `~/.cowork`, `~/.codex`, project repos, or host config files. The Cowork adapter output is:

```text
~/.aiws/hosts/<host-id>/adapter/aiws-generated-plugin/.claude-plugin/plugin.json
~/.aiws/hosts/<host-id>/adapter/aiws-generated-plugin/skills/<skill-id>/SKILL.md
```

Acceptance criteria:

- `aiws-mcp` exposes host surfaces needed by Cowork.
- The MCP runtime can represent installed, materialized, and staged skills consistently.
- The current plugin/helper path and MCP-first path are documented as current state, transitional state, or target state.
- Tests cover the Cowork-relevant skill lifecycle at the control-plane boundary.

### Phase 5: Release Readiness

Turn the alpha into a repeatable release process.

Acceptance criteria:

- The repo has a clear test command that does not silently run zero tests.
- Release validation includes plugin contracts, skill compatibility, MCP config checks, and host adapter expectations.
- Runtime/generated files are clearly excluded from source control.
- Install docs distinguish developer workflows from normal user workflows.

## Project Management Model

The product manager owns product direction, scope, prioritization, acceptance criteria, and handoff clarity. Implementation and testing should be delegated to the AIWS developer session, specialized sub-agents, or future human contributors. The PM should not take over developer responsibilities except for light repo inspection needed to write accurate plans and acceptance criteria.

AIWS review gates for this project must include an AI-engineering reviewer or explicit AI-engineering lens, especially for Cowork, MCP, memory, host adapter, skill lifecycle, or architecture changes.

Work should be managed through short, explicit assignments:

```text
Task: <short task>
Context: <why it matters>
Owner: <developer, tester, or agent>
Expected output: <patch, PR, test result, doc, or decision>
Acceptance: <how we know it is done>
Evidence: <tests, commands, screenshots, logs, or reviewed files>
```

Developer updates should use:

```text
Status: <blocked, in progress, ready for review, done>
Changed: <files or behavior>
Evidence: <tests, commands, screenshots, logs>
Needs PM: <decision or clarification, if any>
```

Publishing and handoff rule: when pushing this project to GitHub, use `athanasiosbot`. This is a project publishing rule, not a request to push as part of this plan.

## Discord Operating Model

Discord is the near real-time communication medium for the project, but Discord MCP itself is global infrastructure outside this repo.

Recommended project channels:

- `#aiws-product` for direction, scope, and tradeoff discussions
- `#aiws-dev` for developer assignments and implementation updates
- `#aiws-testing` for test runs, failures, reproduction notes, and acceptance checks
- `#aiws-decisions` for final decisions only
- `#aiws-release` for release readiness and packaging status

The Discord protocol should stay lightweight but structured. Task IDs and explicit statuses are useful, but the system should not become heavier than the project needs.

## Immediate Next Steps

Task: Lock the Cowork Team import path as the current install gate.
Context: GitHub marketplace registration is blocked, but Cowork Team ZIP import has passed with `core-aiws` and `aiws-productivity`. Phase 2 should build on the proven import path, not wait for marketplace registration.
Owner: Developer session
Expected output: User-facing import guide and validation record for installing `core-aiws` and `aiws-productivity` through `Organization settings -> Plugins -> Add plugin -> Upload a file`.
Acceptance: The guide names the exact artifacts, archive layout, Cowork UI path, expected plugin IDs/skills to verify, safety boundaries, and blocked GitHub marketplace-registration caveat. It excludes local MCP, memory sync, draft editing, GitHub submission, RPM edits, and old registration restore from the install flow.
Evidence: `docs/aiws-cowork-plugin-import-install.md`, `docs/aiws-cowork-plugin-import-validation-pass.md`, import artifact paths, Cowork runtime proof that `meeting-followup` was visible and invocable, and validation command output.

Task: Capture lifecycle constraints for modified skills.
Context: Phase 2 is an urgent Cowork skills-management MVP. Current users need to edit or open drafts, validate them, activate modified local skills, and stage proposals immediately after Cowork-supported plugin import, without waiting for GitHub marketplace registration, memory sync, or MCP control-plane alignment.
Owner: Developer session
Expected output: Product and technical notes for draft creation, validation, activation, update conflict handling, and proposal staging.
Acceptance: The notes preserve one user-facing skill identity, use `Modified locally` status, store draft registry entries under `~/.aiws/state/skill-drafts/`, store editable files under `~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>`, activate modified local skills without duplicate visible skill identity, stage proposals through `stage_proposal` under `~/.aiws/state/skill-proposals/` rather than silently invoking `submit_pr`, expose submission as a separate Cowork UI action, never mutate managed marketplace or organization plugin files, fail closed on updates when an active modified draft exists, and offer only the three approved update choices.
Evidence: Doc path, reviewed lifecycle state table or equivalent, and test cases or fixtures covering draft activation and update conflict handling.

Task: Move `discord-mcp-for-codex/` out of this repo.
Context: Discord MCP is global infrastructure, not part of the AIWS product repo. This remains necessary cleanup, but it comes after the urgent Cowork install and skills-management tasks.
Owner: Developer session
Expected output: Patch that removes the in-repo Discord MCP subtree from AIWS and documents or records its new global tooling location.
Acceptance: No AIWS docs or config still treat Discord MCP as repo-owned product code.
Evidence: Changed-file list, destination path, and `rg "discord-mcp-for-codex|Discord MCP"` results showing only intentional references remain.

Task: Define and test the current Cowork memory bridge contract.
Context: Phase 3 must keep one shared memory model while accurately describing the current helper-managed bridge.
Owner: Developer session
Expected output: Contract doc or patch covering `bootstrap`, `refresh-shared`, `bootstrap-cowork`, `refresh-cowork`, expected roots, staged writes, imports, and eventual visibility.
Acceptance: The contract states that Claude owns the v1 canonical `memory-aiws` store, Cowork reads imported snapshots under `~/.cowork/plugins/data/<plugin-id>-ai-workspace/`, Cowork does not create a second canonical store, `refresh-cowork` rebuilds Cowork imports only, and Cowork writes become visible to Claude after Claude's normal `refresh-shared` path.
Evidence: Helper command output, relevant test output, inspected `~/.cowork/aiws-host-memory/` paths, and before/after visibility notes for one staged Cowork write.

Task: Align the development plan with the `aiws-mcp` control-plane boundary.
Context: Phase 4 should prepare the target architecture without making Phase 1 depend on local MCP.
Owner: Developer session
Expected output: Implementation plan or patch referencing the concrete `aiws-mcp` tools, host identity rules, materialization paths, and Cowork adapter output from `docs/aiws-local-mcp-skills-mvp-plan.md`.
Acceptance: The plan names the MCP tools, including `aiws.host.surfaces`, `~/.aiws/hosts/<host-id>/host.json`, fail-closed host identity conflicts, allowed materialization roots, the Cowork `adapter/aiws-generated-plugin` output, and the rule against direct writes to host config roots.
Evidence: Reviewed files, test names or planned tests for search/resolve/materialize/stage/list-staged/host-surfaces, and sample generated Cowork adapter paths.

Task: Add a discoverable root-level test command.
Context: Release readiness needs a test entrypoint that does not silently run zero tests.
Owner: Developer session
Expected output: Root-level test command, config, or README update that tells developers exactly how to run the expected suite.
Acceptance: The command exercises current AIWS tests or fails clearly when dependencies are missing; it must not pass by discovering no tests.
Evidence: Command output from a clean run or a documented failure with missing dependency details.

Task: Mark current, transitional, and target architecture docs.
Context: Contributors need to know whether they are changing the plugin/helper bridge, the transitional Cowork path, or the MCP-first target.
Owner: Developer session
Expected output: Documentation patch that labels affected architecture sections consistently.
Acceptance: `docs/aiws-project-development-plan.md`, `docs/aiws-skills-cowork-marketplace.md`, `docs/aiws-local-mcp-skills-mvp-plan.md`, and target architecture references do not conflict about ownership, roots, or timing.
Evidence: Changed docs list and reviewed excerpts showing the current/transitional/target labels.

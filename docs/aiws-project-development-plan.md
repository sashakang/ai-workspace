# AIWS Project Development Plan

Updated: 2026-05-14

## Product Direction

AI Workspace is a local-first system for managing reusable AI skills across hosts. The product goal is to make skills discoverable, installable, editable, validated, and promotable without tying the workflow to one AI provider or one host application.

The primary host goal is Cowork. Claude Code may be used as an intermediate implementation target when it reduces delivery risk for Cowork, especially where Claude Code already provides working plugin, memory, or marketplace behavior that can be adapted. Codex remains an important development and validation host, but it is not the primary product target for the next cycle.

The first user journey to optimize is a clean Cowork-supported marketplace install of AIWS skills. The Personal marketplace path is now the primary product path: the 2026-05-14 canonical Cowork user test passed with marketplace `sashakang/ai-workspace`, installed plugin IDs `core-aiws@ai-workspace` and `aiws-productivity@ai-workspace`, visible skill `aiws-productivity:meeting-followup`, successful skill invocation, and user-driven Cowork UI updates that kept `meeting-followup` visible. See [Cowork Canonical User Test Report](./cowork-canonical-user-test-report-2026-05-14.md). Manual Cowork ZIP import remains a validated fallback path for Team accounts and recovery testing, but it is no longer the primary user journey.

Customer constraints have loosened around GitHub use, but the user experience should still stay Cowork-first. Normal users should stage and submit skill improvements through friendly Cowork UI actions. GitHub is the backend review and source-control system: repo maintainers and skill maintainers review, comment on, and merge pull requests in GitHub. Branches, commits, remotes, and tokens should remain backend details unless the user explicitly asks for them.

The target Cowork user path must not assume Python, `uvx`, GitHub CLI, or terminal fluency on the user's machine. A technical pilot may temporarily use a plugin-provided MCP launcher backed by `uvx`, but that is not the final end-user install model. Before AIWS is called end-user ready for Cowork, users must install through Cowork and operate through Cowork without separately installing Python, `uvx`, `gh`, or running shell commands.

The near-term private/non-public skills path is now a maintainer/operator workflow in Claude Code, not MCP running inside Claude Code and not a hosted remote MCP surface that can see private skills. Claude Code should be used as a "skill workshop" for maintainers: update skill source, validate contracts, build Cowork packages, push to GitHub as the maintainer or bot, and prepare or upload marketplace artifacts on demand. This is a practical bridge while the Cowork edit UX and runtime/security model are still being cleaned up.

Hosted FastMCP or official MCP Python SDK connector work remains useful, but it is parked as a secondary/future proof. It must stay harmless until auth, permissions, and tenancy are designed. A hosted remote MCP service must not expose private skills, memory, drafts, proposal records, or source content.

There is an urgent current-user need from a group of Cowork users who need practical skills management now. The plan should therefore treat marketplace install as the first usable install gate, then immediately deliver a narrow Cowork skills-management MVP before broader memory sync or MCP alignment work. Manual ZIP import stays available as a fallback when marketplace access, permissions, or service behavior blocks a tester.

Memory sync across hosts is a required infrastructure capability. It should be implemented as one shared infrastructure layer, not as separate memory systems per host. Hosts may expose different adapters or local surfaces, but AIWS should preserve one coherent memory model.

## Product Boundaries

AIWS owns:

- skill discovery, validation, materialization, installation, and staged changes
- host adapter contracts for Cowork, Claude Code, and Codex
- shared memory contracts and host-to-host memory sync rules
- reusable process capabilities such as SOP and `aiws-improve`
- project documentation, acceptance criteria, and release readiness

Cowork owns normal-user plugin install, update, and activation for Cowork. AIWS may validate source, stage changes, prepare proposal records, materialize to AIWS-owned cache or adapter roots, and build package artifacts, but it must not directly mutate Cowork installed plugin folders or RPM/runtime state. The canonical Cowork user path must not require repo cloning, terminal commands, manual runtime edits, direct writes under `~/.cowork/plugins`, or `~/.claude` edits.

AIWS does not own the Discord MCP implementation. Discord MCP is global infrastructure and should live outside this repository. This project may use Discord as the team communication medium, but the product should treat it as an external communication surface, similar to GitHub, Slack, or another host-provided connector.

## Architecture View

The current repository contains both the existing plugin/helper architecture and the newer MCP-first target architecture. The development plan should make that transition explicit rather than hiding it.

Current working surfaces:

- `core-aiws` provides shared SOP, protocols, and `aiws-improve`.
- `memory-aiws` defines shared-memory contracts and, in the current Claude/Cowork v1 bridge, owns the canonical shared-memory store under Claude plugin data.
- `aiws-host-memory` provides host-side bootstrap and refresh support for Claude Code and Cowork.
- Domain plugins such as `aiws-productivity`, `data-analysis-aiws`, and `software-engineer-aiws` provide skills and references.

Target control-plane surface:

- `aiws-mcp` becomes the AIWS control plane for skill search, resolve, materialization, staged changes, host surfaces, and adapter output.
- For the near term, maintainers use Claude Code as a skill workshop rather than running MCP inside Claude Code for private skill operations.
- The hosted FastMCP or official MCP Python SDK deployment is a secondary/future connector proof registered through Cowork's supported managed/custom connector path. This is a separate deployable runtime surface from Cowork marketplace/upload plugins, and it must expose only harmless public proof tools until auth, permissions, and tenancy exist.
- Cowork marketplace and upload plugins remain the skills distribution and user-facing UX surface. They should not be treated as the production control-plane runtime unless Cowork documents and proves a supported local runtime path.
- `~/.aiws/` becomes the local runtime root for personal skills, host cache, staged writes, indexes, and host identity state.
- Host-specific installs and exports are adapter-owned operations, not direct writes from core skill logic.

Cowork-specific architecture is tracked in `docs/aiws-skills-cowork-marketplace.md`. Target-state local memory and host adapter architecture is tracked in `docs/aiws-target-architecture.md`.

### State Model

Use three explicit states when planning implementation:

- Current state: Cowork fresh install is marketplace/plugin based. Shared memory is bridge-managed, with Claude Code currently owning the canonical `memory-aiws` plugin-data store and Cowork using imported snapshots.
- Transitional state: maintainers can use Claude Code as a skill workshop for private or non-public skill source changes, validation, package builds, GitHub pushes, and marketplace artifact preparation. This is not the normal Cowork user path, and it must not make Claude-specific assumptions part of the product contract.
- Target state: `~/.aiws/` is the local runtime root for personal memory, host caches, staged writes, indexes, locks, and host identity. Cowork, Claude Code, and Codex are adapters over the same AIWS runtime contract.

## Feature Development Plan

### Phase 1: Cowork Install Gate

Deliver the simplest credible Cowork user journey: start from a clean Cowork setup, add the AIWS marketplace, install `core-aiws` plus one domain plugin through Cowork's marketplace/plugin UI, and confirm that a starter skill is available in Cowork. The primary path is Personal marketplace install from `sashakang/ai-workspace`, followed by installing `core-aiws` and `aiws-productivity`. Manual ZIP import through `Organization settings -> Plugins -> Add plugin -> Upload a file` remains a fallback path. Phase 1 does not include local MCP control-plane behavior, memory sync, direct writes to `~/.cowork`, GitHub submission, or managed draft lifecycle work.

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

Current status: the Personal marketplace path has canonical user-test runtime proof: Cowork installed the AIWS marketplace `sashakang/ai-workspace`, installed `core-aiws@ai-workspace` and `aiws-productivity@ai-workspace`, exposed `aiws-productivity:meeting-followup`, invoked it successfully, and kept it visible after user-driven Cowork UI updates. Cowork did not expose plugin-level versions through `list_plugins`; one skill-level signal showed `aiws-improve` as `v1.0.0`. The canonical install/use invocation found a non-blocking `meeting-followup` date normalization issue: on Thursday, May 14, 2026, "Friday" should have resolved to May 15, 2026, but the output used 2026-05-16. A later regular-user draft/submit test did resolve Friday as May 15, 2026, so the earlier date bug did not recur in that scenario. A Cowork-supported Team import fallback also has runtime proof: `Organization settings -> Plugins -> Add plugin -> Upload a file` accepted individual ZIPs for `core-aiws` and `aiws-productivity`, and `meeting-followup` was visible and invocable. See [Cowork Canonical User Test Report](./cowork-canonical-user-test-report-2026-05-14.md), [Cowork Regular User Draft Submit Report](./cowork-regular-user-draft-submit-report-2026-05-14.md), [AIWS Cowork GitHub Marketplace Install](./aiws-cowork-fresh-marketplace-install.md), [AIWS Cowork GitHub Marketplace Runtime Validation Checklist](./aiws-cowork-runtime-validation-checklist.md), and [AIWS Cowork Plugin Import Validation PASS](./aiws-cowork-plugin-import-validation-pass.md).

Expected developer evidence for the primary marketplace path:

- the exact marketplace repo/path submitted to Cowork
- the Cowork marketplace UI label and exact menu or settings path used
- proof that Cowork adds the marketplace through its supported UI
- the accepted marketplace source layout
- proof that Cowork installs `core-aiws` and `aiws-productivity` from the marketplace
- the installed plugin IDs
- the visible Cowork skill IDs, including `core-aiws` and `aiws-productivity/meeting-followup`
- proof that `meeting-followup` can be invoked in Cowork
- a sanitized `installed_plugins.json` if Cowork exposes one
- runtime logs or errors from marketplace add, plugin install, skill discovery, and skill invocation
- validation command output or equivalent logs for manifests, contracts, skill folders, and version alignment
- a screenshot, copied Cowork surface text, or other direct proof that `meeting-followup` is visible and usable in Cowork

Acceptance criteria:

- From a clean Cowork setup, a user can add the AIWS marketplace and install AIWS without manual runtime edits.
- A user can install `core-aiws` plus one domain plugin from that marketplace path.
- A starter skill, starting with `meeting-followup`, is visible and usable in Cowork after the install.
- The install and update path does not require manual file copying, symlinks, repo cloning, terminal commands, manual RPM/runtime edits, direct `~/.cowork/plugins` writes, or `~/.claude` edits by a normal user.
- Duplicate skill identity behavior is clear and fails closed when scope is ambiguous.
- The flow is documented for a non-dev user.

Fallback path:

- Manual Cowork ZIP import is kept as a fallback and diagnostic path. It is documented in `docs/cowork-clean-import-test-plan.md` and `docs/aiws-cowork-plugin-import-install.md`. It should not replace marketplace install as the primary journey unless marketplace access is blocked for a tester.

### Phase 2: Urgent Cowork Skills-Management MVP

After the Cowork marketplace install path is reliable, immediately deliver the smallest Cowork skills-management MVP that lets current users edit or open a draft, validate it, prepare a modified draft package for Cowork upload, stage a proposed improvement, and submit it for maintainer review from Cowork. This lifecycle work follows the installed Cowork plugin package directly; it does not depend on memory sync or the MCP control plane being complete.

Phase 2 has three runtime levels:

- **Phase 2A technical pilot bridge:** acceptable for AIWS maintainers and technical testers. The current `core-aiws` MCP bridge may use `uvx` to start `aiws-mcp`, and GitHub submission may depend on local authenticated tooling while the lifecycle behavior is being proven. This validates draft/edit/stage/submit semantics, but it is not the target user experience.
- **Claude Code skill workshop:** the preferred near-term maintainer path for private and non-public skills. It should use Claude Code's normal skills, workflows, and commands to edit skill source, validate contracts, run tests, build Cowork packages, push with maintainer or bot credentials, and prepare/upload marketplace artifacts. It should not run AIWS MCP inside Claude Code for this workflow.
- **Phase 2B end-user Cowork path:** required before broader customer rollout. A normal Cowork user must not install Python, install `uvx`, configure `gh`, run terminal commands, or understand the MCP server runtime. Cowork remains the user-facing surface for installing and using skills. Cowork edit UX remains the product target, but it is deferred until the runtime and security model are clean enough to avoid leaking or overwriting private work.

For this urgent MVP, staging means calling the contract-owned `stage_proposal(draft_id, target_scope, target_repo, summary, rationale)` operation to write a local proposal record with provenance, the concrete backend review repository, and review notes under `~/.aiws/state/skill-proposals/`. `target_scope` is the Cowork/user-facing destination label and policy scope; `target_repo` is the concrete repository used later by submit-for-review. Staging must not be silently treated as PR submission. Submission is a separate explicit Cowork UI action that may create or update a GitHub pull request behind the scenes. Normal users should see statuses such as `Draft`, `Modified locally`, `Ready to submit`, `Submitted for review`, `Changes requested`, and `Merged`, not raw git mechanics.

GitHub is now an acceptable collaboration backend for the customer experiment. The product boundary is still clear: Cowork owns the normal user workflow for staging and submitting; GitHub owns maintainer review, comments, approvals, and merges. Direct push is not part of the normal user flow. Pull requests are created by an explicit submit action and should target the appropriate unit, company, public, or personal skills repository based on the selected target scope.

Lifecycle behavior must preserve one user-facing skill identity. In the current Cowork-safe slice, AIWS does not replace the installed version in Cowork UI/runtime and does not change runtime skill resolution. A modified draft can be validated and packaged, then marked `Modified locally, pending Cowork upload` until the user uploads the package through Cowork. Future true runtime overlay or direct activation behavior requires a supported Cowork activation surface and a separate design pass. Organization-managed plugins are read-only for members. User edits become personal drafts or proposals derived from the installed variant; AIWS must not mutate the managed plugin in place.

Editable draft files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>
```

The path matches `aiws-mcp/aiws_mcp/skill_manager.py`: marketplace and plugin values are slug-normalized, and `origin-repo-sha10` is `sha256(origin_repo)[:10]`. The suffix prevents origin repository collisions. It does not change the user-facing identity, which remains `plugin_id + skill_id`, and must not create duplicate visible skills.

The authoritative draft registry lives under:

```text
~/.aiws/state/skill-drafts/
```

When updating from GitHub and either a modified draft or pending Cowork upload exists, AIWS fails closed and offers only:

```text
keep local draft and pending package
discard local changes and update
submit/upload first
```

Acceptance criteria:

- A user can create or open a draft of an installed skill.
- AIWS validates the draft against skill compatibility rules.
- A modified local skill can be packaged for Cowork upload without becoming a confusing duplicate or changing runtime resolution.
- The user can stage a proposed improvement through an explicit local proposal-record operation with provenance and review notes.
- The user can explicitly submit a staged proposal from Cowork for maintainer review without using GitHub UI or GitHub CLI directly.
- Repo maintainers and skill maintainers can review and merge the resulting proposal in GitHub.
- Maintainers can use the Claude Code skill workshop to update private/non-public skill source, validate it, package it for Cowork, push it to GitHub, and prepare/upload marketplace artifacts without exposing private content to a hosted remote MCP service.
- Duplicate skill identity fails closed when scope is ambiguous.
- Managed marketplace or organization plugin files are never mutated in place.
- Phase 2A is accepted only as a technical pilot if it still requires `uvx`, Python-managed execution, or local GitHub CLI.
- Phase 2B is accepted only when normal users can install skills and access AIWS draft/edit/validate/stage/submit through Cowork without Python, `uvx`, `gh`, shell commands, or manual MCP setup.

Current status: the Cowork skill-management bridge is a validated Phase 2A technical pilot after `core-aiws` version `0.3.7` bundled the AIWS MCP bridge source, added the Scenario D draft-record safety fix, and made submit-for-review return a safe handoff when `gh` is unavailable. Runtime testing on 2026-05-14 passed the full A-H lifecycle, including PR creation through authenticated host `gh` and maintainer merge in `sashakang/aiws-skill-tests` PR #1.

The regular Cowork user draft/edit/validate/stage/submit path is also proven end to end for `aiws-productivity:meeting-followup`: Cowork exposed the draft-management tools, opened draft `aiws-productivity--meeting-followup--de0e75a572` from installed plugin version `0.2.1`, confined the edit to the draft under `~/.aiws/plugins/...`, validated and staged proposal `skillprop_ed458362021141179dbdb85a9df73794`, and submitted PR #2 to `sashakang/aiws-skill-tests`. The flow preserved installed plugin files, marketplace files, `~/.claude`, and Cowork runtime files. That historical test predated the corrected Gate 1 boundary; current normal Cowork submission leaves review and merge to repository maintainers and policy instead of writing product-level reviewer-role metadata. See [Cowork Regular User Draft Submit Report](./cowork-regular-user-draft-submit-report-2026-05-14.md).

This is not yet the full Phase 2B end-user path because the launcher still depends on `uvx`, production-grade submit must move from host `gh` to a GitHub App, bot, API, or Cowork-compatible adapter path, and review assignment needs repository policy such as CODEOWNERS or branch protection before it can be called enforced.

Current testing scenario: `docs/cowork-skills-management-phase2-test-plan.md` covers the Phase 2A path from marketplace-installed `core-aiws` and `aiws-productivity` through `meeting-followup`, draft creation, safe draft edits, `aiws.skills.validate_draft`, activation fallback, proposal staging, submit-for-review, and maintainer merge. Retest with refreshed `core-aiws >= 0.3.11`; if Cowork cannot see the AIWS tools, the draft-management scenarios remain blocked.

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

Align the Cowork install, skill lifecycle, and memory paths with `aiws-mcp` or an equivalent adapter so AIWS has one control-plane direction after the supported Cowork install/import path and initial lifecycle constraints are proven. Managed lifecycle behavior, including materialization state, staged skill changes, host surfaces, and future draft flows, should eventually sit behind a clean runtime boundary. This phase must not retroactively make Phase 1 depend on local MCP.

The concrete technical control-plane boundary is currently the local Python stdio MCP server `aiws-mcp` described in `docs/aiws-local-mcp-skills-mvp-plan.md`. That is acceptable as a Phase 2A implementation and pilot boundary, but the target Cowork path must not expose Python as a user prerequisite. For private and non-public skill maintenance, the near-term path is the Claude Code skill workshop, not running MCP in Claude Code and not exposing private local state through a hosted connector.

FastMCP or the official MCP Python SDK remains the preferred future connector-proof technology because AIWS control-plane code is already Python. The TypeScript SDK remains a possible later choice only if AIWS builds a new hosted service from scratch. Remote connector work must stay limited to harmless proof tools until auth, permissions, and tenancy are designed.

Uploaded-plugin `.mcp.json` stdio and HTTP experiments are closed evidence, not the path forward. They showed that Cowork upload plugins can remain useful as the skills and user-facing UX surface, but they should not be relied on for AIWS control-plane runtime registration unless Cowork documents or proves a supported local runtime path. Executable packaging and uploaded-plugin runtime experiments are paused on the same condition.

`aiws-mcp` owns these tool surfaces:

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

The parked FastMCP proof should expose only harmless runtime tools such as:

```text
aiws.health.ping
aiws.runtime.info
```

It must not expose memory tools, private skills, drafts, proposal records, source content, mutate managed Cowork plugin files, or write into marketplace or organization plugin packages.

Host identity is the boundary between the shared AIWS runtime and each host. Each host persists `~/.aiws/hosts/<host-id>/host.json`; `host-kind` is `claude-code`, `cowork`, or `codex`; and if `--host-id` is omitted, the default identity is derived from `host-kind` plus the hash of the canonical resolved host config root. Later commands may use `--host-id` alone. Missing host registration, conflicting CLI values, or duplicate shared skill IDs without pinned scope/version must fail closed.

The 2026-05-14 Cowork host-surface check passed only after `host_kind: cowork` was supplied. It returned `host_id: cowork-db8a0e250a1c`, `capability_exposure: plugin-package`, and `direct_host_install_supported: false`. Writable AIWS-owned surfaces were host identity, staged skill changes, materialized skill cache, adapter output, and package uploads. The installed Cowork plugin directory `~/.cowork/plugins` was read-only. This confirms the package boundary: AIWS can prepare package/upload artifacts and adapter output, while Cowork owns installation and update.

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
- The Claude Code skill workshop can update skill source, validate contracts, build Cowork packages, and prepare maintainer-controlled GitHub or marketplace publication without exposing private state to hosted MCP.
- The Cowork end-user path has no user-installed Python, `uvx`, `gh`, terminal, or manual MCP setup prerequisite.
- Technical-pilot dependencies are clearly labeled and cannot be mistaken for the target install path.

### Phase 5: Release Readiness

Turn the alpha into a repeatable release process.

Acceptance criteria:

- The repo has a clear test command that does not silently run zero tests.
- Release validation includes plugin contracts, skill compatibility, MCP config checks, and host adapter expectations.
- Runtime/generated files are clearly excluded from source control.
- Install docs distinguish developer workflows from normal user workflows.
- Release docs include a dependency audit that separately lists technical-pilot requirements and target end-user requirements.

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

Task: Lock the Cowork marketplace path as the current primary install gate.
Context: Cowork marketplace install is now the primary user journey. The user reported that Cowork installed the AIWS marketplace plugins and generated `meeting-followup` nodes correctly. Cowork Team ZIP import has also passed with `core-aiws` and `aiws-productivity`, but it is now the fallback path.
Owner: Developer session
Expected output: User-facing marketplace install guide and validation record for adding `sashakang/ai-workspace`, installing `core-aiws` and `aiws-productivity`, and invoking `meeting-followup` from Cowork. The existing ZIP import guide remains as fallback documentation.
Acceptance: The guide names the exact marketplace repo/path, Cowork marketplace UI path, expected plugin IDs/skills to verify, accepted source layout, safety boundaries, and fallback ZIP import path. It excludes local MCP, memory sync, draft editing, GitHub submission, RPM edits, and old registration restore from the marketplace install flow.
Evidence: `docs/aiws-cowork-fresh-marketplace-install.md`, `docs/aiws-cowork-runtime-validation-checklist.md`, user-reported Cowork marketplace runtime proof that `meeting-followup` nodes were generated correctly, and fallback evidence in `docs/aiws-cowork-plugin-import-validation-pass.md`.

Task: Capture lifecycle constraints for modified skills.
Context: Phase 2 is an urgent Cowork skills-management MVP. Current users need to edit or open drafts, validate them, prepare modified draft packages for Cowork upload, and stage proposals immediately after marketplace-installed Cowork plugins are available. Manual ZIP import remains a fallback install source only. Phase 2 should not wait for memory sync or MCP control-plane alignment.
Owner: Developer session
Expected output: Product and technical notes for draft creation, validation, activation, update conflict handling, and proposal staging.
Acceptance: The notes preserve one user-facing skill identity, use `Modified locally` and `Modified locally, pending Cowork upload` status labels, store draft registry entries under `~/.aiws/state/skill-drafts/`, store editable files under `~/.aiws/plugins/<marketplace-slug>/<plugin-id>-<origin-repo-sha10>`, store pending Cowork upload records under `~/.aiws/state/draft-activations/<host-id>/`, prepare modified draft packages without duplicate visible skill identity or runtime resolver changes, stage proposals through `stage_proposal` under `~/.aiws/state/skill-proposals/` rather than silently invoking `submit_pr`, expose submission as a separate Cowork UI action, never mutate managed marketplace or organization plugin files, fail closed on updates when a modified draft or pending upload exists, and offer only the approved update choices.
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

Task: Define the Claude Code skill workshop path.
Context: Private and non-public skill maintenance needs a practical near-term path that does not expose private skills, memory, drafts, or proposal records through hosted MCP. Claude Code can act as the maintainer/operator workshop without being the normal Cowork user surface.
Owner: Developer session
Expected output: Maintainer workflow documentation or implementation slice for updating skill source, validating contracts, running tests, building Cowork packages, pushing as maintainer or bot, and preparing or uploading marketplace artifacts on demand.
Acceptance: The workflow is clearly labeled maintainer/private-skill only, does not require MCP in Claude Code, does not replace Cowork as the normal install/use surface, preserves repository review boundaries, and keeps Cowork edit UX as the deferred product target.
Evidence: Changed docs, commands for validation/package build, and any tests or dry-run output used by the workflow.

Task: Park the Phase 2B FastMCP control-plane proof as secondary.
Context: Uploaded-plugin `.mcp.json` stdio and HTTP runtime experiments are closed evidence. The hosted FastMCP or official MCP Python SDK AIWS control-plane proof remains useful for future Cowork connector validation, but it is no longer the primary near-term path for private or non-public skills.
Owner: Developer session
Expected output: Hosted proof service exposing only `aiws.health.ping` and `aiws.runtime.info`, plus Cowork connector registration notes.
Acceptance: A normal Cowork user can install the AIWS skills through Cowork and access the harmless AIWS control-plane proof tools through Cowork without Python, `uvx`, `gh`, shell commands, uploaded-plugin runtime setup, or manual MCP configuration. The proof does not expose memory tools, private skills, drafts, proposal records, source content, or managed plugin mutation. Docs explicitly say this is a parked secondary proof, not the private-skills path and not an implemented production runtime.
Evidence: Cowork connector configuration, runtime logs, visible tool names, one successful ping/info call, and explicit note that FastMCP is secondary/future until auth, permissions, and tenancy are designed.

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

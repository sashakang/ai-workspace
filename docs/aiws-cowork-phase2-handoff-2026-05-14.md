# AIWS Cowork Phase 2 Handoff

**Date:** 2026-05-14  
**Project:** `sashakang/ai-workspace`  
**Primary user journey:** Cowork marketplace install  
**Current phase:** Phase 2A technical pilot for Cowork skills management  
**Current repo commit:** `9571ceb` (`Add Cowork GitHub submit handoff`)  
**Current visible versions:**

```text
core-aiws: 0.3.7
core-aiws contract: 0.3.7
marketplace metadata: 0.3.8
aiws-productivity: 0.2.1
```

## Executive Summary

Phase 2A has moved from a blocked concept to a working technical pilot for Cowork skill lifecycle management. A Cowork user can now install AIWS through the marketplace, open a draft from an installed skill, edit the draft safely, validate it, build an activation package fallback, stage a local proposal, and reach a safe submit-for-review handoff when Cowork lacks `gh`.

The implementation is not yet the final end-user Cowork experience. It still depends on `uvx` to launch the bundled AIWS MCP bridge, and real GitHub PR creation from Cowork still needs a Cowork-compatible GitHub adapter, bot, or connector-backed submitter. The latest implementation intentionally returns `submit_handoff_required` instead of pretending that a PR was created when `gh` is unavailable.

The most important product result is that the lifecycle is now honest and safe. Draft edits do not mutate installed marketplace plugins. Validation and staging preserve user work. Negative tests fail closed. Submission no longer crashes with a raw `gh: command not found`; it returns a structured handoff after all normal submit gates pass.

## Role And Operating Model

The PM role should remain product and coordination focused:

- define scope, acceptance criteria, and test scenarios
- delegate engineering to developer sessions or sub-agents
- require AI engineer and code reviewer gates
- keep Cowork user experience as the primary product lens
- avoid taking over implementation work except for light inspection and acceptance review

Implementation work in this phase was delegated to developer agents. Gate 2 reviews consistently included an AI-engineering lens and code review. GitHub pushes were done as `athanasiosbot`, per project rule.

## Current State

### Marketplace Install Path

Marketplace install is now the primary user journey.

Cowork marketplace:

```text
sashakang/ai-workspace
```

Minimum plugins for the current flow:

```text
core-aiws
aiws-productivity
```

`meeting-followup` from `aiws-productivity` is visible and usable after marketplace install. The original manual ZIP upload path remains a fallback only.

### Current Runtime Shape

`core-aiws` now bundles the AIWS MCP bridge source under:

```text
core-aiws/servers/aiws-mcp/
```

The Cowork-installed `core-aiws` package exposes an MCP server through:

```text
core-aiws/.mcp.json
core-aiws/bin/aiws-mcp-launcher
```

The launcher starts the bundled server through `uvx`:

```text
uvx --from "${CLAUDE_PLUGIN_ROOT}/servers/aiws-mcp" aiws-mcp serve
```

This is acceptable for Phase 2A technical pilot testing, but it is not acceptable for the final normal-user package. Phase 2B must remove user-installed Python, `uvx`, `gh`, terminal commands, and manual runtime setup from the Cowork user path.

### Working Tree Note

At handoff time, the repo has only one known untracked local artifact directory:

```text
dist/
```

This contains generated ZIPs and should remain untracked unless explicitly rebuilding and distributing artifacts. Do not use `git add .` casually in this repo.

## Key Commits In This Phase

Recent commits on `master`:

```text
9571ceb Add Cowork GitHub submit handoff
01e1305 Bump core AIWS release version
d841b4a Fix dirty draft reopen identity checks
0bfa1c0 Bundle AIWS MCP bridge in core plugin
36516f3 Record Cowork draft tool exposure blocker
a5f31c2 Tighten Cowork Phase 2 negative test prompts
69deaa1 Clarify Cowork Phase 2 testing prompts
af09cba Add Cowork Phase 2 test plan
228a919 Add Cowork draft validation operation
d88044c Make Cowork marketplace install primary
5be7214 Add Cowork clean import test plan
625e28b Fix Cowork import package builder
```

## Phase 2A Test Results

### Install And Smoke Test

Cowork marketplace install worked. The user reported:

- marketplace installed the plugins
- `meeting-followup` nodes were generated correctly
- `core-aiws` later exposed the AIWS MCP tools after the server bundle was added

The installed MCP server exposed tools under names like:

```text
mcp__plugin_core-aiws_aiws__aiws_skills_create_or_open_draft
mcp__plugin_core-aiws_aiws__aiws_skills_validate_draft
```

### Scenario A: Create Or Open Draft

Status: **PASS**

Observed draft:

```text
draft_id: aiws-productivity--meeting-followup--de0e75a572
draft_path: ~/.aiws/plugins/cowork-upload/aiws-productivity-de0e75a572
source: installed marketplace plugin
target_repo: sashakang/aiws-skill-tests
status: active, unmodified, last validation passed
```

Acceptance result:

- draft path is under `~/.aiws/plugins/`
- installed marketplace plugin files were not edited
- draft opened successfully

### Scenario B: Happy Path Edit And Validation

Status: **PASS**

User made a harmless edit inside:

```text
skills/meeting-followup/SKILL.md
```

Observed edit:

```text
"concise meeting minutes" -> "concise, structured meeting minutes"
```

Validation result:

```text
validation_status: passed
modified: true
status_label: Modified locally
package built: no
proposal staged: no
GitHub branch/commit/push/PR: no
installed marketplace plugin files touched: no
```

### Scenario C: Clean Unchanged Draft Validation

Status: **PASS**

Observed draft:

```text
draft_id: aiws-productivity--meeting-followup--689f3c6c5a
draft_path: /Users/aleksanderkan/.aiws/plugins/rpm/aiws-productivity-689f3c6c5a
validation_status: passed
modified: false
status_label: Current
```

No package, proposal, GitHub action, or installed-plugin mutation occurred.

### Scenario D: Out-Of-Scope Edit Safety

Status: **PASS with updated interpretation**

Initial implementation issue:

- direct external root-file edit could leave confusing state or create reopen path errors across source slugs
- fixed in `d841b4a`
- versioned for Cowork in `01e1305`

Retest on `core-aiws 0.3.6`:

```text
draft_id: aiws-productivity--meeting-followup--85b1961a6e
draft_path: /Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-85b1961a6e
```

Attempted writes:

```text
plugin.yaml
skills/plugin.yaml
```

Both were blocked by the draft API:

```text
Draft file path is outside the managed skill folder
```

Result:

- no out-of-scope file created through normal draft API
- validation passed because the draft remained clean
- reopening the same draft succeeded without overwriting
- no package, proposal, GitHub action, or installed-plugin mutation occurred

Updated interpretation:

Scenario D should allow either safe outcome:

```text
A. write_draft_file rejects the out-of-scope edit before validation
B. if an out-of-scope file already exists by external means, validate_draft fails closed and persists failed metadata
```

### Scenario E: Missing SKILL.md

Status: **PASS with UX/API improvement**

Observed draft:

```text
draft_id: aiws-productivity--meeting-followup--1295e51d67
draft_path: /Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-1295e51d67
```

Result:

- `delete_draft_file` allowed deleting `skills/meeting-followup/SKILL.md`
- `validate_draft` raised a hard error:

```text
Missing SKILL.md
```

Persisted state:

```text
last_validation_status: failed
last_validation_tree_digest: null
```

Reopen behavior:

- same draft reopened successfully
- dirty state was preserved
- missing `SKILL.md` was not overwritten

Safety result:

- no package built
- no proposal staged
- no GitHub action
- no installed-plugin mutation
- no `~/.claude` memory mutation

Improvement to file later:

```text
delete_draft_file should probably block deletion of the canonical skills/<skill_id>/SKILL.md, or validate_draft should return a structured failed validation result instead of only surfacing a hard tool error.
```

Current behavior is safe but rough.

### Scenario F: Activation Technical-Pilot Check

Status: **PASS**

Input draft:

```text
aiws-productivity--meeting-followup--de0e75a572
```

Result:

```text
status: host_capability_missing
capability_exposure: plugin-package
direct_host_install_supported: false
activation_effective: false
requires_manual_upload: true
```

Package output:

```text
/Users/aleksanderkan/.aiws/tmp/cowork-phase2-packages/aiws-productivity--meeting-followup--de0e75a572.zip
```

Fallback action:

```text
type: package_upload
host_kind: cowork
label: Upload draft package to Cowork
terminal: false
```

Interpretation:

- direct Cowork activation is not supported yet
- fallback package creation works
- this is expected Phase 2A behavior
- final UX still needs Cowork-supported activation/install handling

### Scenario G: Stage Proposal Without Submitting

Status: **PASS with API visibility gap**

Input draft:

```text
aiws-productivity--meeting-followup--de0e75a572
```

Proposal:

```text
proposal_id: skillprop_f5c76d99df644865ab73634d718e7c68
proposal_path: /Users/aleksanderkan/.aiws/state/skill-proposals/skillprop_f5c76d99df644865ab73634d718e7c68.json
target_scope: Personal test skills
target_repo: sashakang/aiws-skill-tests
draft_id: aiws-productivity--meeting-followup--de0e75a572
```

Safety:

- package built: no
- Cowork runtime mutation: no
- GitHub branch/commit/push/PR: no
- installed marketplace plugin mutation: no
- `~/.claude` memory touched: no

API visibility gap:

```text
stage_proposal response does not echo validation_status.
```

The proposal record contains validation data, but users should not need filesystem access to confirm the staging gate.

### Scenario H: Submit Staged Proposal For Review

Status before latest fix: **BLOCKED**

Observed in Cowork:

```text
gh: command not found
```

Root cause:

- `submit_for_review` depended on local GitHub CLI
- Cowork sandbox did not have `gh`
- GitHub MCP/connector auth was not proven callable from inside `aiws-mcp`

Important repo/access finding from PM environment:

```text
sashakang/aiws-skill-tests exists
visibility: PRIVATE
athanasiosbot has access
```

Latest implementation in `9571ceb`:

- runtime selects `GhCliProposalSubmitter` only when `gh` exists
- runtime selects `GithubHandoffProposalSubmitter` when `gh` is missing
- runtime still calls `submit_pr` in both cases
- `submit_pr` still runs all normal gates before calling the submitter:
  - proposal exists
  - `allowed_target_repos` matches
  - proposal is staged
  - validation status is passed
  - draft identity is valid
  - current draft digest matches staged validation digest
  - changes are only under the managed skill folder
  - plugin validates
  - skill exists

Expected Cowork retest on `core-aiws 0.3.7`:

```text
status: submit_handoff_required
reason_code: github_cli_unavailable
terminal: false
no_pr_created: true
required_review_roles includes AI engineer
proposal remains staged
branch_name/pr_url are not persisted as submitted metadata
```

This is not real PR creation. It is an honest safe handoff until a Cowork-compatible GitHub adapter exists.

## Known Gaps And Follow-Up Work

### Must Do Next

1. **Retest Scenario H on Cowork with `core-aiws 0.3.7`.**

   Expected result is `submit_handoff_required`, not a raw `gh` failure.

2. **Record the new Scenario H result in the Phase 2 test evidence.**

   If the result matches the expected structured handoff, Phase 2A can be considered technically validated except for final end-user packaging gaps.

3. **Decide the next product slice: real Cowork GitHub adapter or Phase 2B runtime packaging.**

   The adapter is needed for real PR creation from Cowork. Runtime packaging is needed before normal users can operate without `uvx`.

### Product/API Improvements

These are not blockers for Phase 2A safety, but they should be prioritized before broader user rollout:

- `stage_proposal` should return validation status and validation digest in its response.
- `delete_draft_file` should probably block deletion of the canonical `SKILL.md` or return a clearer user-facing warning.
- `validate_draft` should return structured failed validation results where possible, instead of relying on hard tool errors.
- `submit_handoff_required` should distinguish intended branch name from created branch. The current branch name is deterministic and useful for handoff, but no branch is created.
- `list_staged_changes` appeared empty even when `submit_for_review` could resolve a proposal by ID. Investigate scope/filtering.
- Cowork tool discovery should expose installed `core-aiws` version directly in AIWS responses, so testers do not need to inspect files.

### Architecture Gaps

These are the main remaining gaps between Phase 2A and the final normal-user Cowork experience:

- `core-aiws` still launches through `uvx`.
- Real PR creation still depends on either `gh` or a future Cowork-compatible GitHub adapter.
- Direct Cowork activation is not supported; activation currently returns a package-upload fallback.
- The current package is a technical pilot, not a dependency-free end-user runtime.
- Memory sync is not part of Phase 2A validation and remains a later phase.

## Current Test Commands

The latest pushed commit passed:

```bash
python -m unittest tests.test_aiws_skill_manager tests.test_aiws_mcp tests.test_cowork_packaging
python -m unittest discover -s tests
python -m py_compile aiws-mcp/aiws_mcp/runtime.py aiws-mcp/aiws_mcp/skill_manager.py core-aiws/servers/aiws-mcp/aiws_mcp/runtime.py core-aiws/servers/aiws-mcp/aiws_mcp/skill_manager.py tests/test_aiws_mcp.py tests/test_aiws_skill_manager.py
python -m json.tool .claude-plugin/marketplace.json
python -m json.tool core-aiws/.claude-plugin/plugin.json
python -m json.tool core-aiws/contracts/core-aiws.contract.json
git diff --check
```

Latest reported counts:

```text
focused suite: 150 tests passed
full suite: 185 tests passed
```

## Version And Retest Rules

For future Cowork tests, the installed plugin must show:

```text
core-aiws >= 0.3.7
```

If Cowork shows `0.3.6` or earlier, it does not have the latest submit handoff behavior. If Cowork shows `0.3.5` or earlier, it also may not have the draft-record safety fixes.

Version history relevant to recent testing:

```text
0.3.5: bundled AIWS MCP bridge
0.3.6: draft-record safety fix visible to Cowork
0.3.7: no-gh submit handoff
```

Marketplace metadata must show:

```text
0.3.8
```

## Recommended Next Cowork Prompt

After updating Cowork marketplace and reinstalling/updating `core-aiws` to `0.3.7`, rerun Scenario H with the staged proposal.

```text
Run Scenario H: Submit Staged Proposal For Review.

Submit this staged AIWS skill proposal for maintainer review:

proposal_id: skillprop_f5c76d99df644865ab73634d718e7c68

Target repo must be the one stored in the proposal:
sashakang/aiws-skill-tests

This action may create or update a GitHub branch and pull request only if a supported GitHub submit adapter is available.

Requirements:
- Use the staged proposal record.
- Revalidate the current draft before submitting.
- Refuse submission if the draft changed after staging.
- Do not submit if validation fails.
- Do not mutate installed marketplace plugin files.
- Do not touch ~/.claude memory.
- Do not activate the draft in Cowork.
- Include AI engineer in reviewer routing.
- If no GitHub CLI or Cowork-compatible GitHub adapter is available, return a structured submit_handoff_required result.

Afterward, tell me:
1. installed core-aiws version
2. submit result/status
3. reason_code, if any
4. proposal_id
5. target_repo used
6. branch_name returned, if any
7. PR URL, if created
8. whether no_pr_created is true or false
9. whether the proposal remained staged or was marked submitted
10. whether AI engineer reviewer routing is included
11. whether validation was rerun before submit
12. whether the staged validation digest matched current draft state
13. whether installed marketplace plugin files were touched
14. whether ~/.claude memory was touched
15. whether Cowork runtime files were mutated
16. any errors or manual follow-up needed
```

Expected current result:

```text
status: submit_handoff_required
reason_code: github_cli_unavailable
terminal: false
no_pr_created: true
required_review_roles includes AI engineer
proposal remains staged
```

## Developer Handoff: Next Implementation Options

### Option 1: Real Cowork-Compatible GitHub Submit Adapter

Goal: make Scenario H create/update a real PR from Cowork without local `gh`.

Research first. Do not guess.

Questions to answer:

- Does Cowork expose authenticated GitHub connector tools to plugin MCP servers?
- Can `aiws-mcp` call host connector tools directly, or only its own local tools?
- If connector calls are possible, what APIs exist for:
  - repository metadata
  - branch creation
  - file commit
  - PR create/update
  - reviewer metadata or role routing
- If connector calls are not possible, should AIWS use:
  - a GitHub App
  - an organization bot service
  - a maintainer handoff queue
  - an export package plus manual maintainer workflow

Acceptance:

- no user-pasted tokens
- no local `gh` requirement
- proposal remains staged until real review item exists
- PR metadata is written only after real PR creation/update
- `AI engineer` review routing remains present

### Option 2: Dependency-Free Cowork Runtime Package

Goal: remove `uvx` and local Python assumptions from normal Cowork user path.

Current state:

```text
core-aiws -> .mcp.json -> bin/aiws-mcp-launcher -> uvx -> bundled aiws-mcp
```

Target:

```text
Cowork install starts AIWS skill-management bridge without user-installed Python, uvx, gh, or shell setup.
```

Acceptance:

- install through Cowork is enough
- AIWS tools appear without terminal setup
- dependency audit proves no user-installed runtime dependency
- all Phase 2A scenarios still pass

### Option 3: User-Facing Cleanup And UX Hardening

Goal: improve rough edges found during Phase 2A without solving GitHub adapter yet.

Candidate fixes:

- make `stage_proposal` response include validation metadata
- make `delete_draft_file` block canonical `SKILL.md` deletion or return a clearer safety warning
- return structured validation failure objects where possible
- make `list_staged_changes` reliably surface proposal records in the same scope as `submit_for_review`
- expose installed `core-aiws` version through AIWS tools

## Safety Rules To Preserve

Do not regress these:

- never edit installed marketplace plugin files in place
- never edit `~/.claude` memory during Cowork skills-management tests
- never mutate Cowork RPM files by hand
- never reconstruct Cowork marketplace state manually as a clean install substitute
- draft edits must stay under `~/.aiws/plugins/`
- draft state must stay under `~/.aiws/state/skill-drafts/`
- proposal state must stay under `~/.aiws/state/skill-proposals/`
- validation-only operations must not activate, stage, package, submit, or upload
- staging must not create GitHub branches, commits, pushes, or PRs
- submit must not mark a proposal submitted until a real review item exists
- `AI engineer` must stay in review routing

## Important Files

Current implementation surfaces:

```text
aiws-mcp/aiws_mcp/runtime.py
aiws-mcp/aiws_mcp/skill_manager.py
core-aiws/servers/aiws-mcp/aiws_mcp/runtime.py
core-aiws/servers/aiws-mcp/aiws_mcp/skill_manager.py
```

Contracts and plans:

```text
core-aiws/contracts/skill-management.md
core-aiws/protocols/skill-management.md
docs/aiws-cowork-skills-management-mvp.md
docs/aiws-cowork-skills-management-implementation-slices.md
docs/cowork-skills-management-phase2-test-plan.md
docs/aiws-project-development-plan.md
```

Tests:

```text
tests/test_aiws_skill_manager.py
tests/test_aiws_mcp.py
tests/test_cowork_packaging.py
```

Packaging:

```text
scripts/build_cowork_import.py
dist/cowork-import/
```

Do not commit generated `dist/` contents unless explicitly requested.

## Open Questions

1. Can Cowork plugin MCP servers invoke host-level GitHub connector tools?
2. If yes, what is the exact supported API and auth boundary?
3. If no, should the AIWS submit adapter be an org bot/GitHub App instead?
4. Should activation remain package-upload fallback, or should Cowork support direct plugin replacement?
5. Should `delete_draft_file` block `SKILL.md` deletion at API level?
6. How should staged proposals be listed consistently across Cowork sessions/scopes?
7. What is the expected UX label for `submit_handoff_required`?

## PM Recommendation

The next PM decision is between two priorities:

1. **If the customer urgently needs proposal submission:** research and implement a Cowork-compatible GitHub submit adapter.
2. **If the customer needs broader nontechnical users:** prioritize dependency-free Phase 2B packaging so users do not need `uvx`, Python, `gh`, or terminal setup.

Given the current customer experiment allows GitHub use by maintainers, the pragmatic next slice is:

```text
Research Cowork-compatible GitHub submit adapter options, then implement the smallest adapter or confirm the handoff remains the only supported Cowork path.
```

Do not build against assumptions. The next research task must prove whether the GitHub connector is callable from the AIWS MCP runtime.


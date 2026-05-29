# Miro Board Handoff — AIWS Skill Library Phase 1 Testing Scenario

## Purpose

Continue work on the Miro board that visualizes the AIWS Phase 1 Drive Skill Library 10-step testing scenario. The board is freshly created with the core flowchart in place. The next agent extends it with annotations, callouts, and reference clusters as listed in **Open work**.

## Board

- **Name**: AIWS Skill Library Phase 1 — Testing Scenario
- **URL**: https://miro.com/app/board/uXjVHNBbn_8=/
- **Created by**: prior agent acting on behalf of Sasha Kang
- **Confirm before creating any new board**; current board is the only canvas in scope.

## What is already on the board

A single top-to-bottom flowchart titled "AIWS Phase 1 — 10-step demo flow" centered at (0, 0). It contains:

- **25 nodes**: START + 10 main steps with sub-steps (4.1, 4.2, 4.3, 10a, 10b) + END.
- **Decision diamonds** at three points: clean-state check (Step 1), Save-plugin-card OK (Step 2), Step 10 download-vs-update fork.
- **7 dashed-line clusters** grouping steps by phase: Preflight (Step 1), First install (Step 2), Author + propose new skill (Steps 3–4), Refresh + pick up new skill (Step 5), Use + iterate locally (Steps 6–7), Propose v.2 update (Steps 8–9), Canonical flows out (Step 10).
- **Color palette**: `#adf0c7 #c6dcff #fff6b6 #ffd8f4 #dbfaad`
  - green (`#adf0c7`) — terminators (START/END)
  - blue (`#c6dcff`) — decisions
  - light green (`#dbfaad`) — AIWS-invoking steps (install, propose, refresh, validate)
  - pink (`#ffd8f4`) — maintainer actions (read proposal, edit canonical)
  - yellow (`#fff6b6`) — user / Cowork-local steps (author local skill, click Save plugin, cleanup, verify)
- **Anti-pattern guard** wired into the flow: NO branch on the Save-plugin-card decision reads "Save skill or .skill artifact" and loops back to Reset.

## Source of truth for the demo content

The flowchart was built from the 10-step manual in the `sashakang/ai-workspace` GitHub repo:

- **File**: `docs/aiws-skill-library-phase1-testing-manual.md`
- **Latest relevant commits**:
  - `17e2270` — `core-aiws v0.4.22: signal SOP hard-coding fix release`
  - `7457058` — `testing manual: restructure around 10-step demo + SOP for AIWS skill name hardcoding`
- **Author identity for all repo edits**: `athanasiosbot <athanasiosbot@users.noreply.github.com>`

Any change to step language, marker conventions, or anti-pattern wording should be cross-checked against this manual.

## Open work, in priority order

1. **Side annotations per step** — sticky notes or text widgets next to each main step listing:
   - the natural-language user prompt (from the manual)
   - which AIWS skill is invoked (e.g., `aiws-install-drive-skill-library`)
   - which surface is touched (Drive canonical / Drive proposals / local user skill / installed plugin)
2. **Cleanup arrows as dashed** — Step 4.3 → "delete proposal folder", Step 5 → "Cleanup local if byte-identical to last proposal", Step 9 → "delete proposal folder". These currently render as the standard elbow connector; the cleanup-path semantics should visually differ from forward flow.
3. **Anti-pattern callouts** — red boxes on Step 2 and Step 5: `.skill` artifact / Save skill card / per-skill plugin id `<plugin-id>--<skill-id>` / `aiws-generated-plugin` identity / marketplace-language → FAIL. The current flowchart only mentions Save skill on the Step 2 decision branch; the full anti-pattern set in the manual is broader.
4. **Maintainer review reference** — pin the `code --diff` and Meld command syntax near Step 4.2 / Step 9 so the maintainer's local Markdown diff step is concrete.
5. **Known Upstream Skill Issues panel** — a footer cluster listing the three open AIWS-skill issues (`aiws-install` legacy hard-coded `meeting-followup`, `aiws-propose` mis-instruction on `contracts/<plugin-id>.contract.json`, `aiws-refresh` missing anti-marketplace guard) and the SOP audit table. Source: manual's "Known Upstream Skill Issues" section.
6. **Marker convention reference card** — a small pinned widget stating: marker is `> <skill-id> v1: running` for v1, `> <skill-id> v2: running` for v2 (hyphen + colon — option A). Note that the demo's actual canonical SKILL.md uses an alternate spaced form; the agent should NOT edit canonical to "fix" this — it's an accepted drift, manual is the spec.
7. **REMOVE Step 10 decision diamond and 10a node from the flowchart** — Step 10a (fresh install) was determined to be mechanically identical to Step 2 and was deleted from the manual. The current diagram's Step 10 decision (`Download 10a or Update 10b`) and its 10a branch (`Step 10a Fresh install Test Plugin`) are now obsolete. Step 10 is a single linear node: "Refresh Test Plugin (rebuild, bump 0.2.0 → 0.2.1)". The diagram needs:
   - Delete node n19 (decision diamond `Step 10 Download 10a or Update 10b`)
   - Delete node n20 (`Step 10a Fresh install Test Plugin`)
   - Rename node n21 from `Step 10b Refresh Test Plugin ...` to `Step 10 Refresh Test Plugin ...`
   - Re-wire: incoming edge into n21 comes directly from n18 (Step 9 accept); the merge edge from n20 into n22 is dropped
   - Update cluster c7 title from "Canonical flows out (Step 10)" to keep the same title — still accurate, just one path now

## Tools the next agent will need

Available via ToolSearch (Miro server prefix: `mcp__24e7f6ec-fdcc-4e72-95bc-7e4a70744b13__*`):

- `board_search_boards` — find the existing board if URL is lost
- `diagram_get_dsl` — fetch the flowchart DSL spec before any new diagram edit
- `diagram_create` — add new diagrams (specify `miro_url` to target the existing board)
- `comment_create` / `comment_list_comments` — sticky comments per node
- `code_widget_create` — for displaying user prompts or command examples verbatim
- `doc_create` / `doc_update` — for the Known Upstream Skill Issues panel as a doc widget
- `image_create` — for color-legend or screenshot annotations
- `layout_create` / `layout_get_dsl` — for additional swimlane / annotation layout if needed
- `board_list_items` — to enumerate current widgets and find item IDs

Outside Miro:

- `mcp__workspace__bash` — for reading manual content / cross-checking against repo
- `Read` on `/Users/aleksanderkan/projects/ai-workspace/docs/aiws-skill-library-phase1-testing-manual.md` — primary source

## Constraints and conventions to respect

- **Marker convention**: option A (hyphen + colon) is the spec. Do not invent a third convention.
- **Approved/Rejected folders are unused** in the demo; do not render arrows pointing to them.
- **Test Plugin / test-plugin / morning-briefing / slack-response-triage / schedule-summary** are the only concrete names that appear in the manual. New skill names should not be invented in the diagram.
- **Athanasiosbot identity** is used for any repo commit that materializes from this work. Do not commit as any other identity.
- **Approval before destructive action**: any deletion or board overwrite needs Sasha's explicit confirmation per his standing instruction.

## Quick recovery checklist if anything is unclear

1. Open the Miro board URL above — verify the flowchart is present at center.
2. Read `docs/aiws-skill-library-phase1-testing-manual.md` end-to-end (about 600 lines).
3. Cross-reference each step in the manual to its node in the flowchart.
4. Pick the highest-priority open work item from the list above.
5. Show Sasha a brief plan before adding new board content (sticky locations, count, sample wording).

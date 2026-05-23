# AIWS Skill Library Phase 1

## Summary

Restart around a skill-first, Drive-backed model. Cowork can import/install a Google Drive root folder shaped like a lightweight plugin container:

```text
<Drive root>/
  skills/
    <skill-id>/
      SKILL.md
```

Cowork may present that root as a plugin-like container, but AIWS treats it as a Skill Library, not a packaged plugin marketplace. AIWS provides the convention, metadata, validation, and maintainer update skills. Cowork installs and runs skills. Google Drive is the shared source and review space.

No ZIP upload, plugin contracts, bridge export, or Cowork marketplace registration is required for the Drive happy path. Cowork may still require a generated plugin artifact/card for first-class plugin visibility; that artifact is produced from the Drive folder at install time.

## Target User Stories

- As a Cowork user, I can use the AIWS install skill to package a shared Drive folder into a Cowork **Save plugin** artifact and use its skills under one plugin-like container.
- As a maintainer, I can keep team skills in a Google Drive folder with a predictable structure.
- As a contributor, I can use the AIWS proposal skill to save or export the changed `SKILL.md` into `Proposals/Submitted/`.
- As a maintainer, I can review a submitted `SKILL.md` by comparing local Markdown copies in VS Code/VSCodium or Meld, then apply accepted changes directly to canonical `skills/<skill-id>/SKILL.md`.
- As a maintainer, I can optionally move or copy the proposal folder to `Proposals/Approved/` or `Proposals/Rejected/` for recordkeeping.
- As a maintainer, I can use the AIWS refresh skill to verify the canonical skill file, validate the library, and refresh Cowork from Drive.
- As an AIWS maintainer, I can keep the same skill folders compatible with Cowork, Claude Code, and Codex.
- As an AIWS maintainer, I can later map GitHub libraries or real plugin-backed libraries into the same model.

## Key Changes

- Define AIWS Skill Library as the source-neutral product object.
- Phase 1 source kind: `google_drive`; future reserved kinds: `github`, `cowork_plugin`.
- First demo library name: `Test Plugin`.
- Use this Drive shape:

```text
Test Plugin/
  skills/
    meeting-followup/
      SKILL.md
    morning-briefing/
      SKILL.md
```

- Keep `SKILL.md` portable: only `name` and `description` frontmatter; folder name equals frontmatter `name`.
- Keep AIWS metadata outside runtime skill folders.
- Test whether Cowork tolerates root-level AIWS metadata/proposal folders. If not, store metadata out-of-band.
- Add `aiws-validate-skill-library` as the Phase 1 AIWS skill for user-facing library validation. Python validation remains a developer/CI check, not the primary product surface.
- Add `aiws-install-drive-skill-library` as the Phase 1 install helper. In Cowork, it reads the Drive folder, packages `skills/<skill-id>/SKILL.md` into one plugin artifact, and presents a **Save plugin** card. The generated artifact uses Cowork's flat package layout: `.claude-plugin/plugin.json`, `contracts/<plugin-id>.contract.json`, and `skills/<skill-id>/SKILL.md` at archive root. Its fallback/manual wording is exactly `Install this Google Drive folder as a plugin: <drive-folder-url>`.
- The install helper must preflight the generated artifact before showing the **Save plugin** card. It reports `READY FOR SAVE` while waiting for the user click, and `PASS` only after Cowork accepts the plugin and the installed plugin/container and skills are verified.
- Keep the install helper out of AIWS marketplace tooling. It must not register the Drive folder as a marketplace, call `aiws.marketplaces.drive_workflow`, call `export_cowork_bridge`, or report that a `test-plugin` marketplace is empty. A flat `skills/<skill-id>/SKILL.md` folder is enough for the Phase 1 install path.
- Add `aiws-propose-skill-update` as the Phase 1 contributor skill for preparing `Proposals/Submitted/<skill-id>/<proposal-id>/` folders and `aiws.proposal.json` metadata.
- Add `aiws-refresh-skill-library` as the Phase 1 maintainer verification and refresh skill after the maintainer applies accepted changes to canonical `skills/<skill-id>/SKILL.md`.
- Keep `aiws-update-skill-library` only as a compatibility alias for refresh. The user-facing verb is `refresh`, not `update`, because `update meeting-followup` sounds like a request to edit the skill content.
- Make user prompts human-style. `refresh Test Plugin`, `sync Test Plugin from Drive`, and `refresh meeting-followup in Test Plugin` mean verify/refresh the library. The assistant should ask what to change only when the user explicitly asks to edit, rewrite, propose, create, or change skill content.
- Treat `Proposals/Approved/` and `Proposals/Rejected/` as optional archive/status folders. They are useful for recordkeeping, but they are not mandatory workflow gates.
- Use local Markdown diff for maintainer review. The recommended path is VS Code/VSCodium `code --diff skills/<skill-id>/SKILL.md Proposals/Submitted/<skill-id>/<proposal-id>/SKILL.md`; Meld is the non-IDE alternative. Google Docs compare is not part of Phase 1.
- Runtime capability artifacts like MCP servers, connectors, auth config, and host tools are out of phase 1.
- Existing plugin-backed AIWS flows remain unchanged and still require plugin manifests, contracts, draft records, and proposal state.
- The Drive source folder remains skill-first and does not contain plugin manifests or contracts. Any plugin manifest or contract exists only in the generated Cowork install artifact.

## Metadata Convention

If Cowork tolerates root-level extras, the Drive root may include:

```text
Test Plugin/
  aiws.library.json
  aiws.skills/
    meeting-followup.json
    morning-briefing.json
  Proposals/
    Submitted/
      meeting-followup/
        <proposal-id>/
          SKILL.md
          aiws.proposal.json
    Approved/
      meeting-followup/
        <proposal-id>/
          SKILL.md
          aiws.proposal.json
    Rejected/
      meeting-followup/
        <proposal-id>/
          SKILL.md
          aiws.proposal.json
  skills/
    meeting-followup/
      SKILL.md
    morning-briefing/
      SKILL.md
```

If Cowork exposes or rejects those extras, keep the same metadata shape in a sibling or out-of-band AIWS metadata folder and leave the Cowork-imported root as `skills/<skill-id>/SKILL.md` only.

Stable AIWS identity should come from the Drive folder ID or explicit AIWS metadata, not the mutable Drive folder name.

## Test Plan

- Cowork import test prompt: `Install Test Plugin from this Drive folder: <folder-url>`. Cowork should generate one preflighted **Save plugin** artifact/card for the Drive root and install it as a plugin/container, not only as loose skills. A `Plugin validation failed` result must include the generated archive entries, manifest JSON, contract JSON, packaged skill frontmatter, and exact Cowork error text if available.
- Metadata tolerance test: verify whether Cowork ignores root-level `aiws.library.json`, `aiws.skills/`, and `Proposals/`.
- Validation test prompt: `Check Test Plugin skill library`.
- Proposal test prompt: `Propose this meeting-followup change for Test Plugin: <plain-language change>`.
- Review test: maintainer opens local/synced copies of canonical and proposed `SKILL.md` in VS Code/VSCodium or Meld and confirms the diff is understandable.
- Canonical update test: maintainer applies accepted changes directly to `skills/<skill-id>/SKILL.md`.
- Optional archive test: maintainer may move or copy the proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/` or `Proposals/Rejected/<skill-id>/<proposal-id>/` in Google Drive UI for recordkeeping.
- Refresh test prompt: `Refresh Test Plugin` or `Refresh meeting-followup in Test Plugin`. This should verify the canonical update, validate the library, and verify Cowork refresh/import sees the update without asking what content change to make.
- Compatibility test: Cowork, Claude Code, and Codex consume plain skill folders.
- Boundary test: existing plugin-backed flows still require manifests/contracts and are not treated as Skill Library mode.

## Assumptions

- First-class phase 1 visibility means first-class Cowork visibility for skills, even if Cowork labels the containing Drive folder as a plugin.
- AIWS in phase 1 means standards, governance, validation, metadata, and optional tooling, not runtime execution.
- Submitted proposals are the required contributor landing zone. Approved/Rejected folders are optional archive/status folders, not required gates.
- If Cowork rejects the plain Drive-root skill-library path later, phase 1 fails closed and does not fall back to ZIP upload, plugin bridge, or marketplace work.

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
- As a maintainer, I can review a submitted `SKILL.md` in Drive and approve it by moving or copying the final proposal folder to `Proposals/Approved/`.
- As a maintainer, I can use the AIWS update skill to apply an approved proposal to the canonical skill file, validate the library, and verify Cowork refresh.
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
- Add `aiws-install-drive-skill-library` as the Phase 1 install helper. In Cowork, it reads the Drive folder, packages `skills/<skill-id>/SKILL.md` into one plugin artifact, and presents a **Save plugin** card. Its fallback/manual wording is exactly `Install this Google Drive folder as a plugin: <drive-folder-url>`.
- Add `aiws-propose-skill-update` as the Phase 1 contributor skill for preparing `Proposals/Submitted/<skill-id>/<proposal-id>/` folders and `aiws.proposal.json` metadata.
- Add `aiws-update-skill-library` as the Phase 1 maintainer skill for applying only approved proposals from `Proposals/Approved/<skill-id>/<proposal-id>/`.
- Treat Drive folder movement as the approval signal. Chat statements and proposal metadata do not approve a proposal.
- Runtime capability artifacts like MCP servers, connectors, auth config, and host tools are out of phase 1.
- Existing plugin-backed AIWS flows remain unchanged and still require plugin manifests, contracts, draft records, and proposal state.

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

- Cowork import test: use `aiws-install-drive-skill-library`; Cowork should generate one **Save plugin** artifact/card for the Drive root and install it as a plugin/container, not only as loose skills.
- Metadata tolerance test: verify whether Cowork ignores root-level `aiws.library.json`, `aiws.skills/`, and `Proposals/`.
- Validation test: use `aiws-validate-skill-library` to check the Drive root and report PASS/FAIL with concrete fixes.
- Proposal test: use `aiws-propose-skill-update` to save/export edited `SKILL.md` into `Proposals/Submitted/<skill-id>/<proposal-id>/` with `aiws.proposal.json`.
- Approval test: maintainer moves or copies the final proposal folder to `Proposals/Approved/<skill-id>/<proposal-id>/` in Google Drive UI.
- Update test: use `aiws-update-skill-library` to apply the approved proposal, validate the library, and verify Cowork refresh/import sees the update.
- Compatibility test: Cowork, Claude Code, and Codex consume plain skill folders.
- Boundary test: existing plugin-backed flows still require manifests/contracts and are not treated as Skill Library mode.

## Assumptions

- First-class phase 1 visibility means first-class Cowork visibility for skills, even if Cowork labels the containing Drive folder as a plugin.
- AIWS in phase 1 means standards, governance, validation, metadata, and optional tooling, not runtime execution.
- Approval is Drive-folder state: only `Proposals/Approved/<skill-id>/<proposal-id>/` can be applied by the update skill.
- If Cowork rejects the plain Drive-root skill-library path later, phase 1 fails closed and does not fall back to ZIP upload, plugin bridge, or marketplace work.

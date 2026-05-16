# AIWS Repo Scaffold And Release Workflow Gate 1

**Date:** 2026-05-16  
**Result:** PASS  
**Scope:** reusable repo scaffold and GitHub Actions maintainer release workflow

## Decision

AIWS participating repos need a reusable scaffold before they are considered release-ready. Normal Cowork users continue to propose only skill-folder changes under `skills/<skill_id>/...`. Maintainers own plugin release metadata and marketplace publication.

The release path is:

```text
Cowork proposal -> maintainer review/merge -> GitHub Actions release PR -> maintainer merge release PR -> Cowork marketplace sync
```

## Approved Constraints

- Release PRs are created by a least-privilege GitHub App credential.
- Validation and package build steps use read-only credentials.
- The workflow does not use `pull_request_target`.
- The workflow is manually triggered with `workflow_dispatch`.
- Inputs require `plugin_id` and exactly one of `bump_type` or `explicit_version`.
- Invalid SemVer, downgrade, no-op, and existing metadata drift fail.
- Plugin manifest, contract, and marketplace plugin entry versions move together.
- Root marketplace metadata version changes only for marketplace-level metadata changes.
- Scaffold install/check is idempotent and refuses to overwrite modified owned files unless forced.

## Reviewer Outcome

- AI engineer reviewer: PASS.
- Release engineering reviewer: PASS.
- Product/architecture reviewer: PASS with conditions.

## Gate 2 Conditions

- Name the marketplace sync owner and failure path per participating repo.
- Add a repo readiness checklist before calling a repo AIWS-release-ready.
- Confirm GitHub App-created PRs trigger required `pull_request` checks.
- Keep release PR diffs predictable and reviewable.

## Implemented Surfaces

- `scripts/aiws_release.py` prepares and validates plugin releases.
- `scripts/aiws_repo_scaffold.py` installs and checks reusable scaffold files.
- `.github/workflows/aiws-release-plugin.yml` is the generated maintainer release workflow.
- `docs/aiws-maintainer-release-runbook.md` is the generated maintainer runbook.
- `tests/test_aiws_release_workflow.py` covers release and scaffold behavior.

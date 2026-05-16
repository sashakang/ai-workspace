# AIWS Maintainer Release Runbook

AIWS separates contribution from release.

Contributor flow:

```text
Draft -> Validated -> Submitted -> Accepted
```

Maintainer release flow:

```text
Accepted -> Released -> Marketplace synced
```

`Accepted` means a skill proposal PR was merged. It does not mean the updated plugin is available in Cowork.

## Release A Plugin

Prerequisite: the repo has an AIWS GitHub App installed with write access to contents and pull requests. Configure these repository secrets before running the workflow:

- `AIWS_RELEASE_APP_ID`
- `AIWS_RELEASE_APP_PRIVATE_KEY`

If either secret is missing, the workflow stops before creating a token and reports the missing release credential setup.

1. Open GitHub Actions.
2. Run **AIWS Release Plugin**.
3. Enter the `plugin_id` from `.claude-plugin/marketplace.json`.
4. Set exactly one version input:
   - `bump_type`: `patch`, `minor`, or `major`
   - `explicit_version`: a concrete `MAJOR.MINOR.PATCH`
5. Review the generated release PR.
6. Merge only after validation passes.
7. Trigger or wait for Cowork marketplace sync.

The workflow updates plugin release metadata and opens a PR. It does not push directly to `master`.

If the release PR is merged but Cowork marketplace sync fails, the plugin is `Released` in GitHub but not `Marketplace synced`. Do not tell Cowork users the version is available until the marketplace update is visible from Cowork.

## Repo Readiness

A repo is AIWS-release-ready only when:

- this scaffold check passes
- release PR creation uses the AIWS GitHub App credential
- normal user proposals remain skill-folder-only
- plugin manifest, contract, and marketplace versions validate consistently
- Cowork marketplace sync ownership and failure handling are documented for the repo

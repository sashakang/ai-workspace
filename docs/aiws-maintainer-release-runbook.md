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

## One-Time Repo Setup

Each participating AIWS repo needs the same release scaffold and a repo-installed GitHub App before maintainers can cut plugin releases from GitHub.

Install or verify the scaffold from the repo root:

```bash
python -m scripts.aiws_repo_scaffold check
```

If the scaffold is missing in a new repo, install it from a repo that already contains `scripts/aiws_repo_scaffold.py`:

```bash
python -m scripts.aiws_repo_scaffold install --repo-root /path/to/target-repo
```

The scaffold owns these files:

```text
.github/workflows/aiws-release-plugin.yml
docs/aiws-maintainer-release-runbook.md
```

If `check` reports changed scaffold files, inspect the diff before overwriting. Use `--force` only when you intentionally want to replace the target repo's scaffold files with the canonical version.

## GitHub App Setup

Create a GitHub App once, then install it on every repo that should be able to create AIWS release PRs.

1. GitHub -> avatar -> **Settings** -> **Developer settings** -> **GitHub Apps**.
2. Create a new GitHub App. Use a name such as `aiws-release-bot`.
3. Disable webhooks unless the repo has a separate reason to receive them.
4. Give the app these repository permissions:
   - **Contents:** Read and write
   - **Pull requests:** Read and write
   - **Metadata:** Read-only, which GitHub includes automatically
5. Create the app.
6. Copy the numeric **App ID** from the app settings page.
7. Generate a private key and download the `.pem` file.
8. Install the app on the target repo, for example `owner/repo`.

Do not paste the private key into chat or commit it to the repo. Keep the downloaded `.pem` file local and restrict permissions:

```bash
mkdir -p ~/.config/aiws/secrets
mv ~/Downloads/*.private-key.pem ~/.config/aiws/secrets/aiws-release-bot.private-key.pem
chmod 600 ~/.config/aiws/secrets/aiws-release-bot.private-key.pem
```

Configure the target repo secrets:

```bash
gh secret set AIWS_RELEASE_APP_ID \
  --repo owner/repo \
  --body "<numeric-app-id>"

gh secret set AIWS_RELEASE_APP_PRIVATE_KEY \
  --repo owner/repo \
  < ~/.config/aiws/secrets/aiws-release-bot.private-key.pem
```

Verify the secrets exist:

```bash
gh secret list --repo owner/repo
```

Expected secret names:

```text
AIWS_RELEASE_APP_ID
AIWS_RELEASE_APP_PRIVATE_KEY
```

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

CLI equivalent:

```bash
gh workflow run "AIWS Release Plugin" \
  --repo owner/repo \
  -f plugin_id=aiws-productivity \
  -f bump_type=patch
```

Then watch the run:

```bash
gh run list --repo owner/repo --workflow "AIWS Release Plugin" --limit 1
gh run watch <run-id> --repo owner/repo --exit-status
```

Expected result:

```text
workflow status: success
release PR author: app/aiws-release-bot
release PR title: Release <plugin_id> <new_version>
release branch: aiws/release/<plugin_id>/<new_version>
```

If the workflow fails with missing `AIWS_RELEASE_APP_ID` or `AIWS_RELEASE_APP_PRIVATE_KEY`, the GitHub App secrets are not configured on that repo. If PR creation fails after the token step, check that the GitHub App is installed on the repo and has **Contents** and **Pull requests** set to read/write.

If the release PR is merged but Cowork marketplace sync fails, the plugin is `Released` in GitHub but not `Marketplace synced`. Do not tell Cowork users the version is available until the marketplace update is visible from Cowork.

## Repo Readiness

A repo is AIWS-release-ready only when:

- this scaffold check passes
- release PR creation uses the AIWS GitHub App credential
- normal user proposals remain skill-folder-only
- plugin manifest, contract, and marketplace versions validate consistently
- Cowork marketplace sync ownership and failure handling are documented for the repo

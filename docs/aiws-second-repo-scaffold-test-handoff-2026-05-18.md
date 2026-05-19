# AIWS Second-Repo Scaffold Test Handoff

**Date:** 2026-05-18  
**Target repo:** `owner/repo`  
**Operator identity:** `kangsasha` on the local machine  
**Source-of-truth scaffold repo:** `sashakang/ai-workspace`  
**Goal:** prove the reusable AIWS release scaffold works on a second participating repo

## Why This Test Exists

The primary repo already passed the full maintainer release loop:

```text
Accepted -> Released -> Marketplace synced
```

That is not enough to call the scaffold reusable. The next proof is to apply the same release scaffold, GitHub App, and GitHub Actions flow to a second repo and confirm the result is not tied to one repository or one host.

## Architecture Boundary

This test is host-agnostic.

`Cowork`, `Claude Code`, and `Codex` are all first-class hosts in the target architecture. The thing being tested here is not host-specific behavior. The thing being tested is:

- reusable repo scaffold
- GitHub App credential path
- GitHub Actions release workflow
- repo-level release metadata updates

Any host may be used to drive the repo changes. For this handoff, the operator will run the test from the local machine. `Cowork` is only needed later if the repo is actually connected to a Cowork marketplace and the released version needs runtime verification there.

## What Counts As PASS

This test is a real PASS only if all of the following are true:

- the second repo accepts the scaffold files cleanly
- scaffold check passes
- the GitHub App is installed on the second repo
- repo secrets are configured on the second repo
- the `AIWS Release Plugin` workflow succeeds
- a release PR is opened by `app/aiws-release-bot`
- the release PR uses branch `aiws/release/<plugin_id>/<new_version>`
- the PR updates plugin manifest, contract, and marketplace plugin entry consistently
- no direct push is made to the default branch

If the repo is later connected to a Cowork marketplace, the final downstream proof is that Cowork sees the new version. That is downstream verification, not part of the scaffold proof itself.

## First Readiness Check

Before installing the scaffold, confirm the target repo is shaped like an AIWS marketplace/plugin repo.

Look for:

```text
.claude-plugin/marketplace.json
```

Then confirm that the referenced plugin source contains:

```text
.claude-plugin/plugin.json
contracts/<plugin>.contract.json
skills/<skill-id>/SKILL.md
```

If the repo does not already have marketplace/plugin structure, stop. The scaffold does not convert an arbitrary repo into a release-ready AIWS plugin repo by itself.

## Local Operator Flow

### 1. Clone both repos locally

```bash
cd ~/Documents
git clone https://github.com/sashakang/ai-workspace.git
git clone https://github.com/owner/repo.git
```

If both clones already exist, reuse them.

### 2. Inspect the target repo shape

```bash
cd ~/Documents/repo
find . -maxdepth 3 \( -name marketplace.json -o -name plugin.json -o -name "*.contract.json" -o -name SKILL.md \)
```

Use this to confirm the repo really contains AIWS plugin assets before proceeding.

### 3. Install the scaffold from `ai-workspace`

Run this from the scaffold source repo:

```bash
cd ~/Documents/ai-workspace
python -m scripts.aiws_repo_scaffold install --repo-root ~/Documents/repo
```

This should add:

```text
.github/workflows/aiws-release-plugin.yml
docs/aiws-maintainer-release-runbook.md
```

### 4. Verify the scaffold inside the target repo

```bash
python -m scripts.aiws_repo_scaffold check --repo-root ~/Documents/repo
```

Expected result:

```text
status: ok
missing: []
changed: []
```

### 5. Commit and push the scaffold in the target repo

```bash
cd ~/Documents/repo
git status
git add .github/workflows/aiws-release-plugin.yml docs/aiws-maintainer-release-runbook.md
git commit -m "chore: add AIWS release scaffold"
git push origin <default-branch>
```

Use the actual default branch name for that repo, usually `main` or `master`.

## GitHub App Setup On The Second Repo

Reuse the existing GitHub App:

```text
App ID: <app-id>
```

The app must be installed on `owner/repo`.

Required repository permissions:

- `Contents: Read and write`
- `Pull requests: Read and write`

Do not create a second app unless there is a policy reason to separate credentials.

## Repo Secret Setup On The Second Repo

Use the same private key file already created locally:

```text
~/.config/aiws/secrets/aiws-release-bot.private-key.pem
```

Set secrets:

```bash
gh secret set AIWS_RELEASE_APP_ID \
  --repo owner/repo \
  --body "<app-id>"

gh secret set AIWS_RELEASE_APP_PRIVATE_KEY \
  --repo owner/repo \
  < ~/.config/aiws/secrets/aiws-release-bot.private-key.pem
```

Verify:

```bash
gh secret list --repo owner/repo
```

Expected secret names:

```text
AIWS_RELEASE_APP_ID
AIWS_RELEASE_APP_PRIVATE_KEY
```

## Release Workflow Test

### 6. Find the plugin ID in the target repo

Read `.claude-plugin/marketplace.json` in the target repo and use the exact plugin ID from that file.

### 7. Run the release workflow

```bash
gh workflow run "AIWS Release Plugin" \
  --repo owner/repo \
  -f plugin_id=<plugin_id> \
  -f bump_type=patch
```

### 8. Watch the run

```bash
gh run list --repo owner/repo --workflow "AIWS Release Plugin" --limit 1
gh run watch <run-id> --repo owner/repo --exit-status
```

### 9. Review the resulting PR

Expected:

- PR author is `app/aiws-release-bot`
- PR title is `Release <plugin_id> <new_version>`
- PR branch is `aiws/release/<plugin_id>/<new_version>`
- plugin manifest version changes
- plugin contract version changes when present
- `.claude-plugin/marketplace.json` plugin entry version changes
- no direct push to the default branch

## Likely Failure Modes

- the repo is not actually an AIWS marketplace/plugin repo
- the GitHub App is not installed on the target repo
- the repo secrets are missing
- the wrong `plugin_id` is passed
- plugin metadata is already in drift before the workflow starts
- the operator lacks repo admin rights to install the app or set secrets

## Reporting Template

Use this exact structure when reporting the result:

```text
Repo: owner/repo
Scaffold install: PASS/FAIL
Scaffold check: PASS/FAIL
GitHub App installed: yes/no
Repo secrets configured: yes/no
Workflow run URL: <url>
Workflow result: PASS/FAIL
Release PR URL: <url or none>
Release PR author: <value>
Branch: <value>
Direct push to default branch: yes/no
Notes: <brief note>
```

## Next Step After PASS

If this second repo passes, the next milestone is not more one-off testing. The next milestone is to turn this into the documented standard path for participating repos:

- repo is AIWS-shaped
- scaffold is installed
- GitHub App is installed
- secrets are present
- release workflow is live

At that point, the scaffold can be treated as reusable across first-class hosts rather than as a single-repo proof.

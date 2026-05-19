# AIWS Empty Repo Bootstrap Handoff

**Date:** 2026-05-18  
**Target repo:** `owner/repo`  
**Operator identity:** `kangsasha` on the local machine  
**Source-of-truth scaffold repo:** `sashakang/ai-workspace`  
**Goal:** prepare an empty repo to be AIWS-ready without inventing plugins that the repo does not yet own

## Summary

This is an empty bootstrap, not a release proof.

The repo is currently empty. That means it cannot yet prove the reusable AIWS release workflow, because the workflow requires a real `plugin_id` from `.claude-plugin/marketplace.json`.

What this handoff does prove is narrower and still useful:

- the repo can receive the reusable AIWS scaffold
- the repo can receive the maintainer runbook
- the GitHub App can be installed on the repo
- the required repo secrets can be configured
- the repo can be marked AIWS-ready for future plugin creation

It does **not** prove release readiness yet, because there is nothing in the repo to release.

## Architecture Boundary

This bootstrap is host-agnostic.

`Cowork`, `Claude Code`, and `Codex` are first-class hosts in the target architecture. None of them should be a dependency of the repo bootstrap itself. The reusable part is:

- repo scaffold
- maintainer runbook
- GitHub App installation
- repository secrets

The host used to apply the bootstrap can be any first-class host or plain local terminal. In this handoff, the operator will run it from the local machine.

## What Counts As PASS

This empty bootstrap is a PASS only if all of the following are true:

- the scaffold files are added to the empty repo cleanly
- the scaffold check passes
- the GitHub App is installed on the repo
- the required repo secrets are configured
- the repo remains honest about having no plugins yet
- no fake marketplace entries, fake plugins, or copied public infrastructure plugins are created just to satisfy the scaffold

After that, the repo can be described as:

```text
AIWS-ready bootstrap complete
release workflow not yet testable because no plugins exist
```

## Important Non-Goals

Do **not** do any of the following in this bootstrap:

- do not copy `core-aiws` into the closed repo
- do not invent a fake domain plugin just to make the workflow runnable
- do not add `.claude-plugin/marketplace.json` unless the repo is actually ready to own real plugin entries
- do not claim release readiness
- do not claim marketplace readiness

This repo should only contain plugins it truly owns.

## Local Operator Flow

### 1. Clone the target repo locally

```bash
cd ~/Documents
git clone https://github.com/owner/repo.git
```

If the clone already exists, reuse it.

### 2. Confirm the repo is empty

```bash
cd ~/Documents/repo
git status
find . -maxdepth 3 \( -name marketplace.json -o -name plugin.json -o -name "*.contract.json" -o -name SKILL.md \)
```

Expected result:

- no AIWS plugin assets
- empty repo or near-empty repo state

### 3. Copy only the scaffold-owned files

From the source-of-truth repo, copy these files into the target repo:

```text
.github/workflows/aiws-release-plugin.yml
docs/aiws-maintainer-release-runbook.md
```

These are the current scaffold-owned files.

Because the target repo is empty and does not yet contain the AIWS helper scripts, do **not** rely on running `python -m scripts.aiws_repo_scaffold install` inside the empty repo. Instead, copy the owned files from the canonical scaffold repo in a controlled way.

Current canonical source paths:

```text
/Users/athanasios/Documents/ai-workspace/.github/workflows/aiws-release-plugin.yml
/Users/athanasios/Documents/ai-workspace/docs/aiws-maintainer-release-runbook.md
```

### 4. Commit and push the scaffold

```bash
cd ~/Documents/repo
git add .github/workflows/aiws-release-plugin.yml docs/aiws-maintainer-release-runbook.md
git commit -m "chore: add AIWS repo scaffold"
git push origin <default-branch>
```

Use the actual default branch, usually `main` or `master`.

## GitHub App Setup

Reuse the existing GitHub App:

```text
App ID: <app-id>
```

Install the app on:

```text
owner/repo
```

Required repository permissions:

- `Contents: Read and write`
- `Pull requests: Read and write`

Do not create a second app unless there is a policy reason to isolate credentials.

## Repo Secret Setup

Use the same local private key file:

```text
~/.config/aiws/secrets/aiws-release-bot.private-key.pem
```

Set the repo secrets:

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

## How To Describe The Result Honestly

If all steps above succeed, the correct status is:

```text
Repo bootstrap: PASS
Repo release proof: NOT RUN
Reason: no plugins exist in the repo yet
```

That wording matters. It keeps the evidence clean.

## Reporting Template

Use this exact structure:

```text
Repo: owner/repo
Repo empty at start: yes/no
Scaffold files added: yes/no
Scaffold commit pushed: yes/no
GitHub App installed: yes/no
Repo secrets configured: yes/no
Release workflow tested: no
Reason release workflow not tested: no plugin_id / no marketplace plugin entries yet
Final status: PASS / FAIL / BLOCKED
Notes: <brief note>
```

## Next Step After PASS

After the empty bootstrap passes, the next valid milestone is to add the first real plugin that this repo actually owns.

Only after that should anyone run the release workflow proof.

The sequence is:

1. empty bootstrap
2. first real plugin added to repo
3. `.claude-plugin/marketplace.json` created with real plugin entry
4. release workflow proof
5. optional downstream host verification in Cowork, Claude Code, or Codex

# AIWS <org> Bootstrap Status

**Date:** 2026-05-19  
**Target repo:** `owner/repo`  
**Operator context used:** `kangsasha` on the local machine  
**Scope:** empty AIWS repo bootstrap, not release proof

## Summary

The empty bootstrap progressed successfully through repo preparation and secret setup, then stopped at the expected tenancy boundary.

The repo is now scaffolded and AIWS-ready at the repository level, but it is not release-testable yet for two separate reasons:

1. the repo is still empty and contains no AIWS plugin entries
2. `kangsasha` cannot install a GitHub App into the `<org>` org/repo context

This is not a scaffold failure. It is an honest blocked state.

## What Was Completed

- Confirmed `owner/repo` was empty at the start.
- Did **not** add fake marketplace, plugin, contract, or skill files.
- Added only the scaffold-owned files:

```text
.github/workflows/aiws-release-plugin.yml
docs/aiws-maintainer-release-runbook.md
```

- Scaffold commit was pushed to the target repo:

```text
<scaffold-sha> chore: add AIWS repo scaffold
```

- Scaffold check passed:

```text
missing: []
changed: []
```

- Repo secrets were configured successfully on the target repo.

## Current Repo State

Correct current description:

```text
Repo bootstrap: materially complete
Release proof: not run
Reason: no plugin_id / no marketplace plugin entries yet
```

The repo remains intentionally empty except for scaffold files. That is correct for this phase.

## GitHub App Findings

### Existing app

The existing AIWS release app owned outside the corporate repo context was not usable for `owner/repo`.

Observed blocker:

- the app was installed only in the `sashakang` context
- GitHub returned a repo/org installation boundary when trying to use it for the `<org>` repo

### New app created under `kangsasha`

A new GitHub App was created successfully under `kangsasha`:

```text
App name: <app-name>
App ID: <app-id>
Owner: @kangsasha
```

Private key generation was understood and is available for this app.

However, under `Install App`, no `<org>` repos were available as installation targets.

This means:

```text
kangsasha can own a GitHub App
kangsasha cannot install that app into the <org> org/repo context
```

That is the current hard blocker.

## Secret Material Actually Used

During repo secret setup, the handoff path did not contain the expected key file. The working key file that was found and used was:

```text
~/.config/aiws/secrets/<app>.private-key.pem
```

This confirms the private key material was valid enough for secret-setting operations, but it does **not** remove the org-level app installation blocker.

## Final Status

Use this status wording:

```text
Repo: owner/repo
Repo empty at start: yes
Scaffold files added: yes
Scaffold commit pushed: yes
Scaffold check: PASS
Repo secrets configured: yes
GitHub App installed on target repo: no
Release workflow tested: no
Reason release workflow not tested: no plugin_id / no marketplace plugin entries yet
Primary blocker: <org> org/repo app-install permission boundary
Final status: BLOCKED
```

## What Needs To Happen Next

The next step is not more local coding work.

The next step requires an `<org>` org or repo admin to do one of these:

1. install an approved GitHub App on `owner/repo`
2. or create and own a new GitHub App in an `<org>`-controlled context, then install it on that repo

Required app repository permissions:

- `Contents: Read and write`
- `Pull requests: Read and write`

Only after that blocker is cleared does the repo become fully AIWS-ready from the credential/install perspective.

## What Must Not Be Done

Do not unblock this by:

- copying `core-aiws` into the closed repo
- inventing a fake plugin just to run the release workflow
- inventing a fake marketplace entry
- claiming release-readiness before the app-install boundary is solved

## Next Milestones After The Blocker Is Cleared

The correct continuation order is:

1. clear the `<org>` GitHub App install boundary
2. keep the repo empty if no real plugin is ready yet
3. when the first real plugin exists, add real marketplace/plugin metadata
4. only then run the release workflow proof on this repo

Until step 3 happens, this repo is bootstrap-ready, not release-proven.

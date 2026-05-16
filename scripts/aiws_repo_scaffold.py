from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKFLOW = """name: AIWS Release Plugin

on:
  workflow_dispatch:
    inputs:
      plugin_id:
        description: "Plugin id from .claude-plugin/marketplace.json"
        required: true
        type: string
      bump_type:
        description: "SemVer bump type. Leave blank when explicit_version is set."
        required: false
        type: choice
        options:
          - ""
          - patch
          - minor
          - major
      explicit_version:
        description: "Explicit MAJOR.MINOR.PATCH version. Leave blank when bump_type is set."
        required: false
        type: string

permissions:
  contents: read

concurrency:
  group: aiws-release-${{ inputs.plugin_id }}
  cancel-in-progress: false

jobs:
  prepare-release-pr:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout read-only
        uses: actions/checkout@v4
        with:
          persist-credentials: false

      - name: Validate current plugin state
        run: python -m scripts.aiws_release validate --plugin-id "${{ inputs.plugin_id }}"

      - name: Prepare release metadata
        run: |
          set -euo pipefail
          args=(prepare --plugin-id "${{ inputs.plugin_id }}")
          if [ -n "${{ inputs.bump_type }}" ]; then
            args+=(--bump-type "${{ inputs.bump_type }}")
          fi
          if [ -n "${{ inputs.explicit_version }}" ]; then
            args+=(--explicit-version "${{ inputs.explicit_version }}")
          fi
          python -m scripts.aiws_release "${args[@]}" | tee aiws-release-result.json

      - name: Validate updated plugin state
        run: python -m scripts.aiws_release validate --plugin-id "${{ inputs.plugin_id }}"

      - name: Build package
        run: python -m scripts.aiws_release package --plugin-id "${{ inputs.plugin_id }}" --output-dir dist/aiws-release

      - name: Check release credential configuration
        env:
          AIWS_RELEASE_APP_ID: ${{ secrets.AIWS_RELEASE_APP_ID }}
          AIWS_RELEASE_APP_PRIVATE_KEY: ${{ secrets.AIWS_RELEASE_APP_PRIVATE_KEY }}
        run: |
          set -euo pipefail
          if [ -z "$AIWS_RELEASE_APP_ID" ] || [ -z "$AIWS_RELEASE_APP_PRIVATE_KEY" ]; then
            echo "::error::Missing AIWS release GitHub App secrets. Configure AIWS_RELEASE_APP_ID and AIWS_RELEASE_APP_PRIVATE_KEY before running this workflow."
            exit 1
          fi

      - name: Create GitHub App token
        id: app-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.AIWS_RELEASE_APP_ID }}
          private-key: ${{ secrets.AIWS_RELEASE_APP_PRIVATE_KEY }}

      - name: Open or update release PR
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PLUGIN_ID: ${{ inputs.plugin_id }}
        run: |
          set -euo pipefail
          version=$(python - <<'PY'
          import json
          import os
          from pathlib import Path
          plugin_id = os.environ["PLUGIN_ID"]
          marketplace = json.loads(Path(".claude-plugin/marketplace.json").read_text())
          print(next(item["version"] for item in marketplace["plugins"] if item["name"] == plugin_id))
          PY
          )
          branch="aiws/release/${PLUGIN_ID}/${version}"
          git config user.name "aiws-release-app"
          git config user.email "aiws-release-app@users.noreply.github.com"
          git checkout -B "$branch"
          python - <<'PY' > /tmp/aiws-release-files
          import json
          from pathlib import Path
          result = json.loads(Path("aiws-release-result.json").read_text())
          for path in result["changed"]:
              print(path)
          PY
          while IFS= read -r path; do
            git add -- "$path"
          done < /tmp/aiws-release-files
          git commit -m "chore: release ${PLUGIN_ID} ${version}"
          gh auth setup-git
          git push --force-with-lease origin "$branch"
          gh pr create \\
            --title "Release ${PLUGIN_ID} ${version}" \\
            --body "Maintainer release PR for ${PLUGIN_ID} ${version}. Merging this PR makes the release metadata available for Cowork marketplace sync." \\
            --base "${{ github.ref_name }}" \\
            --head "$branch" \\
          || gh pr edit "$branch" \\
            --title "Release ${PLUGIN_ID} ${version}" \\
            --body "Maintainer release PR for ${PLUGIN_ID} ${version}. Merging this PR makes the release metadata available for Cowork marketplace sync."
"""


RUNBOOK = """# AIWS Maintainer Release Runbook

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
gh secret set AIWS_RELEASE_APP_ID \\
  --repo owner/repo \\
  --body "<numeric-app-id>"

gh secret set AIWS_RELEASE_APP_PRIVATE_KEY \\
  --repo owner/repo \\
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
gh workflow run "AIWS Release Plugin" \\
  --repo owner/repo \\
  -f plugin_id=aiws-productivity \\
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
"""


OWNED_FILES = {
    ".github/workflows/aiws-release-plugin.yml": WORKFLOW,
    "docs/aiws-maintainer-release-runbook.md": RUNBOOK,
}


def check_scaffold(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    missing: list[str] = []
    changed: list[str] = []
    for relative, expected in OWNED_FILES.items():
        path = repo_root / relative
        if not path.exists():
            missing.append(relative)
        elif path.read_text(encoding="utf-8") != expected:
            changed.append(relative)
    status = "ok" if not missing and not changed else "drift"
    return {"status": status, "missing": missing, "changed": changed}


def install_scaffold(repo_root: Path, *, force: bool = False) -> dict[str, object]:
    repo_root = repo_root.resolve()
    drift = check_scaffold(repo_root)
    changed = list(drift["changed"])
    if changed and not force:
        return {"status": "refused", "missing": drift["missing"], "changed": changed, "written": []}

    written: list[str] = []
    for relative, content in OWNED_FILES.items():
        path = repo_root / relative
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(relative)
    status = "installed" if written else "unchanged"
    return {"status": status, "missing": [], "changed": [], "written": written}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install or check reusable AIWS repo scaffold files.")
    parser.add_argument("command", choices=["install", "check"])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "check":
        result = check_scaffold(args.repo_root)
        print(result)
        return 0 if result["status"] == "ok" else 1
    result = install_scaffold(args.repo_root, force=args.force)
    print(result)
    return 0 if result["status"] != "refused" else 1


if __name__ == "__main__":
    raise SystemExit(main())

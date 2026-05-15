# Cowork Activation UX Gate 1

**Date:** 2026-05-15  
**Status:** APPROVED FOR NEXT SLICE  
**Scope:** regular-user path for using updated skills without manual ZIP handling

## Decision

Do not build a fake local activation path for regular Cowork users.

The normal user journey should be:

```text
edit draft -> validate -> stage proposal -> submit for review -> maintainer merges -> Cowork marketplace update/sync delivers the updated plugin
```

Local package activation remains a technical-pilot and maintainer fallback. It is not the regular-user happy path because current runtime proof shows it can create duplicate visible plugin instances and requires manual upload.

## Current Evidence

AIWS has now validated the Cowork skill-management loop up to review submission:

- marketplace install and skill invocation passed
- installed-source inspection passed
- draft open/edit/validate passed
- accidental parallel draft creation is blocked
- stale draft cleanup passed through `aiws.skills.revert_draft`
- staging and submit-for-review passed

The remaining product gap is what happens after a user changes a skill and wants the updated version to become available in Cowork.

The existing package activation fallback is safe but not product-ready:

- `activate_draft` can build a package and record `pending_upload`
- manual Cowork upload works
- the modified skill can run after upload
- Cowork can expose both original and uploaded copies of the same logical skill
- duplicate visible `plugin_id + skill_id` instances are not acceptable for normal users

## External Research

Official Cowork plugin documentation says users can install plugins from marketplaces or uploaded files, and Cowork checks for updates from the marketplace a plugin came from. It also says Cowork detects local file edits before an update would overwrite them.

Anthropic's organization plugin management documentation describes two supported organization distribution paths:

- manual marketplaces: upload a new ZIP with the same plugin name; the new version overwrites the existing one
- GitHub-synced marketplaces: push changes to the connected repository and trigger sync, or enable automatic sync after PR merge

The same documentation says GitHub sync replaces all plugins in the marketplace with the current repository state. This is the closest supported mechanism to "update the plugin in place" without asking normal users to handle ZIP files.

Sources:

- [Install plugins - Claude.ai Documentation](https://claude.com/docs/cowork/guide/plugins)
- [Manage Claude Cowork plugins for your organization](https://support.claude.com/en/articles/13837433-manage-cowork-plugins-for-your-organization)

## Options Considered

### Option A: Keep Manual ZIP Upload As Normal Activation

Rejected.

Manual upload is validated, but it is a fallback. It asks regular users to handle package files and can leave duplicate visible skills.

### Option B: Copy ZIPs To `package_uploads` And Call That Activation

Rejected.

AIWS can safely copy a package to a writable package-upload surface, but there is still no proof that Cowork watches that folder, imports packages from it, or replaces the active plugin. Copying a ZIP is a handoff, not activation.

### Option C: Use Cowork Marketplace Update/Sync As The Normal Delivery Path

Approved.

This matches Cowork's documented model. The user edits and submits in Cowork. Maintainers review and merge. Cowork then receives the updated plugin through marketplace update/sync under the same plugin identity.

For Team and Enterprise customers, the preferred path is a GitHub-synced organization marketplace with automatic sync enabled when the customer is ready. Manual marketplace upload with the same plugin name remains a maintainer/admin fallback.

### Option D: Full Programmatic Runtime Activation

Future work.

Only implement when Cowork exposes a supported API, connector, or documented package-intake behavior that can prove the modified package became active without duplicate visible identities.

## Approved Next Slice

Build the update-after-merge path, not local runtime replacement.

The next implementation should add Cowork-facing status and guidance for proposals after submission:

1. A proposal submitted for review remains tied to its source plugin and target repo.
2. After maintainer merge, AIWS should report that the update must be delivered by marketplace sync/update.
3. For GitHub-synced organization marketplaces, AIWS should guide maintainers to trigger Cowork marketplace update or rely on automatic sync if enabled.
4. For manual marketplaces, AIWS should guide maintainers/admins to upload a package with the same plugin name so Cowork overwrites the old version.
5. AIWS must keep local draft activation as a technical-pilot fallback and label it clearly.

## Non-Goals

Do not:

- edit Cowork RPM/runtime files
- patch installed marketplace or organization plugin folders
- write into `~/.claude`
- claim a local package copy is active
- hide duplicate skills by mutating Cowork state
- ask regular users to choose a GitHub reviewer
- ask regular users to upload ZIP files in the happy path
- require normal users to install Python, `uvx`, or `gh`

## Acceptance Criteria

The next slice passes when:

- the testing manual separates the normal review/merge/sync path from the technical-pilot manual upload path
- proposal status text tells the user what happens after merge in plain language
- maintainer/admin guidance says how the updated plugin reaches Cowork:
  - GitHub-synced marketplace update/sync for organization marketplaces
  - same-name ZIP upload for manual marketplaces
- AIWS does not claim local activation unless Cowork confirms visibility and callability through a supported mechanism
- duplicate visible skill instances remain a fail-closed condition or a clearly labeled fallback caveat

## Gate 1 Result

Gate 1 passes for replacing the regular-user "use modified draft locally" goal with the supported Cowork delivery model:

```text
regular user proposes -> maintainer merges -> marketplace update/sync delivers
```

Gate 1 does not approve more work on pretending package handoff is activation. That path stays technical-pilot/fallback only.

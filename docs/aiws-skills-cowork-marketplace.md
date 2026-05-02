# AIWS Skills-Only Cowork Marketplace Architecture

## Summary

Cowork skills distribution is plugin-marketplace based. Memory, local MCP, direct writes to `~/.cowork`, and GitHub-facing workflows for nontechnical users are out of scope for this slice.

Users install plugins, and skills come with those plugins. For the skills-management flow, users install `core-aiws` and whichever domain plugin they need. They do not install a separate skill-manager plugin.

## Core Identities

- Plugin: the installable Cowork package.
- Skill: a capability inside a plugin.
- Repo: a GitHub-backed marketplace/source for one scope of plugin variants.
- `core-aiws`: the integral AIWS plugin that owns `aiws-improve`.
- `aiws-productivity`: a demo domain plugin that owns `meeting-followup`.

## Cowork Installation

Individual Cowork users may add a public GitHub plugin marketplace repo through Cowork's Personal plugin marketplace flow, where Cowork exposes "Add marketplace from GitHub". This is not arbitrary ZIP or file installation from chat.

Team and Enterprise org owners connect private or internal `github.com` repos through Organization settings > Plugins. Public plugins need individual install, manual upload, or an internal mirror for org-managed rollout.

Example unit marketplace:

```text
github.com/owner/repo
```

Repository layout:

```text
.claude-plugin/marketplace.json
plugins/
  aiws-productivity/
    .claude-plugin/plugin.json
    skills/
      meeting-followup/
        SKILL.md
```

`marketplace.json` includes `name`, `owner`, and `plugins`. Each plugin entry includes `name`, `source`, `version`, and `description`. Each plugin has a matching `.claude-plugin/plugin.json`.

## Scoped Variants

A logical skill is:

```text
plugin_id + skill_id
```

A concrete variant is:

```text
scope + marketplace_repo + plugin_id + skill_id + version_or_commit + integrity_hash
```

The same logical skill may exist in public, company, unit/project, and personal repos. These are scoped variants, not one file belonging to multiple repos.

AIWS catalog and review tooling own duplicate detection. If multiple visible variants share the same `plugin_id + skill_id`, AIWS asks the user or org admin to choose one, or follows an explicit org policy. AIWS must not silently merge variants.

Until a later namespacing design exists, AIWS policy is not to intentionally install multiple variants of the same logical skill into one Cowork profile.

## Modification And Escalation

Organization-managed plugins are read-only for members in Cowork. User changes to those plugins become personal drafts or proposals derived from the installed variant; they do not mutate the managed plugin in place.

`core-aiws` owns the internal skill-management bridge. The bridge handles draft creation, validation, draft package build, draft activation, GitHub update, PR submission, and revert. It is an implementation detail of `core-aiws`, not a user-facing marketplace plugin.

Editable draft files live under:

```text
~/.aiws/plugins/<marketplace-slug>/<plugin-id>
```

The authoritative draft registry lives under:

```text
~/.aiws/state/skill-drafts/
```

If a modified draft is active, Cowork should show one skill identity with a `Modified locally` status. The draft replaces the installed version in the UI/runtime, but the installed package remains available internally as a fallback/cache.

When updating from GitHub and an active modified draft exists, AIWS fails closed and offers only:

```text
keep local modified skill active
discard local changes and update
submit/upload first
```

Users choose targets in product language:

```text
Personal
PNC skills
Company skills
Public skills
```

Direct escalation is allowed from any source to any target, including personal to public.

AIWS backend or a GitHub App handles branches and pull requests behind the scenes. Nontechnical users see status labels such as submitted, reviewing, changes requested, approved, rejected, and published.

## Validation Gates

Before install, update, draft activation, or PR submission, AIWS validates:

- marketplace and plugin manifests
- plugin contracts
- `.mcp.json` files using top-level `mcpServers`
- skill folders using Codex `skill-creator` compatibility rules
- version alignment across marketplace entries, plugin manifests, and contracts

`.mcp.json` files with top-level `servers` fail validation.

Skill folders must include `SKILL.md` with only `name` and `description` frontmatter. The skill folder name must match the frontmatter `name`.

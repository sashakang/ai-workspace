# AIWS Skills-Only Cowork Marketplace Architecture

## Summary

Cowork skills distribution is plugin-marketplace based. Memory, local MCP, direct writes to `~/.cowork`, and GitHub-facing workflows for nontechnical users are out of scope for this slice.

Users install plugins, and skills come with those plugins.

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

Users choose targets in product language:

```text
Personal
PNC skills
Company skills
Public skills
```

Direct escalation is allowed from any source to any target, including personal to public.

AIWS backend or a GitHub App handles branches and pull requests behind the scenes. Nontechnical users see status labels such as submitted, reviewing, changes requested, approved, rejected, and published.

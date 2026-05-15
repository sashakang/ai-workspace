# Cowork Inspected Draft Proposal Submit PASS

**Date:** 2026-05-15  
**Result:** PASS  
**Scope:** Scenario 3, 4, 11, and 12 retest after installed-copy inspection was integrated into draft opening.

## Summary

The regular Cowork proposal path passed with the new installed-source safety check in place.

Cowork opened the draft without an explicit `source_plugin_root`, auto-inspected installed copies of `aiws-productivity:meeting-followup`, found exactly one installed source, edited the draft copy under `~/.aiws/plugins/`, validated it, staged a local proposal, and submitted the proposal to the allowed GitHub test repository.

No installed plugin files, Cowork runtime files, memory files, or `~/.claude` files were mutated.

## Draft Open

```text
draft_id: aiws-productivity--meeting-followup--de0e75a572
draft_path: /Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-de0e75a572
```

Installed-source inspection from `create_or_open_draft`:

```text
inspection.status: ok
inspection.instance_count: 1
inspection.selected_instance.source_plugin_root:
/Users/aleksanderkan/Library/Application Support/Claude/local-agent-mode-sessions/c7686c44-41b4-4505-8b68-b030becb9290/3581ad1d-5821-4080-b19b-b01a25310587/rpm/plugin_01UbGZsu5hJezcVifsV8C75U
duplicate installed copies found: no
```

The draft path was under `~/.aiws/plugins/`, not inside the installed Cowork RPM plugin path.

## Draft Edit And Validation

The edit was made through the AIWS draft system, not the installed RPM plugin.

The active draft for the validated edit was:

```text
draft_id: aiws-productivity--meeting-followup--25bf8e1a23
draft_path: /Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-25bf8e1a23
changed file: skills/meeting-followup/SKILL.md
```

Validation result:

```text
validation status: passed
modified status: true
status label: Modified locally
current_tree_digest: d347ce6087ae3ff52d294ac2be2fcf2eae54196bc4de1515cc2695eabba60d43
validation_tree_digest: d347ce6087ae3ff52d294ac2be2fcf2eae54196bc4de1515cc2695eabba60d43
```

Side effects:

```text
package built: no
proposal staged: no
GitHub touched: no
installed plugin files touched: no
```

## Stage Proposal

```text
status: staged
proposal_id: skillprop_a39b43d759ba440ca93b71e0f528d9b5
draft_id: aiws-productivity--meeting-followup--25bf8e1a23
target_repo: sashakang/aiws-skill-tests
target_scope: Personal test skills
validation_digest: d347ce6087ae3ff52d294ac2be2fcf2eae54196bc4de1515cc2695eabba60d43
```

Staging side effects:

```text
package built: no
branch created: no
commit created: no
push: no
pull request: no
Cowork runtime mutation: no
installed plugin files touched: no
~/.claude touched: no
```

## Submit For Review

Pre-submit gates:

```text
validation/digest gate passed: yes
repository allowlist gate passed: yes
```

Submit result:

```text
submit status: submitted_for_review
proposal_id: skillprop_a39b43d759ba440ca93b71e0f528d9b5
target_repo used: sashakang/aiws-skill-tests
branch_name: aiws/skill-proposals/skillprop_a39b43d759ba440ca93b71e0f528d9b5
pr_url: https://github.com/sashakang/aiws-skill-tests/pull/4
proposal status changed staged -> submitted: yes
```

Submit side effects:

```text
package built: no
Cowork runtime mutation: no
installed plugin files touched: no
~/.claude touched: no
errors / manual follow-up: none
```

## Interpretation

This confirms the regular-user proposal path works after source inspection became part of draft opening:

1. AIWS identifies the installed source before draft work.
2. AIWS fails closed if duplicate installed copies are found.
3. The user edits only the draft copy.
4. Validation records a digest.
5. Staging writes only a local proposal record.
6. Submit revalidates and creates a PR only after the digest and repository gates pass.

This does not solve activation UX. It confirms the review/proposal path is stable.

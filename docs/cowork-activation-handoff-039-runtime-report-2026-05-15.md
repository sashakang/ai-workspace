# Cowork Activation Handoff 0.3.9 Runtime Report

**Date:** 2026-05-15  
**Result:** PASS via fallback path; `handoff_prepared` not observed  
**Scope:** Runtime validation of `core-aiws` 0.3.9 activation handoff behavior for `aiws-productivity:meeting-followup`.

## Summary

The `core-aiws` 0.3.9 retest passed through the safe fallback path. Cowork opened and edited a new draft, validated it, built a package, wrote the AIWS pending-upload activation record, and then successfully loaded the manually uploaded modified package in a new Cowork chat.

The new `handoff_prepared` path was not observed in this Cowork environment. `activate_draft` returned `host_capability_missing`, meaning the runtime did not find or use a safe Cowork package-upload surface for automatic handoff. This is still valid behavior for 0.3.9: the implementation must fall back honestly instead of claiming activation.

## Draft And Validation

```text
draft_id: aiws-productivity--meeting-followup--c838a91aa7
draft_path: /Users/aleksanderkan/.aiws/plugins/cowork-upload/aiws-productivity-c838a91aa7
```

The draft edit changed only:

```text
skills/meeting-followup/SKILL.md
```

The added instruction was:

```text
Keep follow-up messages brief and to the point — prefer plain language over jargon so recipients can understand and act without re-reading.
```

Validation passed:

```text
validation status: passed
modified status: true
status label: Modified locally
current_tree_digest: d6a1767df1ada67bd451f2bbac008424f71d665b21b411a327c0685089400ebd
validation_tree_digest: d6a1767df1ada67bd451f2bbac008424f71d665b21b411a327c0685089400ebd
```

No package, proposal, GitHub action, or installed marketplace plugin mutation happened during validation.

## Activation Result

```text
status: host_capability_missing
activation_status: pending_upload
activation_effective: false
requires_manual_upload: true
requires_cowork_confirmation: not returned
package_path: /Users/aleksanderkan/.aiws/tmp/cowork-phase2-packages/aiws-productivity--meeting-followup--c838a91aa7.zip
copied_package_path: not returned
activation_record_path: /Users/aleksanderkan/.aiws/state/draft-activations/cowork-db8a0e250a1c/aiws-productivity--meeting-followup--c838a91aa7.json
host_id: cowork-db8a0e250a1c
```

The activation record path was under:

```text
~/.aiws/state/draft-activations/<host-id>/<draft_id>.json
```

Guard checks:

```text
installed marketplace plugin files touched: no
~/.claude touched: no
Cowork runtime files mutated directly: no
proposal staged: no
GitHub touched: no
```

## Manual Upload Verification

After manually uploading:

```text
/Users/aleksanderkan/.aiws/tmp/cowork-phase2-packages/aiws-productivity--meeting-followup--c838a91aa7.zip
```

a new Cowork chat loaded and ran `meeting-followup`.

Observed result:

```text
uploaded package installed: yes
meeting-followup visible: yes
meeting-followup runs successfully: yes
loaded SKILL.md contains expected test edit: yes
output reflects brief/plain-language instruction: yes
```

The skill loaded from:

```text
/var/folders/ts/qdbqrt412bnb972vcvtqd4x40000gs/T/claude-hostloop-plugins/29e408ad64584ef3/skills/meeting-followup
```

## Caveats

Duplicate `aiws-productivity` registration remains present:

- one RPM instance had the edit
- one RPM instance did not have the edit
- the live skill invocation used a third hostloop path that did contain the edit

`aiws_skills_resolve` could not resolve the installed skill in AIWS metadata, even though the Cowork Skill invocation system could load and run it from disk. This means the modified package is functionally usable in Cowork, but AIWS metadata and Cowork skill invocation are not yet aligned.

## Product Interpretation

```text
CW-08: PASS via fallback path; handoff_prepared not observed
CW-09: PASS after manual upload; duplicate/registry caveats remain
```

This confirms 0.3.9 did not regress the safe fallback path. It also confirms the activation handoff problem is not fully solved in this Cowork environment. The next product work remains: make Cowork activation/update user-friendly, avoid duplicate visible plugin instances, and align AIWS metadata with the skill invocation path.

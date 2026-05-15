# Cowork Modified Draft Upload Report

**Date:** 2026-05-15  
**Result:** PASS, with duplicate-plugin caveat  
**Scope:** CW-09 verification that a package produced from a modified `aiws-productivity:meeting-followup` draft can be uploaded through Cowork and then used from a new Cowork chat.

## Summary

The modified draft package upload path passed. After the package produced by the draft activation flow was uploaded through Cowork, a new Cowork chat could see and run `aiws-productivity:meeting-followup`. The loaded skill reflected the modified instruction that follow-up messages should be clear and concise.

This proves the current manual package-upload bridge works for testing an updated skill in Cowork. It does not prove a clean end-user activation path, because Cowork retained both the original marketplace plugin and the uploaded modified package.

## Setup

The test started from a modified `aiws-productivity:meeting-followup` draft. The modified draft had previously added guidance that follow-up messages should be clear and concise.

The package produced by the draft activation flow was uploaded through Cowork's plugin upload UI. Verification was then run in a new Cowork chat, as required by the testing manual, so Cowork had a chance to refresh plugin and skill visibility.

## Evidence

Cowork found two `aiws-productivity` plugin instances:

- `plugin_01UbGZsu5hJezcVifsV8C75U`: original `aiws-productivity` v0.2.1, without the modified Follow-Up Messages section.
- `plugin_01GuNX3DwSXBLS1dUwPRVccm`: modified uploaded package, with the clear-and-concise Follow-Up Messages instruction.

The skill that actually ran loaded from a Cowork hostloop plugin cache path:

```text
/var/folders/ts/qdbqrt412bnb972vcvtqd4x40000gs/T/claude-hostloop-plugins/29e408ad64584ef3/skills/meeting-followup
```

That loaded `SKILL.md` contained the modified instruction:

```text
clear and concise: one main point per message, no unnecessary filler, and direct language
```

## Invocation

Test input:

```text
Decision: Validate pending-upload draft activation.
Alice will send the revised notes by Friday.
Ben will review them.
```

Observed result:

- `meeting-followup` was visible.
- `meeting-followup` ran successfully.
- The output included the decision to validate pending-upload draft activation.
- The output included Alice's Friday action item.
- The output included Ben's review action item.
- The draft follow-up messages were short, direct, and reflected the modified clear-and-concise instruction.

## Result

```text
uploaded package installed: yes
meeting-followup visible: yes
meeting-followup runs successfully: yes
updated instruction reflected: yes
```

Result: PASS.

## Caveat

`meeting-followup` appeared twice because Cowork had both the original marketplace plugin and the uploaded modified package installed. This is acceptable for the technical pilot, but it is not acceptable as the final regular-user experience.

The next product slice should replace or hide this manual upload/duplicate-plugin behavior behind a user-friendly Cowork activation path. The target experience is that a regular user can test or activate a modified skill without understanding packages, plugin IDs, duplicate installs, or upload mechanics.

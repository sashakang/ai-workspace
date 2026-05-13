# AIWS Cowork Plugin Import Validation PASS

**Date:** 2026-05-11  
**Tester:** Sasha Kang  
**Cowork version/build:** 1.6608.2  
**Account type:** Team  
**Result:** PASS

## Scope

This validates the Cowork-supported ZIP import path, not the GitHub marketplace registration path.

At the time of this 2026-05-11 Team ZIP import test, the Personal marketplace registration path had been blocked in a separate Personal-account test. That historical blocker is recorded in [AIWS Phase 1 Blocked](./aiws-phase1-blocked.md). Marketplace install later became the primary user journey after the user reported that Cowork installed the marketplace plugins and generated `meeting-followup` nodes correctly.

## Import Path

```text
Organization settings -> Plugins -> Add plugin -> Upload a file
```

Cowork action label:

```text
Upload a file
```

Package format tested:

```text
Individual plugin ZIPs
```

Accepted archive layout:

```text
.claude-plugin/plugin.json
skills/
contracts/
README.md
```

## Artifacts Tested

```text
core-aiws-0.3.4.zip
aiws-productivity-0.2.1.zip
```

The multi-plugin bundle was not tested because individual plugin ZIP import worked.

## Install Result

```text
core-aiws: installed and active as plugin_012NpiRCyfQPjKuJfziDqX79
aiws-productivity: installed and active as plugin_01VXEPSTMd236ZFTiBSJbDd1
Marketplace shown by Cowork: My Uploads
Marketplace ID: marketplace_01N6hSbepnJzo9DPKXoFBcps
```

## Skill Visibility

```text
meeting-followup visible: yes
```

Evidence:

```text
meeting-followup loaded from aiws-productivity/skills/meeting-followup/SKILL.md
```

## Invocation Proof

Input:

```text
Create brief meeting follow-up notes from this test meeting: Alice will send the draft by Friday. Ben will review it. The decision was to validate the Cowork plugin import install first.
```

Output summary:

```text
Meeting minutes with a decision, two action items, and a draft follow-up message.

Decision:
Validate the Cowork plugin import install path before proceeding.

Action items:
- Alice: send the draft by Friday.
- Ben: review the draft after Alice delivers.
```

## Safety

```text
~/.claude touched: no
Memory sync commands run: no
RPM files edited manually: no
```

## Logs And Errors

```text
None reported.
```

## Notes

Cowork assigns manually uploaded plugins to a marketplace named `My Uploads`.

This path is a clean Cowork-supported import path for Team accounts because Cowork performs the install through its own UI and no runtime state is edited by hand.

This report does not validate GitHub marketplace registration. It preserves the fallback ZIP import PASS result.

from __future__ import annotations


SOP_RESOURCE = """# Standard Operating Procedure

This is the MCP-first AIWS SOP resource.

Use it to classify work, plan non-lightweight changes, review plans and outputs, test the result, and capture follow-up improvements. AIWS exposes this process through the local MCP server rather than through a required infrastructure plugin.

Core rules:

- classify work before execution
- use a reviewed plan for standard, complex, and maximum tasks
- keep implementation evidence local unless the user explicitly stages a proposal
- route durable workflow changes through local staged proposals before any shared review flow
"""


AIWS_IMPROVE_SKILL = """---
name: aiws-improve
description: Analyze local AIWS signals and stage process, skill, or protocol improvement proposals.
---

# AIWS Self-Improvement

Use this skill when the user asks to analyze accumulated local signals and improve AIWS behavior.

This MCP-first version reads from local AIWS surfaces under `~/.aiws/`, MCP skill/catalog resources, current conversation context, and user-supplied evidence. It may propose changes to skills, protocols, prompts, adapter behavior, or documentation.

## Boundaries

- Do not upload personal skills, memory, transcripts, or staged evidence.
- Do not directly mutate shared, unit, company, or public skills.
- Do not assume installed plugin registries or helper-managed plugin data paths.
- Stage proposed skill changes locally before any future shared review flow.

## Output

Present a concise evidence summary, proposed target, rationale, and the smallest useful change. If the user approves staging, use the AIWS skill-change staging flow.
"""


BUILTIN_SKILLS = {
    "aiws-improve": AIWS_IMPROVE_SKILL,
}


RESOURCES = {
    "aiws://protocols/sop": SOP_RESOURCE,
    "aiws://skills/aiws-improve": AIWS_IMPROVE_SKILL,
}

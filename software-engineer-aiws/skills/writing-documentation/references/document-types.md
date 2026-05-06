# Document Types

Choose the smallest document type that satisfies the reader's need.

## Diataxis Shapes

Use this structure when the documentation set is large enough to separate learning, task execution, lookup, and understanding.

- Tutorial: teaches by walking through a complete learning path. Optimize for a successful first experience, not exhaustive coverage.
- How-to guide: helps a reader complete a real task. Use imperative steps, prerequisites, expected result, and troubleshooting notes.
- Reference: lets a reader look up precise facts. Optimize for completeness, consistency, stable headings, and examples of valid values.
- Explanation: helps a reader understand why the system works the way it does. Use context, trade-offs, constraints, and design reasoning.

Do not force every repo into four folders. For small projects, use the shapes inside a compact `README.md` or `docs/` page.

## Common AIWS Document Types

- README: orient the reader. Cover what this component is for, when to use it, where to start, and where deeper docs live.
- Runbook: tell an operator how to detect, diagnose, mitigate, and verify an operational situation.
- Architecture note: describe current or target structure, boundaries, trade-offs, and failure modes.
- ADR: record a decision, context, options considered, final choice, consequences, and date.
- Skill documentation: give an agent the concrete workflow, references, validation rules, and boundaries it needs for one reusable capability.
- Contract documentation: state interface fields, invariants, compatibility expectations, and failure behavior.

## Selection Rules

- If the reader asks "how do I do X?", write a how-to.
- If the reader asks "what is X?", write reference.
- If the reader asks "why is X this way?", write explanation.
- If the reader is new and must learn the path, write a tutorial or README section.
- If the reader is operating or recovering a system, write a runbook.
- If the doc will guide future agents, write explicit triggers, workflow steps, file boundaries, and verification rules.

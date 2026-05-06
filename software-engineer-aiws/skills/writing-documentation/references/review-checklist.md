# Review Checklist

Use this checklist for documentation reviews and final self-review.

## Accuracy

- The document matches current code, schemas, contracts, or configuration.
- Target-state or planned behavior is labeled as such.
- Commands use the right working directory and flags.
- Version-sensitive or date-sensitive claims are current or caveated.
- Examples are realistic and do not include secrets.

## Reader Fit

- The intended reader is clear.
- The document answers one main need.
- Prerequisites and assumptions are explicit.
- The first section helps the reader decide whether the page is relevant.
- Troubleshooting or caveats cover likely failure points.

## Structure

- Headings are ordered and stable.
- Steps are numbered only when sequence matters.
- Reference material is scannable.
- Links point to canonical sources.
- Duplicated or stale sections are removed or clearly archived.

## AIWS Fit

- AIWS plugin, skill, contract, and marketplace boundaries are described correctly.
- Memory behavior does not imply automatic shared writes.
- Skill docs follow progressive disclosure.
- AIWS skill folders contain no unsupported clutter files.
- Packaging changes pass the existing release validation gate.

## Handoff

For a review, report findings first, ordered by severity. For an edit, summarize changed files and verification. If checks were skipped, state the gap plainly.

# Style And Quality

Use the local project's existing style first. Apply these rules when the project does not define something more specific.

## Writing Style

- Write plainly and directly.
- Prefer short paragraphs over long blocks.
- Use active voice and present tense.
- Use concrete nouns and verbs.
- Avoid marketing language, vague benefit claims, and filler.
- Avoid unexplained jargon. If a technical term is required, define it once.
- Use exact dates when relative time could become stale.
- Use placeholders only when they make the example safer or reusable. Name placeholders clearly.

## Structure

- Start with what the reader needs to know or do.
- Put prerequisites before steps.
- Put expected results after steps.
- Keep headings hierarchical and stable.
- Use numbered lists only for ordered steps.
- Use tables only when comparison or lookup is easier than prose.
- Link to canonical docs instead of restating common external material.

## Code And Commands

- Use fenced code blocks with a language tag when possible.
- Prefer copyable examples that work from the documented working directory.
- Do not include secrets, tokens, private URLs, or environment-specific values.
- State whether a command is read-only, writes files, starts a service, or changes remote state when that matters.
- For generated output, show only the lines needed to explain the result.

## Accuracy

- Read the implementation before documenting behavior.
- If docs and code disagree, treat the code, tests, contracts, and schemas as evidence. Surface the mismatch instead of silently guessing.
- Do not preserve stale docs because they sound polished.
- Prefer a small accurate document over a large speculative one.
- Keep docs changes in the same change as related code when practical.

## Links

- Prefer relative links for repository-local files.
- Check renamed headings for inbound anchor links.
- Use descriptive link text.
- Avoid bare "click here" links.
- Remove links to dead or superseded pages when replacing content.

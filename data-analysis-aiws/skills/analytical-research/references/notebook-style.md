# Notebook Style

Rules for keeping analytical notebooks observable and maintainable.

## Code must stay observable

- No large all-purpose objects (no single `analysis` object that hides reasoning)
- No class-like notebook structure
- No abstractions unless reused 3+ times
- No hidden logic in external scripts that the notebook only imports
- Intermediate outputs shown, not only final outputs
- The notebook must allow the user to observe thinking and intervene in real time

## Allowed minimal helpers

These are permitted because they are mechanical and repeated:

- Query runner (execute + return dataframe)
- Cache loader/saver (load cached result or run query)
- Chart export helper (save figure to file)
- A repeated routine ONLY if reused 3+ times and would otherwise create noise

## Query caching

- Cache query results locally when rerunning similar notebook states
- Make cache usage explicit in the notebook
- Cache signature: query text + parameters + source identifiers + as-of date + freshness mode
- Store a cache timestamp with each cached result
- Show visible cache hit/miss message including timestamp
- Invalidate when query text, parameters, sources, as-of date, freshness mode, or explicit user refresh changes
- Avoid unnecessary repeat queries during formatting-only or wording-only passes

## Code placement

- Code lives next to its output and reasoning
- No "utility cell" blocks at the top that hide analytical logic
- Imports and config at the top are fine
- Helper definitions (if any) go in a clearly labeled early cell, not scattered

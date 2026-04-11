# Bootstrap Prompt

Use this prompt in Claude Code after loading `core-aiws`, `memory-aiws`, and `data-analyst-aiws`:

```text
Validate that the three inline plugins are loaded: core-aiws, memory-aiws, and data-analyst-aiws.
Then check that the data-analyst-forecast skill is available, inspect the analyst plugin contract,
and summarize what environment variables or local MCP configuration are still required before real forecasting work can begin.
Do not assume any credentials are present. Report missing prerequisites explicitly.
```

# Token and budget diagnostics

The assistant panel exposes server Token telemetry under:

```text
展开 Developer 诊断
  → Token 与预算
```

The card shows the model, input/output/total Token counts, known cumulative
usage, configured turn limit, LLM and tool call counts, provider reporting
completeness, output-cap enforcement capability, budget status, and an explicit
block reason when present.

The client accepts only typed `token_usage` messages. Invalid numeric fields,
stale connection generations, and summaries belonging to another session are
ignored or rejected without changing the active runtime state.

The telemetry payload never includes prompt text, credentials, tool arguments,
or tool results.

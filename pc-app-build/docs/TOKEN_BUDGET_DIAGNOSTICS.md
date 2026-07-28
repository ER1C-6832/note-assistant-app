# Token and budget diagnostics

## Layered request path

Developer 诊断中的“Token、路径与预算”会明确显示：

- `普通聊天（无工具）`：服务端没有向模型发送任何工具 Schema。
- `工具请求（候选工具）`：显示可用工具数、实际候选数和候选 Schema 字符数。
- 当前 chat/tool 独立预算、供应商实际输入/输出 Token、模型调用与真实工具调用次数。

普通聊天如果显示候选工具数大于 0 或 Schema 字符数大于 0，应视为回归错误。
工具结果总结应在服务端日志中显示 `purpose=tool_followup`、
`tool_count=0`、`tool_schema_chars=0`。

The assistant panel exposes server Token telemetry under:

```text
展开 Developer 诊断
  → Token、路径与预算
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

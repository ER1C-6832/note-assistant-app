# ADR-009: In-process Xiaozhi MCP Tool Runtime

状态：Accepted for Gate 5 implementation; Real acceptance pending

## Context

旧实现通过外部 py-xiaozhi 集成、HTTP Notes API 或 Sidecar 转发工具调用。它可以验证概念，但产生第二进程、重复状态、额外 sender、跨进程错误语义和 UI 同步困难。Android 工具面还包含 PC 领域模型不存在的 archive、done、revision 和 tag rename。

## Decision

PC 端固定使用单进程 MCP runtime：

```text
Real/Fake transport
-> one private JSON-RPC queue and worker
-> one ToolRegistry with 31 descriptors
-> Gate53ToolExecutor
-> NoteCommandService / NoteQueryService / TagCatalogService / UiCommandBus
-> one existing WebSocket sender
```

工具描述承载服务端意图路由规则；客户端只做确定性的 query 归一化，不实现本地 NLP 执行器。含糊 mutation 必须先 resolve，多个候选零写入。高风险 mutation 只能通过 bounded、session/generation-bound、single-use PendingConfirmationService 执行。

## Consequences

正面：

- Fake 与 Real 使用同一 executor；
- 无 Sidecar、HTTP localhost 服务或第二 sender；
- 32 个工具名、schema、风险和确认策略可冻结；
- UI、数据库和确认状态拥有明确关闭顺序；
- descriptor 可增强口语路由而不破坏领域边界。

代价：

- 服务端模型是否选对工具仍需真实语音验收；
- PC 不广告 Android 的 8 个额外工具；
- 真实 32-tool 场景较长，采用用户自由表达的手工记录器而非固定 prompt runner。

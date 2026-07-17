# Gate 5 Implementation Plan

状态：实施候选  
阶段数量：**5 个子阶段**。不得为了交付方便继续拆成 6～10 个零碎 Gate。

## 1. 总体顺序

```text
Gate 5.0  Protocol core + registry
Gate 5.1  Read / resolve + UI navigation
Gate 5.2  Note / tag mutations
Gate 5.3  Confirmation + high-risk closure
Gate 5.4  Cumulative + Real + freeze
```

每个子阶段都必须继续运行 Gate 1 through 当前 Gate 的累计测试。前一阶段退出条件未满足，不进入下一阶段真实写链路。

## 2. Gate 5.0：协议内核与 31-tool registry

### 目标

把当前 fail-closed 的 MCP envelope 升级为真实、私有、有界、可响应的 JSON-RPC 路径；31 个 descriptor 全部可发现，但尚未完成的 handler 必须明确 blocked/not_ready，不能假成功。

### 主要工作

- 建立 `assistant/mcp/` 模块；
- typed JSON-RPC request/notification/response/error；
- `initialize`、`notifications/initialized`、`tools/list`、`tools/call`；
- 31 个稳定 descriptor、JSON Schema、risk、mutation、confirmation metadata；
- bounded request queue、single worker、dedupe cache、canonical fingerprint；
- Real transport response sink 复用现有 sender；
- sanitized lifecycle event 投影到 AssistantController；
- Fake transport 支持完整 MCP request/response；
- oversized、unknown method/tool、invalid params、queue overflow fail-closed；
- MCP coordinator 的 start/close/reconnect generation ownership；
- Bootstrap 注入 executor；executor 缺失时 fail-closed。

### 推荐新增文件

```text
app/assistant/mcp/
├─ __init__.py
├─ contracts.py
├─ jsonrpc.py
├─ descriptors.py
├─ registry.py
├─ coordinator.py
├─ queues.py
├─ idempotency.py
├─ result_mapper.py
└─ testing.py
```

名称可调整，但所有权不能散落在 router、controller 和 tool handler 三处。

### 退出条件

- Fake initialize/list/call response 通过；
- `tools/list` 精确 31 names，无 8 个 unsupported names；
- duplicate in-flight call 只执行一次；
- receiver 不等待 handler；
- response 只走一个 sender；
- shutdown/reconnect 无 MCP task/future；
- Real protocol probe 能完成 initialize + tools/list，尚不执行 mutation。

## 3. Gate 5.1：读取、目标解析与 UI 导航

### 工具范围：15

Read/resolve：

```text
notes.resolve
notes.search
notes.list_recent
notes.get
notes.list_by_tag
notes.list_deleted
notes.list_todos
notes.list_pinned
```

UI：

```text
ui.open_note
ui.show_search
ui.show_note_list
ui.show_tag
ui.show_trash
ui.show_pinned
ui.show_confirmation
```

`ui.show_confirmation` 此阶段只验证 bus/display contract；没有有效 pending 时返回 blocked。真实确认闭环在 5.3。

### 主要工作

- 扩展 `NoteQueryService` 的 recent/filtered bounded query；
- 实现 resolver：exact id/title 优先，模糊结果返回 candidates；
- ambiguous target 永不自动 mutation；
- 搜索/列表 result 截断和 32 KiB output budget；
- `UiCommandBus` protocol、Qt adapter、generation-safe dispatch；
- UI open/search/tag/trash/pinned/navigation；
- UI unavailable、stale selection、note deleted 等安全错误；
- Read tool 也产生 sanitized audit；
- Real text call 验证 search/get/list + UI navigation。

### 退出条件

- 8 个 read/resolve 工具真实返回当前数据库数据；
- 7 个 UI 工具不直接导入/调用 QML；
- “刚才那条”只能在唯一候选时解析；
- deleted 不混入 active search；
- `待办` 使用 protected tag 语义；
- 多候选时零 mutation；
- UI 切换无需重启 App。

## 4. Gate 5.2：便签与标签 mutation

### 工具范围：13

Note mutation：

```text
notes.create
notes.append
notes.update_title
notes.replace_content
notes.convert_type
notes.pin
notes.delete
notes.restore
```

Tags：

```text
tags.create
tags.search
tags.list
tags.delete
tags.bind
```

本阶段实现 handler、service boundary 和 Fake behavior。高风险分支必须返回 `requires_confirmation`，实际 confirm 执行留到 5.3。

### 主要工作

- note tool handlers 只调用 Command/Query services；
- `source=VOICE_PC`；
- append/title/convert 根据当前快照构造 `UpdateNoteCommand`；
- 新增 all-or-nothing 批量 tag binding application command；
- 新增 `TagCatalogService` 并让 UI/MCP 共用；
- create/update/bind 后 observe tags；
- mutation 成功触发 NotesViewModel/tag sidebar refresh；
- write idempotency、same-id/different-payload conflict；
- business/domain errors 映射为 safe ToolResult；
- high-risk preview 生成但不执行；
- UI refresh failure 与 committed mutation 分开报告。

### 退出条件

- create/append/title/convert/pin/restore 小批量 Fake 和本地集成通过；
- tags create/search/list 和小批量 bind 通过；
- replace/delete/tags.delete/bind replace 在无确认时零写入；
- duplicate create 只产生一个 note；
- batch tag bind 失败整体回滚；
- UI 与数据库最终一致；
- 无 TagCatalog 并发覆盖写。

## 5. Gate 5.3：确认与高风险闭环

### 工具范围：3 confirmation + high-risk completion

```text
assistant.confirm
assistant.reject
assistant.list_pending_confirmations
```

完成以下高风险路径：

```text
notes.replace_content
notes.delete
notes.pin (>5)
notes.restore (>5)
tags.bind replace / >5
tags.delete
```

### 主要工作

- bounded PendingConfirmationService；
- 120s TTL、capacity 32、single-use；
- command fingerprint、session/generation、targets、preview binding；
- voice confirm 与 local UI confirm 共用同一 pending object；
- reject/expire/disconnect/disable/shutdown 零 mutation；
- confirm 时重新读取并验证目标；
- confirmation race：confirm/reject/expiry 同时到达只 finalize 一次；
- repeated confirm 返回 consumed，不重放 command；
- `ui.show_confirmation` 真正展示 pending；
- real voice/text “删除 -> 拒绝”与“删除 -> 确认”验证。

### 退出条件

- confirmation 前数据库字节级/查询结果不变；
- confirm/reject race 只产生一个终态；
- expired/stale/cross-session confirm 拒绝；
- delete 只软删除；
- replace content 只修改指定字段；
- pending capacity/TTL/cleanup 通过；
- AssistantState/log 不含 preview 原始正文。

## 6. Gate 5.4：累计、真实验收与冻结

### 目标

在当前 Windows 目标工作树和真实 endpoint 上完成 31 工具发现、完整 CRUD、标签、UI、确认、去重和资源终态签字。

### 必须完成的 Real scenario

```text
tools/list == 31
-> create normal note
-> create todo note
-> list_recent / resolve / search / get
-> append
-> update_title
-> convert normal <-> todo
-> tags create/search/list/bind
-> pin
-> UI open/search/tag/pinned
-> delete -> reject (zero mutation)
-> delete -> confirm (soft deleted)
-> show trash / list_deleted
-> restore
```

另外执行：

- duplicate request id；
- same id/different args；
- disconnect during read/write/pending confirmation；
- queue overflow；
- invalid/oversized JSON；
- mode switch、disable、shutdown；
- reconnect 后不自动 replay；
- UI unavailable；
- TagCatalog concurrent UI/MCP access。

### 文档收口

- 新增 `docs/report/GATE5_0...GATE5_4_IMPLEMENTATION_REPORT.md`；
- 新增 `docs/report/GATE5_FINAL_ACCEPTANCE_REPORT.md`；
- 新增 `docs/adr/ADR-009-in-process-xiaozhi-mcp-tool-runtime.md`；
- 将本规格并回 Master Plan amendment；
- 更新真实进度表；
- 修正 README 中 MCP/KWS/barge-in 的未来完成式描述；
- 在最终报告记录真实 JSON 摘要和人工验收结果，不只列命令。

### 最终退出条件

- Automated、Fake、Real 全部返回 0；
- 31 tools 均有 descriptor + handler + contract test；
- 8 unsupported tools 不出现在 list；
- Real CRUD/tag/UI/confirm scenario 通过；
- resource terminal matrix 全零；
- Gate 5 标记 Accepted 后才进入后续体验 Gate。

## 7. 实施纪律

- 不从 Android 复制 Kotlin 实现；只复用工具名、风险语义和行为契约；
- 不从旧 master 复制 `NotesApiClient`、Sidecar、全局 `_CONTEXT` 或 py-xiaozhi decorator；
- 不以 source assertion 测试替代行为测试；
- 不把 README 声明当通过证据；
- 不把 Fake pass 当 Real pass；
- 不在报告中写入 token、完整 identity、note content 或原始 MCP arguments；
- 不生成外部 MCP server 进程；
- 不在当前 Gate 引入 archive/done/revision 以凑齐 Android 39。


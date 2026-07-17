# Gate 5 MCP Notes Tools Specification

状态：实施候选（Implementation Candidate）  
目标：在 PC 单进程 Runtime 中完成 31 个 Xiaozhi MCP 工具的真实闭环。  
非目标：通过增加第二进程、Sidecar、HTTP 服务或伪实现追求工具数量。

## 1. 成功定义

Gate 5 完成后的真实链路：

```text
Xiaozhi WebSocket MCP envelope
-> typed JSON-RPC parser
-> bounded private MCP request queue
-> in-process MCP protocol server
-> tool registry / risk / confirmation / idempotency
-> NoteCommandService / NoteQueryService / TagCatalogService / UiCommandBus
-> existing DatabaseExecutor / TagCatalog / NotesViewModel
-> existing single WebSocket sender
-> Xiaozhi JSON-RPC response
```

必须满足：

- Fake 与 Real Runtime 使用同一 MCP executor；
- WebSocket receiver 不等待工具执行；
- 所有 MCP response 通过现有唯一 sender queue；
- MCP 不直接访问 Repository、SQLAlchemy Session、SQLite 或 QML；
- Note mutation 继续走 `NoteCommandService`；
- Note read 继续走 `NoteQueryService`；
- TagCatalog 的 UI/MCP 并发访问经过共享异步服务；
- UI 工具经过 `UiCommandBus`，不得从 MCP handler 直接调用 QML；
- 高风险操作经过同一 PendingConfirmationService；
- shutdown 有界且无任务、队列、确认和 response future 泄漏。

## 2. 与 Android 工具面的关系

Android Phase 4 当前契约：39 tools。

PC Gate 5 实现其中 31 个同名工具。以下 8 个不广告、不注册、不返回假成功：

```text
notes.list_archived
notes.list_done
notes.toggle_done
notes.archive
notes.restore_revision
notes.clear_done
tags.rename
ui.show_archive
```

原因：PC 当前 Note schema 没有 `archived`、`done`、revision；TagCatalog 没有 rename 事务；UI 没有 archive page。

未来若增加这些领域能力，应通过独立 amendment、数据库迁移和手动 UI 支撑后再进入 `tools/list`。

## 3. 31 个工具冻结目录

### 3.1 Note read / resolve：8

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

### 3.2 Note mutation：8

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

### 3.3 Tag tools：5

```text
tags.create
tags.search
tags.list
tags.delete
tags.bind
```

### 3.4 UI tools：7

```text
ui.open_note
ui.show_search
ui.show_note_list
ui.show_tag
ui.show_trash
ui.show_pinned
ui.show_confirmation
```

### 3.5 Confirmation tools：3

```text
assistant.confirm
assistant.reject
assistant.list_pending_confirmations
```

工具名不得增加 PC-only alias，例如 `notes.get_note`、`notes.unpin`、`notes.prepare_delete`。如需要 pin=false、confirm 或过滤，应由稳定 schema 参数表达。

## 4. MCP wire contract

### 4.1 Envelope

PC App 在现有 client hello 中继续声明：

```json
{"features":{"mcp":true}}
```

MCP 消息使用现有 Xiaozhi envelope：

```json
{
  "session_id": "...",
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {},
    "id": 3
  }
}
```

request id 支持 JSON string 或 integer，response 必须保留其类型和值。

### 4.2 Supported methods

```text
initialize
notifications/initialized
tools/list
tools/call
```

- `notifications/initialized` 没有 id，不回复；
- `tools/list` 一次返回 31 个工具，`nextCursor` 为空；
- 非空、未知 cursor 返回 invalid params，不静默分页错位；
- `withUserTools` 可接受但 Gate 5 没有额外 user-only descriptor；
- 未知 method 返回 method not found。

### 4.3 JSON-RPC errors

| 场景 | code |
|---|---:|
| parse error | -32700 |
| invalid request | -32600 |
| method / tool not found | -32601 |
| invalid params / schema | -32602 |
| internal error | -32603 |
| bounded queue full / server busy | -32000 |

业务失败通常返回合法 `tools/call` result，设置 `isError=true`，不能把可预期的 not-found、ambiguous、requires-confirmation 变成 transport failure。

### 4.4 Tool result envelope

`tools/call` 的 text content 使用稳定 JSON：

```json
{
  "status": "success",
  "message": "便签已创建",
  "tool_name": "notes.create",
  "risk": "medium",
  "requires_confirmation": false,
  "confirmation_id": null,
  "affected_note_ids": [12],
  "affected_tags": ["客户"],
  "result": {}
}
```

允许状态：

```text
success
failed
blocked
requires_confirmation
partial_success
not_implemented
```

`requires_confirmation` 是成功处理的业务状态，不等同于协议错误。

## 5. Protocol ownership and privacy

### 5.1 Private request path

当前 Gate 2 `McpEnvelope` 只保存脱敏字符串并丢弃真实参数。Gate 5 必须替换为私有 typed request path。

要求：

- untrusted JSON 只解析一次；
- 原始 payload 不写入 `AssistantState`；
- arguments、content、query 不进入普通日志、报告或 exception text；
- dataclass / object 的 `repr` 不得输出 arguments；
- Controller 只接收 sanitized lifecycle event：request id 摘要、method、tool name、status、risk、duration；
- tool result 仅通过 response sink 返回服务端，并投影安全摘要到 UI。

### 5.2 Bounded ownership

冻结默认值：

```text
MCP request queue capacity       16
MCP dedupe entries               64
pending confirmations            32
confirmation TTL                 120 seconds
maximum outer text message        64 KiB
maximum serialized tool result    32 KiB
MCP workers                       1
```

所有数值应定义为具名常量并可测试。不得使用无界 queue、无界 dict 或 per-request detached task。

### 5.3 Single sender

MCP response 必须复用 `RealWebSocketTransport` 当前 sender queue 和 `_enqueue_and_wait` 等价路径。

禁止：

- MCP worker 直接调用底层 websocket `.send()`；
- 新建第二 sender task；
- receiver 里同步执行数据库或等待 UI；
- response 绕过 generation/session 校验。

## 6. Idempotency and concurrency

去重键：

```text
connection_generation | session_id | request_id
```

并保存 method、tool name 与 canonical arguments fingerprint。

规则：

- 同 key、同 fingerprint：等待同一个 in-flight future 或返回首次 cached response；
- 同 key、不同 fingerprint：返回 invalid request conflict，零执行；
- duplicate create/delete/tag bind 不得重复写；
- request 完成前不得移除 in-flight entry；
- started mutation 不因 response waiter timeout 被取消后重新执行；
- disconnect 后不启动队列中尚未执行的 mutation；
- 已进入数据库事务的调用允许完成，记录 `committed_response_lost`，不得伪称 rollback；
- reconnect 不自动重放 MCP mutation。

## 7. Shared application boundaries

### 7.1 Notes

```text
MCP note read     -> NoteQueryService
MCP note mutation -> NoteCommandService
```

对现有完整命令的组合操作，例如 append、title-only update、tag bind，应先读取当前 Note，计算新快照，再构造 `UpdateNoteCommand`。不能直接修改 ORM row。

### 7.2 Tags

新增共享 `TagCatalogService`：

```text
NotesViewModel ─┐
                ├-> TagCatalogService -> TagCatalog
MCP tools ──────┘
```

它负责：

- 串行化 add/delete/observe；
- 统一验证 protected/system/in-use；
- 使用 `asyncio.to_thread` 或专用串行 executor 隔离文件 I/O；
- TagCatalog 修改后通知 sidebar；
- Note 创建、更新、tag bind 成功后 observe 新标签；
- shutdown 后拒绝新写。

不得让 UI 和 MCP 分别在不同 worker 中无锁写 `custom_tags.json`。

### 7.3 UI

新增 Qt-independent `UiCommandBus` protocol 和 Qt adapter。

```text
MCP UiTool -> UiCommandBus -> Qt adapter -> NotesViewModel / navigation signal -> QML
```

MCP handler 不导入 QML，不查找 QML object，不跨线程直接调用 QObject。UI 不可用时返回 `blocked/ui_unavailable`。

## 8. Risk and confirmation matrix

| 工具/操作 | 风险 | 确认 |
|---|---|---|
| 所有 read/resolve | low | 否 |
| 所有 UI tool | low | 否；`ui.show_confirmation` 只展示 |
| `assistant.reject/list_pending` | low | 否 |
| `notes.create/append/update_title/convert_type` | medium | 否 |
| `notes.pin` 1～5 条 | medium | 否 |
| `notes.pin` >5 条 | high | 是 |
| `notes.restore` 1～5 条 | medium | 否 |
| `notes.restore` >5 条 | high | 是 |
| `tags.create` | medium | 否 |
| `tags.bind add/remove` 1～5 条 | medium | 否 |
| `tags.bind add/remove` >5 条 | high | 是 |
| `tags.bind replace` | high | 是 |
| `notes.replace_content` | high | 是 |
| `notes.delete` | high | 总是 |
| `tags.delete` | high | 总是 |
| `assistant.confirm` | high gateway | 必须持有有效 pending id |

确认不能只相信调用参数 `confirmed=true`。

PendingConfirmation 必须绑定：

```text
confirmation_id
origin session / connection generation
tool name
canonical arguments fingerprint
risk
preview
affected note ids / tags
created_at / expires_at
single-use state
```

- voice `assistant.confirm` 必须来自创建 pending 的活跃 session；
- 本地 UI confirmation 作为 trusted local origin 可确认同一 pending；
- expired/rejected/consumed/disconnected pending 不可执行；
- confirm 时重新验证目标存在性和状态；
- app restart、disable、disconnect、shutdown 清空 pending；
- Gate 5 不持久化原始 note content 到 pending 文件。

## 9. Tool behavior cards

### 9.1 Read and resolve

#### `notes.resolve`

输入：`query?`, `exact_title?`, `scope=active|deleted|all`, `limit=5`。  
输出：明确的 `note_id`，或候选列表和 `ambiguous`。  
规则：多个候选时不得自动选第一条执行 mutation。

#### `notes.search`

输入：`query`, `tags?`, `scope=active`, `limit=10`。  
搜索 title/content/tags；默认不含 deleted；返回 title、snippet、tags、pin、updated_at，禁止返回无界正文。

#### `notes.list_recent`

输入：`limit=5`。  
按 `updated_at DESC, id DESC` 返回活动便签，不使用 pinned-first 冒充 recent。需要为 `NoteQueryService` 增加真实 recent query 或等价稳定实现。

#### `notes.get`

输入：`note_id`, `include_deleted=false`。  
返回一条完整领域 Note 的公开字段。

#### `notes.list_by_tag`

输入：`tag`, `limit=20`。  
精确标签匹配，只返回活动便签。

#### `notes.list_deleted`

输入：`limit=20`。  
使用现有 deleted ordering。

#### `notes.list_todos`

输入：`limit=20`。  
PC `todo` 映射为受保护标签 `待办`，不宣称存在 done 字段。

#### `notes.list_pinned`

输入：`limit=20`。  
只返回 active + pinned。

### 9.2 Note mutation

#### `notes.create`

输入：`title` 必填 1～200、`content=""`, `type=normal|todo`, `tags=[]`, `pinned=false`, `open_after_create=false`。  
行为：`type=todo` 合并 `待办` 标签；source 强制 `voice_pc`；调用 `NoteCommandService.create`；成功后 observe tags、刷新 UI；可选择发出 `ui.open_note`。

#### `notes.append`

输入：`note_id`, `content`, `separator=newline|space|none`。  
行为：读取当前 Note，生成追加后的完整 content，构造 `UpdateNoteCommand`；不得覆盖 title/tags。

#### `notes.update_title`

输入：`note_id`, `title`。  
行为：保留 content/tags，构造 `UpdateNoteCommand`。

#### `notes.replace_content`

输入：`note_id`, `content`, `expected_updated_at?`。  
行为：总是先生成 pending preview；确认时检查 expected timestamp 和当前状态；保留 title/tags。

#### `notes.convert_type`

输入：`note_id`, `target_type=normal|todo`。  
行为：todo 添加 `待办`，normal 移除 `待办`；其他标签保持不变。

#### `notes.pin`

输入：`note_ids`, `pinned`。  
行为：去重、正整数、单事务；超过 5 条升级确认。

#### `notes.delete`

输入：`note_ids`。  
行为：总是 requires_confirmation；确认后使用 `SoftDeleteCommand`；不提供 hard delete；preview 只保存安全摘要。

#### `notes.restore`

输入：`note_ids`。  
行为：恢复 deleted notes；超过 5 条升级确认；活动 note 不得伪成功。

### 9.3 Tags

#### `tags.create`

输入：`name`。  
拒绝空值、系统分类名和 protected tag；已存在返回幂等结果。

#### `tags.search`

输入：`query`, `limit=10`。  
在 custom、protected、observed tags 中搜索；返回 usage/deletable。

#### `tags.list`

输入：`include_usage=true`。  
返回 name、protected、in_use、deletable；必须包含 `待办`。

#### `tags.delete`

输入：`name`。  
总是确认；protected/system/in-use 时即使确认也拒绝；只删 catalog，不修改 notes。

#### `tags.bind`

输入：`note_ids`, `operation=add|remove|replace`, `tags`。  
对每条 Note 计算新 tags；必须保证整体原子或在规格中明确 partial_success。Gate 5 冻结为 **all-or-nothing**：应新增批量 UpdateTags command/service，不得循环多个独立事务后声称成功。replace 总是确认，add/remove 超过 5 条确认。

### 9.4 UI

| 工具 | 行为 |
|---|---|
| `ui.open_note` | 打开明确 note id；不存在时不导航 |
| `ui.show_search` | 打开/聚焦搜索并填入 query |
| `ui.show_note_list` | 打开全部活动便签 |
| `ui.show_tag` | 打开精确 tag 分类 |
| `ui.show_trash` | 打开已删除页面 |
| `ui.show_pinned` | 打开置顶视图 |
| `ui.show_confirmation` | 展示有效 pending confirmation；无效 id 时 blocked |

### 9.5 Confirmation

| 工具 | 行为 |
|---|---|
| `assistant.confirm` | 仅接受 confirmation_id；消费一次；重新验证后执行冻结命令 |
| `assistant.reject` | 拒绝并消费 pending；零 mutation |
| `assistant.list_pending_confirmations` | 只返回当前 session 的安全摘要和 expiry |

## 10. UI synchronization

任一 MCP mutation 成功后必须：

- 当前 active/deleted/tag/pinned/search view 重新查询；
- 尽量保持仍可见的 selected note id；
- tag sidebar 同步；
- QML 不接收 ORM/dict 假状态；
- UI refresh 失败不回滚已提交数据库事务，但必须返回/记录 `committed_ui_refresh_failed`；
- 不允许要求用户重启 App 才看到变化。

## 11. Audit

Gate 5 审计记录：

```text
tool_name
request fingerprint hash
source=voice_pc|fake
status / risk / error_code
confirmation state
affected note ids / tag names
started_at / finished_at / duration
response delivered yes/no
```

禁止持久化：

```text
raw MCP JSON
完整 title/content/query
token / authorization
完整 session/device/client identity
PCM / Opus
```

审计可使用滚动 JSONL 或独立表，但必须有容量/轮转、原子写和关闭所有权。不得把原始 arguments_json 当调试捷径。

## 12. Lifecycle

关闭顺序：

```text
stop accepting MCP requests
-> reject/cancel queued not-started requests
-> invalidate pending confirmations
-> await in-flight worker bounded
-> close MCP response sink
-> existing transport close
-> NotesViewModel / TagCatalogService close
-> DatabaseExecutor close
```

终态：

```text
no mcp worker
no tool execution task
no request queue item
no in-flight dedupe future
no pending confirmation
no UI command task
no MCP response future
no second sender
no second Python process
```

## 13. Non-goals

Gate 5 不实现：

- archive/done/revision/color 等 PC 不存在的领域能力；
- hard delete；
- KWS；
- AEC/NS/AGC；
- cloud sync；
- external MCP endpoint/server process；
- filesystem、calendar、contacts、browser、system control tools；
- 自然语言解析器；服务端负责把自然语言规范化为工具调用。


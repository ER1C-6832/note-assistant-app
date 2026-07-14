# MCP Note Tool Scope

状态：Gate 0 冻结候选

## 1. 协议范围

支持 `initialize`、`notifications/initialized`、`tools/list`、`tools/call`。不支持的方法返回 JSON-RPC method not found。

## 2. 执行边界

```text
WebSocket MessageRouter
-> McpProtocolClient
-> McpToolExecutor
-> NoteCommandService
-> NoteRepository
-> SQLite
```

WebSocket Router 不得直接调用 Repository。没有注册 Executor 时 fail-closed。

## 3. MVP 工具

### notes.create

输入：

```json
{"title":"可选标题","content":"内容","tags":["标签"],"type":"normal"}
```

规则：title/content 至少一个非空；默认 source=`voice`；低风险；成功返回 note_id、title。

### notes.search

输入：

```json
{"query":"关键词","limit":10,"include_deleted":false}
```

规则：limit 1～50；只读；低风险；结果保持简洁。

### notes.delete

输入：

```json
{"note_ids":[1],"confirmed":false}
```

规则：高风险；首次只创建 PendingConfirmation；返回 `requires_confirmation` 和 confirmation_id；显式确认后软删除；MVP 不做永久删除。

## 4. 统一结果

```python
@dataclass(frozen=True)
class ToolResult:
    status: Literal["success", "failed", "blocked", "requires_confirmation", "partial_success", "not_implemented"]
    message: str
    tool_name: str | None
    result_json: str | None
    error_code: str | None
    confirmation_id: str | None
    affected_note_ids: tuple[int, ...]
```

## 5. 去重

缓存键为 `session_id | conversation_id | request_id`，容量 64。重复调用返回第一次结果，不重复写数据库。

## 6. 工具命名

与 Android 一致：`notes.create`、`notes.search`、`notes.delete`。

## 7. 审计

记录 tool_name、arguments_json、source、status、risk_level、error_code、confirmation_status、affected_note_ids、started_at、finished_at。

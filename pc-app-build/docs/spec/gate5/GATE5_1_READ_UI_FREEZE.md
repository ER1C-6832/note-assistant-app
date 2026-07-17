# Gate 5.1 Read / Resolve and UI Navigation Freeze

状态：实施完成，等待目标 Windows 工作树累计与 Real 验收。

基线：`c1eb1bf6e6240f7c8e8bccbb0aa320ce057b658e`（Gate 5.0 Accepted）。

## 1. 冻结范围

Gate 5.1 只启用以下 15 个工具：

```text
notes.resolve
notes.search
notes.list_recent
notes.get
notes.list_by_tag
notes.list_deleted
notes.list_todos
notes.list_pinned

ui.open_note
ui.show_search
ui.show_note_list
ui.show_tag
ui.show_trash
ui.show_pinned
ui.show_confirmation
```

其中 `ui.show_confirmation` 仅冻结 bus/display contract；Gate 5.1 没有 pending confirmation，调用必须返回 `blocked/confirmation_not_ready`。其余 mutation、tag 与 confirmation 工具继续返回 `blocked/gate_not_ready`。

## 2. 查询语义

- `notes.list_recent` 使用 `updated_at DESC, id DESC`，不得使用 pinned-first 排序冒充 recent。
- active search 默认排除 deleted；`scope=deleted|all` 必须显式请求。
- `notes.list_todos` 只匹配受保护标签 `待办`，不宣称存在 done 字段。
- `notes.list_by_tag` 使用精确标签匹配。
- list/search 输出使用摘要和 UTF-8 字节预算；`notes.get` 正文受 32 KiB MCP result budget 约束并返回 `content_truncated`。
- `notes.resolve` 优先正整数 id、精确标题，再做模糊候选；多候选返回 `ambiguous` 且 `note_id=null`，不得自动选择第一条。
- 读取工具只经过 `NoteQueryService`，不得直接访问 Repository、SQLAlchemy、SQLite。

## 3. UI 所有权

```text
MCP tool handler
-> UiCommandBus
-> NotesUiCommandAdapter
-> NotesViewModel public API
-> navigationRequested signal
-> Main.qml page/category transition
```

- handler 不导入 Qt/QML，也不查找 QML object。
- `UiCommandBus` 只拥有一个可替换 adapter；generation 变化后丢弃旧 dispatch 结果。
- UI 不可用、关闭或 stale selection 时返回 safe blocked result。
- `ui.open_note` 只允许打开 active note；deleted note 返回 `blocked/note_deleted`。
- 所有 dispatch 都被 await，不创建 per-command detached task。

## 4. Runtime 组合

应用组合根创建一个共享 `ToolRegistry`、`McpCoordinator` 和 `UiCommandBus`。Fake 与 Real transport 必须复用同一个 coordinator，因此 read/UI 工具不允许只在 verifier 中旁路接线。

关闭顺序确保：Assistant transport/coordinator 先停，随后 UI bus、NotesViewModel、DatabaseExecutor 和数据库引擎关闭。终态必须没有 MCP worker、request/future、UI dispatch 或 assistant task。

## 5. Gate 5.1 退出条件

- 8 个 read/resolve 工具通过真实 service/database 集成；
- 6 个当前可执行 UI 导航工具通过 typed bus；
- `ui.show_confirmation` 正确 blocked；
- ambiguous resolve 零 mutation；
- deleted 不混入 active search；
- todo 使用精确 `待办` 标签；
- UI generation stale/unavailable fail-closed；
- Fake 与 Real 复用同一 registry/coordinator；
- 累计测试、Fake runner、Real read/UI runner 返回 0；
- payload、正文、query、token 与完整 identity 不进入普通日志或报告。

# Gate 5.1 Implementation Report

状态：实现候选，等待目标 Windows 工作树验收。

实现基线：`c1eb1bf6e6240f7c8e8bccbb0aa320ce057b658e`。

## 1. 前置验收

Gate 5.0 已由目标 Windows 工作树完成：完整累计测试、387 tests、Fake protocol、Real initialize/tools/list、Gate 4 Real audible stop 均返回 0；31-tool registry 与所有 MCP terminal resources 均通过。

## 2. 本阶段实现

### Read / resolve

启用 8 个 read/resolve handler：

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

新增 `NoteQueryService.list_recent`，并在 SQLAlchemy repository 中实现真实 `updated_at DESC, id DESC` 查询。补充 bounded list、scope/filter search 和 resolver 所需的服务级组合方法。

结果只返回有界摘要；完整读取也受 MCP 32 KiB budget 约束。resolver 对 ambiguous 结果不自动选第一项。

### UI navigation

新增 Qt-independent `UiCommandBus` 及 typed command/result contract。新增 `NotesUiCommandAdapter`，只调用 `NotesViewModel` public API，并通过 `navigationRequested` 信号让 QML 切换页面、分类和搜索框。

当前可执行：open note、search、all notes、tag、trash、pinned。`ui.show_confirmation` 在没有 pending confirmation 时返回 `blocked/confirmation_not_ready`。

### Production composition

Bootstrap 现在创建共享：

```text
ToolRegistry(Gate51ToolExecutor)
-> McpCoordinator
-> McpScriptedFakeTransport / McpRealWebSocketTransport
```

Fake 与 Real 使用同一 executor、registry 和 coordinator。后续 Gate 的 mutation/tag/confirmation handler 保持 `blocked/gate_not_ready`。

## 3. 验证器

```powershell
python tools/verify_gate5_1_cumulative.py
python tools/verify_gate5_1_read_ui.py
python tools/verify_gate5_1_real_read_ui.py
```

包含 Real 累计：

```powershell
python tools/verify_gate5_1_cumulative.py --include-gate4-real --include-gate5-real
```

Real runner 使用当前数据库的一条 active note，只记录 note id、工具状态、masked identity、public endpoint 和资源终态；不打印 title、content、query 或原始 MCP arguments。

## 4. 当前构建环境证据

```text
compileall: passed
Black check: passed
Ruff check: passed
Gate 5.1 core behavior: 10 passed
Gate 5.1 architecture contracts: 3 passed
Gate 5.1 Fake service/database/MCP scenario: fake_gate_complete
read_tool_count: 8
ui_tool_success_count: 6
ui.show_confirmation: blocked
MCP/UI terminal resources: all zero
payload_persisted: false
```

当前环境没有目标仓库的完整历史工作树和真实 Xiaozhi endpoint，因此没有声称运行完整累计 pytest 或 Real read/UI acceptance。

## 5. 非目标

Gate 5.1 不执行任何 note/tag mutation，不创建 pending confirmation，不实现 `assistant.confirm/reject`，也不直接访问 Repository、SQLite 或 QML object。上述能力分别留给 Gate 5.2 和 Gate 5.3。

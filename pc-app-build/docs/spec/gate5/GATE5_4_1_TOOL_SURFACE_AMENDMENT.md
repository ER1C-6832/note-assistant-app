# Gate 5.4.1 Tool Surface Amendment

状态：修订候选，等待 Windows 回归与两项真实复测。

## 修订

1. 当前工具面从 31 增加为 32，新增 `ui.show_todos`。
2. `notes.resolve` 不再把纯数字 query 隐式解释为数据库 ID。
3. 明确 ID 仅接受“编号 119 / ID 119 / 第119号便签 / 便签#119”等表达。
4. 单独“119”“标题叫119”“找119那条”进入标题/关键词候选流程。
5. 断线重连不自动重放任何历史工具调用，mutation 仍由 request-id 去重和 generation/session 边界保护。

## 新工具

```text
ui.show_todos
inputSchema: {}
risk: low
mutates: false
confirmation: never
```

执行链：

```text
Gate51ToolExecutor
-> UiCommandKind.SHOW_TODOS
-> UiCommandBus
-> NotesUiCommandAdapter.loadCategory("todo")
-> Main.qml currentCategory="todo"
```

## 新冻结值

```text
Tool count: 32
Name-set SHA-256: 543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9
```

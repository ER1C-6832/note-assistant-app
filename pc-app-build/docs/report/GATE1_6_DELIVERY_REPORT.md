# Gate 1.6 交付报告：正式 QML 接线

## 完成内容

- Bootstrap 不再创建 `EmptyNotesViewModel`，改为组合正式的 `NotesViewModel`、活动列表 `NoteListModel` 和已删除列表 `NoteListModel`。
- 正式 ViewModel 与 Gate 1.4 的 `NoteCommandService`、`NoteQueryService`、`TagCatalog` 使用同一实例；关闭顺序为 ViewModel task → DB Executor → SQLAlchemy Engine。
- “待办”分类改为精确查询标签 `待办`，刷新时保持当前待办视图。
- QML 页面显式接收 `notesViewModelRef`，不再由子页面直接读取全局上下文对象。
- 创建、编辑、删除、置顶、批量操作、恢复和彻底删除均等待成功 Signal 后改变导航或多选状态；失败时保留当前页面和输入。
- Mutation 期间禁用相关按钮；保留唯一的 220ms 搜索 debounce Timer，未加入 startup/category/tag 延迟 Timer。
- 保留旧 PC 端有价值的页面与交互语义，但未恢复 Controller、sidecar、localhost HTTP 或轮询。

## 自动化测试

新增 `tests/gate1_6`：

- Bootstrap 正式对象组合与关闭；
- offscreen QML 加载；
- ViewModel → Service → SQLite 的创建、待办查询、编辑、软删除、恢复链路；
- QML 无旧 Controller、无多余 Timer、无同步假成功；
- 子页面 ViewModel 显式传递和 Signal 驱动状态。

## 本地验证

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_6.ps1
```

手工启动：

```powershell
cd .\pc-app-build\apps\notes-pyside
python main.py
```

验收重点：便签真实加载；全部/置顶/待办/标签/搜索可切换；CRUD、批量、已删除流程可用；失败不错误导航；退出无 QML traceback 和残留第二 Python 进程。

## 边界

本次完成 Gate 1.6，不接入 Assistant Runtime、MCP、音频、同步或 sidecar。MCP 后续通过当前共享 `NoteCommandService` 接入，而不是回接旧 HTTP Controller。

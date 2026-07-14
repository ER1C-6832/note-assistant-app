# Gate 1 单进程便签实施报告

基线：`rewrite/single-process-runtime`，Gate 1.6 验收后的提交 `85cee9b`。

## 已完成

- **G1.1**：`QGuiApplication + qasync` 单事件循环、应用路径和受控关闭。
- **G1.2**：Domain、SQLAlchemy Repository、单线程 DB Executor、批量事务。
- **G1.3**：LocalAppData、legacy SQLite/标签迁移、校验、备份和迁移报告。
- **G1.4**：异步 Command/Query Service，UI 与未来 MCP 共用应用服务边界。
- **G1.5**：Qt `NoteListModel`、单一 `NotesViewModel`、busy、选择稳定和旧查询保护。
- **G1.6**：Bootstrap/QML 正式接线，成功 Signal 驱动导航，失败保留页面状态。
- **G1.7**：全量回归、真实 SQLite 跨重启测试、legacy Bootstrap 迁移测试、独立进程 offscreen 启停测试和架构扫描。

## 最终架构

```text
QML
  -> NotesViewModel / NoteListModel
  -> NoteCommandService / NoteQueryService
  -> DatabaseExecutor（单工作线程）
  -> SqlAlchemyNoteRepository
  -> %LOCALAPPDATA%\NoteAssistant\data\notes.db
```

当前便签链路不依赖 sidecar、localhost HTTP、FastAPI、轮询或第二个 Python 进程。旧 PC 端仅作为交互行为和未来 MCP 功能参考，不作为运行时架构来源。

## Gate 1.7 新增验证

- Python 源码 AST、单一 Composition Root 和 Context Property 检查。
- 禁止旧 Controller、HTTP 栈、sidecar 和进程启动 API 的源码扫描。
- QML 只保留 220ms 搜索 debounce Timer；写操作不使用同步 bool 假成功。
- 真实 QML + SQLite：创建、待办、标签、搜索、编辑、自定义标签、重启持久化、软删除和彻底删除。
- legacy DB 经 Bootstrap 迁移后直接进入正式 ViewModel，并确认源文件未被修改。
- 独立 Python 进程 offscreen 启动、自动退出，并拒绝 QML TypeError/ReferenceError/traceback。

## 本地验收

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_7.ps1
```

通过标准：Black、Ruff、compileall 和 Gate 1.1～1.7 pytest 全部退出码为 0；offscreen 启停无 QML 异常。

随后手工运行：

```powershell
cd .\pc-app-build\apps\notes-pyside
python main.py
```

检查全部/置顶/待办/标签/搜索、CRUD、多选、已删除、重启持久化；关闭窗口后不应残留本应用的第二个 `python.exe`。

## 结论

完成上述自动与手工验收后，Gate 1 可关闭，下一阶段进入 Gate 2：Runtime Core 与文本链路。MCP 后续应直接复用 `NoteCommandService`，不重新引入旧 sidecar/HTTP 便签链路。

# Gate 1 验收清单

## 架构

- [ ] 单 Python 进程。
- [ ] qasync 是唯一 asyncio loop。
- [ ] Bootstrap 是 Composition Root。
- [ ] Notes Domain 不依赖 PySide6。
- [ ] QML 只依赖 NotesViewModel。
- [ ] UI 和未来 MCP 共用 NoteCommandService。
- [ ] 无 localhost HTTP。
- [ ] 无旧 Controller Adapter。

## 数据

- [ ] 数据位于 `%LOCALAPPDATA%\NoteAssistant\data`。
- [ ] legacy DB 可安全迁移。
- [ ] 迁移不删除源。
- [ ] 多候选不自动猜测。
- [ ] 目标存在时不覆盖。
- [ ] SQLite quick_check 通过。
- [ ] WAL/PRAGMA 已配置。
- [ ] 旧 schema 兼容。

## 功能

- [ ] 全部列表。
- [ ] 置顶列表。
- [ ] 待办列表。
- [ ] 标签列表。
- [ ] 搜索。
- [ ] 创建。
- [ ] 编辑。
- [ ] 单条/批量置顶。
- [ ] 单条/批量软删除。
- [ ] 恢复。
- [ ] 彻底删除。
- [ ] 标签新增/删除规则。
- [ ] 重启持久化。

## 并发

- [ ] DB 单线程 Executor。
- [ ] Session 不跨线程。
- [ ] 批量操作单事务。
- [ ] Mutation 串行。
- [ ] Query generation 防旧结果覆盖。
- [ ] Qt 主线程不执行 SQL。
- [ ] Shutdown 有界。

## UI

- [ ] Context 名为 `notesViewModel`。
- [ ] 不再出现 `notesController`。
- [ ] Mutation 不依赖同步 bool。
- [ ] 成功 Signal 驱动导航。
- [ ] 失败不离开编辑页。
- [ ] 选择按 note_id 稳定。
- [ ] QML 无人工 startup/category/tag 延迟 Timer。
- [ ] Offscreen QML Smoke 通过。

## 测试

- [ ] Repository Unit。
- [ ] Service Integration。
- [ ] Migration。
- [ ] TagCatalog。
- [ ] ViewModel。
- [ ] QML Smoke。
- [ ] Windows 手工矩阵。
- [ ] Ruff/Black/Pytest 全通过。

## Gate 结束

- [ ] Gate 1 Implementation Report。
- [ ] Git 工作区 clean。
- [ ] 分支已推送。
- [ ] 可进入 Gate 2：Runtime Core + 文本链路。

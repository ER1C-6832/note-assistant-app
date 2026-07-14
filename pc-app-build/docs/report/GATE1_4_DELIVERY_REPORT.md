# Gate 1.4 交付报告：Application Service 与 Bootstrap Composition

## 1. 交付结论

Gate 1.4 已建立完整的进程内便签应用服务边界，并将 Gate 1.1～1.3 已完成的路径、迁移、数据库、Repository、TagCatalog 正式组合进桌面应用 Bootstrap。

当前运行链路：

```text
QGuiApplication / qasync
-> AppPaths
-> prepare_gate1_local_data
-> SQLAlchemy Engine / SessionFactory
-> DatabaseExecutor(max_workers=1)
-> SqlAlchemyNoteRepository
-> NoteCommandService / NoteQueryService
```

QML 仍使用 `EmptyNotesViewModel`，没有提前进入 Gate 1.5 或 Gate 1.6。

---

## 2. 新增模块

### `notes/command_service.py`

公开异步接口：

```python
create(command)
update(command)
set_pinned(command)
soft_delete(command)
restore(command)
hard_delete(command)
```

每个公开方法只调用一次统一的 Repository 调度入口。

### `notes/query_service.py`

公开异步接口：

```python
list_all()
list_pinned()
list_deleted()
list_by_tag(tag)
search(query, limit=100)
get(note_id, include_deleted=False)
```

查询同样不在 Qt 主线程执行 SQL。

### `notes/service_errors.py`

应用层错误：

```text
NoteServiceNotFoundError
NoteServiceStateError
NoteServiceUnavailableError
NoteServiceRepositoryError
```

映射关系：

```text
NoteNotFoundError
-> NoteServiceNotFoundError

NoteStateError
-> NoteServiceStateError

DatabaseExecutorClosedError
-> NoteServiceUnavailableError

其他 NoteRepositoryError
-> NoteServiceRepositoryError
```

Service 不把 Repository 的具体错误直接暴露给未来 ViewModel 或 MCP。

---

## 3. Bootstrap Composition

`create_application_context()` 现在按以下顺序执行：

```text
1. Resolve AppPaths
2. ensure_directories
3. resolve_worktree_root
4. prepare_gate1_local_data
5. load TagCatalog
6. 创建空 Qt Models / EmptyNotesViewModel
7. 加载 Main.qml
8. create_sqlite_engine
9. initialize_database
10. create_session_factory
11. 创建 SqlAlchemyNoteRepository
12. 创建 DatabaseExecutor
13. 创建 NoteCommandService / NoteQueryService
14. 注册 Lifecycle closer
15. 调度 EmptyNotesViewModel.loadAll
```

Bootstrap 只负责对象组合，不包含业务 SQL。

### ApplicationContext 新增可访问对象

```text
migration_result
tag_catalog
notes_runtime
database_engine
session_factory
database_executor
note_repository
note_command_service
note_query_service
```

这些对象为 Gate 1.5 的正式 NotesViewModel 提供稳定注入点。

---

## 4. 关闭顺序

Lifecycle 注册顺序：

```text
sqlalchemy-engine
database-executor
```

`ApplicationLifecycle.shutdown()` 逆序执行，因此真实关闭顺序是：

```text
1. DatabaseExecutor.close()
2. SQLAlchemy Engine.dispose()
```

确保不会在数据库任务仍运行时提前释放连接池。

关闭后继续调用 Service，会映射为：

```text
NoteServiceUnavailableError
```

---

## 5. 迁移和数据路径

Gate 1.4 首次把 Gate 1.3 迁移流程接入真实应用启动。

默认路径：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\notes.db
├─ data\custom_tags.json
├─ logs\migration-gate1.json
└─ backups\
```

行为保持 Gate 1.3 规格：

- 有效目标数据库不覆盖；
- 单一 legacy 来源安全迁移；
- 多来源冲突拒绝猜测；
- 损坏目标先备份再阻止继续；
- 源数据库不删除、不移动；
- 使用 SQLite Backup API；
- 测试可注入临时 `data_root` 和 `worktree_root`。

---

## 6. 测试覆盖

新增 Gate 1.4 测试：

```text
test_command_service.py
test_query_service.py
test_service_integration.py
test_bootstrap_composition.py
test_gate1_4_architecture.py
```

覆盖：

- 六个写命令每次只进入一次 Executor；
- 六个查询每次只进入一次 Executor；
- Repository 错误映射；
- Executor 关闭错误映射；
- 真实 SQLAlchemy Repository + DatabaseExecutor + Service CRUD；
- Bootstrap 创建空数据库和默认 TagCatalog；
- Service 可通过 ApplicationContext 调用；
- Lifecycle 关闭后拒绝新查询；
- Executor 在 Engine 前关闭；
- Service 不导入 PySide6；
- Bootstrap 不包含业务 SQL；
- 新测试文件名不会与旧 Gate 的 `test_architecture.py` 发生 pytest 模块冲突；
- Gate 1.4 不新增同级 `conftest.py`，避免破坏 Gate 1.3 的辅助函数导入。

同时更新 Gate 1.1 Bootstrap Smoke Test：

- 使用临时 worktree，避免扫描开发机真实 legacy 数据；
- 验证 Migration 和数据库初始化；
- 测试结束时关闭 DatabaseExecutor 和 Engine；
- 防止 Windows 临时目录被数据库句柄占用。

---

## 7. 实际验证

交付文件使用项目配置 `line-length = 100` 验证：

```text
Black 24.10.0：通过
Ruff 0.9.10：通过
compileall：通过
```

在顺序叠加 Gate 1.1、1.2、1.3 和本次 Gate 1.4 文件的重建环境中：

```text
65 passed
```

该全量运行覆盖 Python、SQLite、SQLAlchemy、PySide6、qasync、Migration、Application Service 和 Bootstrap 关闭顺序。

重建环境缺少远端仓库中未包含于旧覆盖包的部分未修改 QML 组件，因此容器中的 Bootstrap 测试使用最小等价 QML 根窗口；用户当前仓库的真实 QML 已在此前 `python main.py` 验收中正常启动。本地最终验收仍应运行本报告提供的全量命令，以实际仓库 QML 为准。

---

## 8. 当前限制

Gate 1.4 有意保留：

```text
EmptyNotesViewModel
EmptyNoteListModel
```

因此：

- 应用启动会创建或迁移真实本地数据库；
- Service 已可真实 CRUD；
- QML 列表仍不会显示数据库内容；
- UI 按钮仍显示“尚未接入数据库”。

这是 Gate 1.4 与 Gate 1.5 的明确边界，不是缺陷。

---

## 9. 下一阶段

Gate 1.5：

```text
NoteListModel
DeletedNoteListModel
NotesViewModel
query generation
mutation serialization
selection by note_id
busy 状态
成功/失败 Signal
TagCatalog UI 映射
```

Gate 1.5 将直接注入本次交付的：

```text
NoteCommandService
NoteQueryService
TagCatalog
ApplicationLifecycle
```

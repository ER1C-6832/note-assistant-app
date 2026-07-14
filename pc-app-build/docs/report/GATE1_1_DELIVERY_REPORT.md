# Gate 1.1 交付报告

版本：1.0  
工作包：G1.1 骨架和路径

## 1. 已完成

- 新增 `AppPaths`，默认使用 `%LOCALAPPDATA%\NoteAssistant\`；
- 新增 qasync 单事件循环启动；
- 新增 `ApplicationLifecycle`，为后续 DB/Runtime 关闭提供统一边界；
- `run_app()` 已从清理占位切换到真实 bootstrap；
- 新增空 `NotesViewModel` 和两个空 Qt ListModel；
- QML Context Property 已统一为 `notesViewModel`；
- QML 写操作已切换到 `request*` 异步命名，不再依赖同步 bool；
- 删除 QML 的 startup/category/tag 人工延迟 Timer，保留 220ms 搜索 debounce；
- 新增 AppPaths Unit Test 与 offscreen QML Smoke Test；
- `pyproject.toml` 新增 `qasync` 与 `pytest-qt`。

## 2. 当前运行行为

App 可以进入 QML，但列表为空。查询只更新空 ViewModel 的界面状态；创建、编辑、删除、标签等写操作会返回可见错误：

```text
Gate 1.1 尚未接入数据库
```

这是本工作包的预期断点，不属于失败。

## 3. 架构符合性

- 单进程：符合；
- qasync 唯一事件循环：符合；
- Bootstrap 为 Composition Root：符合；
- 无 DB/HTTP/Assistant：符合；
- QML 不直接访问路径或 Repository：符合；
- 旧 `notesController` 上下文：已移除；
- Sidecar/py-xiaozhi/FastAPI/Uvicorn：未引入。

## 4. 测试说明

交付环境已完成：

- 全部 Python 文件 AST/compileall 检查；
- 包应用脚本模拟测试；
- 禁止词与旧上下文静态扫描；
- 清单和 SHA-256 校验。

交付环境未安装 PySide6、qasync、pytest-qt，因此没有声称在此环境实际执行 QML Smoke Test。测试代码已包含，需在 Windows Worktree 安装 dev 依赖后运行：

```bat
python -m pip install -e ".[dev]"
python -m pytest tests\gate1_1 -q
```

## 5. 已知限制

- EmptyNotesViewModel 是 Gate 1.1 临时实现，G1.5 必须整体替换，不能继续堆业务；
- 当前没有数据库迁移；
- 当前没有真实列表数据；
- 生命周期关闭骨架尚无 DB closer；
- QML 成功 Signal 导航已预留，但在空 ViewModel 中不会触发成功。

## 6. 下一步

进入 G1.2：

```text
Domain Note
Commands
Repository Protocol
SQLAlchemy Models
SqlAlchemyNoteRepository
DatabaseExecutor
Repository Tests
```

G1.2 不应修改 EmptyNotesViewModel 的业务逻辑，只构建无 Qt 依赖的领域与持久化层。

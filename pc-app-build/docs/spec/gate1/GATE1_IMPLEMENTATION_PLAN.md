# Gate 1 实施计划

状态：实施候选

## 0. 约束

- 不复制旧 755 行 `NotesController`；
- 不保留新旧两套 Notes 实现；
- 不先恢复同步 API；
- 不在 QML Slot 内同步执行 SQL；
- 不在一次提交中同时完成所有层。

## 1. 工作包 G1.1：骨架和路径

输出：

```text
app/bootstrap.py
app/app_paths.py
app/lifecycle.py
qasync dependency
```

工作：

- 实现 AppPaths；
- 建立 QGuiApplication + qasync；
- 让 `run_app()` 调用 bootstrap；
- 先用 Fake/Empty ViewModel 加载 QML Smoke；
- 建立受控 shutdown。

验收：

- 单进程；
- QML 可加载；
- 没有 DB/HTTP/Assistant；
- offscreen smoke 通过。

建议提交：

```text
feat(app): add qasync bootstrap and application paths
```

## 2. 工作包 G1.2：Domain 和 Persistence

删除过渡文件，创建：

```text
domain.py
commands.py
repository.py
sqlalchemy_models.py
sqlalchemy_repository.py
database_executor.py
```

工作：

- 定义 Domain Note；
- ORM mapper；
- Session transaction；
- WAL/PRAGMA；
- CRUD 和 bulk；
- Repository tests。

验收：

- 不依赖 PySide6；
- 批量单事务；
- 旧 schema 测试通过。

建议提交：

```text
refactor(notes): rebuild in-process note domain and repository
```

## 3. 工作包 G1.3：Migration 和 Tags

输出：

```text
migration.py
tag_catalog.py
```

工作：

- LocalAppData；
- legacy 候选发现；
- quick_check；
- SQLite backup；
- migration report；
- custom tags；
- 观察标签合并。

验收：

- 不覆盖目标；
- 不删除源；
- 多候选拒绝猜测；
- migration tests 通过。

建议提交：

```text
feat(notes): add local data migration and tag catalog
```

## 4. 工作包 G1.4：Application Services

输出：

```text
command_service.py
query_service.py
```

工作：

- async service；
- DB Executor；
- validation；
- command result/error；
- query generation 所需接口。

验收：

- UI 不知道 Session；
- CommandService 可被未来 MCP 注入；
- service integration tests 通过。

建议提交：

```text
feat(notes): add shared note command and query services
```

## 5. 工作包 G1.5：Qt Model 和 ViewModel

输出：

```text
ui/note_list_model.py
ui/notes_view_model.py
```

工作：

- 固定 Model roles；
- ViewModel Properties；
- async Slots；
- mutation Signals；
- busy；
- selection by note_id；
- stale query protection。

验收：

- ViewModel tests；
- 无同步 DB；
- 无第二套领域状态。

建议提交：

```text
feat(ui): add asynchronous notes view model
```

## 6. 工作包 G1.6：QML 接线

工作：

- `notesController` -> `notesViewModel`；
- 删除人工 startup/category/tag Timer；
- mutation 改 Signal 驱动；
- 保留搜索 debounce；
- 删除任何同步 bool 假成功；
- 修复创建/编辑/删除导航。

验收：

- 所有页面可用；
- 操作失败不错误导航；
- 搜索不会被旧结果覆盖；
- QML Smoke 通过。

建议提交：

```text
refactor(qml): bind notes UI to asynchronous view model
```

## 7. 工作包 G1.7：回归与报告

工作：

- 全量 pytest；
- offscreen QML；
- legacy 数据真机迁移；
- 手工矩阵；
- 进程检查；
- 生成 Gate 1 report。

输出：

```text
docs/report/GATE1_IMPLEMENTATION_REPORT.md
```

建议提交：

```text
test(notes): complete Gate 1 single-process validation
```

## 8. 预计有效时间

按 AI 主编码、人工架构 Review 和真机测试：

| 工作包 | 时间 |
|---|---:|
| G1.1 | 0.5 日 |
| G1.2 | 0.5～1 日 |
| G1.3 | 0.5 日 |
| G1.4 | 0.5 日 |
| G1.5 | 0.5～1 日 |
| G1.6 | 0.5 日 |
| G1.7 | 0.5～1 日 |
| 总计 | 3～5 日 |

不可压缩风险：

- legacy DB 实际位置；
- Windows 文件占用；
- qasync shutdown；
- QML 异步导航；
- SQLite 日期兼容。

## 9. 停止条件

Gate 1 不允许扩展为：

- Assistant Runtime；
- 音频；
- MCP；
- 同步；
- 新便签功能。

发现需求时记录到后续 Gate，不在 Gate 1 顺手实现。

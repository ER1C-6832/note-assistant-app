# Gate 1.5 交付报告：Qt Model 与异步 NotesViewModel

## 1. 交付结论

Gate 1.5 已完成以下正式实现：

```text
app/ui/note_list_model.py
app/ui/notes_view_model.py
app/ui/__init__.py
```

并新增 Gate 1.5 自动测试：

```text
tests/gate1_5/conftest.py
tests/gate1_5/test_note_list_model.py
tests/gate1_5/test_notes_view_model.py
tests/gate1_5/test_gate1_5_architecture.py
```

本 Gate 建立了 QML 与 Gate 1.4 Application Service 之间的正式 Qt 边界：

```text
QML（Gate 1.6 正式接线）
-> NotesViewModel
-> NoteCommandService / NoteQueryService
-> DatabaseExecutor(max_workers=1)
-> SqlAlchemyNoteRepository
-> SQLite
```

本次没有恢复旧 PC `main` 分支中的同步 Controller、HTTP API 或 QML 直连数据库逻辑。

---

## 2. 架构参考与实现原则

参考架构是 `note-assistant-android/main`，核心对应关系如下：

```text
Android
NoteListScreen
-> NoteListViewModel
-> NoteListState
-> NoteUseCases
-> Repository

PC
QML
-> NotesViewModel
-> NoteListModel
-> NoteCommandService / NoteQueryService
-> Repository
```

保留的共同原则：

- UI 只观察 ViewModel 暴露的状态；
- ViewModel 是 UI 状态的单一所有者；
- UI 不接触 ORM、Session、SQLAlchemy Engine 或数据库线程；
- 写命令从 ViewModel 进入 Application Service；
- 查询结果异步返回并更新可观察 Model；
- 失败通过状态和 Signal 显式呈现；
- 不维护第二套 Note Domain。

没有机械照搬 Android 的 Compose、StateFlow、Hilt 或 Kotlin coroutine API。PC 端继续使用已经冻结的 PySide6、Qt Model、qasync 和 Python Application Service 边界。

---

## 3. Gate 范围

### 3.1 本次完成

- 固定角色的 `NoteListModel`；
- 正式 `NotesViewModel`；
- Query Slots；
- Selection Slots；
- Mutation Slots；
- mutation 成功和失败 Signals；
- query generation；
- stale query protection；
- mutation serialization；
- busy 状态；
- selection by note_id；
- TagCatalog 到 QML 数据映射；
- ViewModel 任务关闭与取消；
- Gate 1.5 单元和架构测试。

### 3.2 本次明确不做

- 不修改 `Main.qml`；
- 不修改其他 QML 页面；
- 不在 Bootstrap 中替换 `EmptyNotesViewModel`；
- 不改变 Gate 1.4 Service；
- 不新增便签业务功能；
- 不涉及 Assistant Runtime、音频、MCP 或网络。

正式 ViewModel 注入 Bootstrap、QML Signal 导航和真实数据显示属于 Gate 1.6。

---

## 4. NoteListModel

### 4.1 固定 QML Roles

`NoteListModel` 固定输出：

```text
noteId
 title
content
tagsText
updatedText
sourceText
cardColor
isPinned
isDeleted
```

其中模型输入只能是不可变 Domain `Note`。

禁止输入：

- SQLAlchemy ORM Row；
- Session；
- Pydantic/HTTP response；
- 任意业务 dict；
- QML 自行拼装的对象。

### 4.2 模型职责

模型负责：

- 将 Domain Note 映射为 Qt role；
- 原子替换当前列表；
- 按 index 读取 Domain Note；
- 按 `note_id` 查找 index；
- 返回当前可见 note IDs；
- 在列表替换时发送正确的 Qt Model reset 通知。

模型不负责：

- 查询数据库；
- 排序业务规则；
- 写命令；
- 选择状态；
- TagCatalog 持久化。

---

## 5. NotesViewModel

### 5.1 Properties

按 Gate 1 UI Contract 实现：

```text
selectedIndex
hasSelection
selectedTitle
selectedContent
selectedTagsText
selectedSourceText
selectedUpdatedText
selectedIsPinned

deletedSelectedIndex

activeCategory
searchKeyword
resultCount
deletedResultCount

statusMessage
errorMessage
isBusy
mutationBusy

tagItems
```

`isBusy` 的定义：

```text
isBusy = queryBusy or mutationBusy
```

### 5.2 Query Slots

实现：

```text
loadAll()
loadCategory(categoryKey)
loadTag(tag)
loadDeleted()
searchNotes(keyword)
refreshCurrentView()
```

所有 Query Slot 只调度异步任务，不在 Qt 主线程执行 SQL。

查询映射：

```text
all      -> NoteQueryService.list_all()
pinned   -> NoteQueryService.list_pinned()
deleted  -> NoteQueryService.list_deleted()
tag:*    -> NoteQueryService.list_by_tag()
search   -> NoteQueryService.search()
```

### 5.3 Stale Query Protection

每次启动新查询：

```text
query_generation += 1
```

旧查询即使稍后返回，也只有 generation 仍为当前值时才能更新 Model。

因此以下情况不会发生：

```text
用户先搜索 A
-> A 查询较慢
用户立即搜索 B
-> B 先返回并显示
A 后返回覆盖 B
```

### 5.4 Selection by note_id

选择稳定性不依赖旧 index，而依赖 Domain `note_id`。

列表刷新后：

- 原 selected note_id 仍可见：恢复对应新 index；
- 原 note_id 不可见但列表非空：默认选择第一条；
- 空列表：`selectedIndex = -1`；
- active 和 deleted 列表分别维护选择。

这避免了置顶、删除、搜索或更新时间改变排序后选中错误便签。

### 5.5 Mutation Serialization

写操作使用单一 mutation task 串行执行。

已有 mutation 运行时，新 mutation 会被同步拒绝：

```text
operationFailed(operation, "操作正在进行")
```

不会产生两个并发写命令，也不会在 QML 中返回同步成功 bool。

实现的 mutation 请求：

```text
requestCreateNote(...)
requestUpdateSelectedNote(...)
requestDeleteSelectedNote()
requestToggleSelectedPin()
requestBulkDelete(noteIds)
requestBulkPin(noteIds)
requestBulkUnpin(noteIds)
requestRestoreDeletedAt(index)
requestBulkRestoreDeleted(noteIds)
requestBulkHardDeleteDeleted(noteIds)
requestAddCustomTag(tag)
requestDeleteTag(tag)
```

### 5.6 Mutation Signals

数据库成功后发出：

```text
noteCreated(noteId)
noteUpdated(noteId)
notesSoftDeleted(noteIds)
notesRestored(noteIds)
notesHardDeleted(noteIds)
pinStateChanged(noteIds, pinned)
tagAdded(tag)
tagDeleted(tag)
```

失败时发出：

```text
operationFailed(operation, message)
```

Gate 1.6 的 QML 必须根据信号导航，不得根据 Slot 调用返回值假定数据库成功。

### 5.7 TagCatalog

ViewModel 使用 Gate 1.3 `TagCatalog`：

- `tagItems` 映射为 QML 可读 QVariantList；
- 新增标签经过 TagCatalog 验证和持久化；
- 删除标签前汇总 active 与 deleted notes 的完整已使用标签；
- 仍被任何便签引用的标签拒绝删除；
- 受保护标签和系统分类不能作为普通自定义标签操作；
- 查询返回便签中的新标签可由 TagCatalog observe 机制吸收。

### 5.8 任务关闭

`close()` 会取消 ViewModel 自己持有的 query/mutation task，避免 Gate 1.6 接入生命周期后遗留异步任务。

ViewModel 不负责关闭 DatabaseExecutor 或 Engine；它们继续由 `ApplicationLifecycle` 统一关闭。

---

## 6. 文件清单

### 新增

```text
pc-app-build/apps/notes-pyside/app/ui/note_list_model.py
pc-app-build/apps/notes-pyside/app/ui/notes_view_model.py
pc-app-build/tests/gate1_5/conftest.py
pc-app-build/tests/gate1_5/test_note_list_model.py
pc-app-build/tests/gate1_5/test_notes_view_model.py
pc-app-build/tests/gate1_5/test_gate1_5_architecture.py
pc-app-build/docs/report/GATE1_5_DELIVERY_REPORT.md
pc-app-build/docs/report/GATE1_5_LOCAL_ACCEPTANCE.md
VERIFY_GATE1_5.ps1
```

### 更新

```text
pc-app-build/apps/notes-pyside/app/ui/__init__.py
```

### 未修改

```text
pc-app-build/apps/notes-pyside/app/bootstrap.py
pc-app-build/apps/notes-pyside/app/qml/
pc-app-build/apps/notes-pyside/main.py
```

---

## 7. 自动测试覆盖

### 7.1 NoteListModel

覆盖：

- role 名固定；
- Domain Note 到 role 的映射；
- tags 文本映射；
- UTC 时间显示；
- source 显示；
- `note_id` 到 index 查找；
- 当前 ID 列表；
- Model reset。

### 7.2 NotesViewModel

覆盖：

- loadAll 异步查询；
- active selection；
- 刷新后按 note_id 保持选择；
- stale query 不覆盖最新结果；
- mutation busy；
- 并发 mutation 拒绝；
- 创建成功 Signal；
- 更新/删除类命令边界；
- 无效输入同步拒绝；
- operationFailed；
- close 取消任务。

### 7.3 架构测试

覆盖：

- ViewModel 不导入 SQLAlchemy；
- ViewModel 不持有 Session；
- ViewModel 不直接导入 Repository 实现；
- Model 只依赖 Domain Note 与 PySide6；
- 不恢复 HTTP 或旧 NotesController。

---

## 8. 本地验证命令

从仓库根目录进入 `pc-app-build`：

```powershell
cd C:\yuyinzhushou\note-assistant-app-runtime-v2\pc-app-build
```

### 8.1 编译检查

```powershell
python -m compileall -q apps\notes-pyside\app\ui tests\gate1_5
```

验收：

```text
命令退出码为 0
无 SyntaxError
```

### 8.2 Black

```powershell
python -m black --check apps\notes-pyside\app\ui tests\gate1_5
```

验收：

```text
All done!
退出码为 0
```

### 8.3 Ruff

```powershell
python -m ruff check apps\notes-pyside\app\ui tests\gate1_5
```

验收：

```text
All checks passed!
退出码为 0
```

### 8.4 Gate 1.5 定向测试

```powershell
python -m pytest tests\gate1_5 -q
```

验收：

```text
8 passed
0 failed
0 errors
```

### 8.5 Gate 1 累计全量测试

```powershell
python -m pytest tests\gate1_1 tests\gate1_2 tests\gate1_3 tests\gate1_4 tests\gate1_5 -q
```

验收：

```text
所有测试通过
0 failed
0 errors
无 pytest collection error
```

累计总数可能随你刚推送的迁移回归测试增加而变化，因此不把固定总数作为验收依据。

### 8.6 当前 main.py 启动 Smoke

```powershell
cd apps\notes-pyside
python main.py
```

验收：

- 应用窗口能够启动；
- 不出现 MigrationConflictError；
- 不出现 QML load error；
- 关闭窗口后进程正常退出；
- 不残留额外 Python/Sidecar 进程。

注意：Gate 1.5 仍使用 Bootstrap 中的 Empty ViewModel，因此此时 UI 不显示真实数据库内容是预期行为，不是 Gate 1.5 失败。正式接线属于 Gate 1.6。

---

## 9. 一键验证脚本

仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_5.ps1
```

脚本依次执行：

```text
compileall
Black --check
Ruff
Gate 1.5 定向测试
Gate 1.1～1.5 累计测试
```

脚本不会自动运行 `main.py`，因为桌面窗口需要人工关闭。启动 Smoke 按第 8.6 节手动执行。

---

## 10. Gate 1.5 验收清单

### 架构

- [ ] `NotesViewModel` 只依赖 Qt、Domain、Application Service 和 TagCatalog；
- [ ] UI 层不依赖 SQLAlchemy、Session 或 Repository 实现；
- [ ] 没有 HTTP、Sidecar 或旧 NotesController；
- [ ] Qt Model 只接收 Domain Note；
- [ ] 没有第二套 Note Domain 状态。

### Query

- [ ] Query Slot 不阻塞 Qt 主线程；
- [ ] 新查询可替换旧查询；
- [ ] stale result 不覆盖最新页面；
- [ ] all/pinned/deleted/tag/search 映射正确；
- [ ] query busy 状态正确结束。

### Selection

- [ ] 选择按 note_id 保持；
- [ ] 排序变化后不会选错便签；
- [ ] 空列表 index 为 -1；
- [ ] active/deleted 选择相互独立。

### Mutation

- [ ] Mutation 串行；
- [ ] 重复提交可见地拒绝；
- [ ] Slot 不同步返回数据库成功；
- [ ] 成功发对应 Signal；
- [ ] 失败发 operationFailed；
- [ ] 失败时 QML 后续应保留输入。

### 工程质量

- [ ] compileall 通过；
- [ ] Black 通过；
- [ ] Ruff 通过；
- [ ] Gate 1.5 为 8 passed；
- [ ] Gate 1.1～1.5 累计测试全绿；
- [ ] main.py Smoke 可启动并正常退出。

---

## 11. 已知限制

Gate 1.5 有意保留：

```text
Bootstrap -> EmptyNotesViewModel
QML -> Empty ViewModel Contract
```

因此当前限制：

- 正式 NotesViewModel 尚未在运行时实例化；
- QML 页面尚未显示真实数据库列表；
- 创建、编辑和删除页面尚未由成功 Signal 驱动导航；
- `main.py` 只能验证 Gate 1.1～1.4 组合未被 Gate 1.5 文件破坏。

这些限制将在 Gate 1.6 解除。

---

## 12. 下一阶段

Gate 1.6：QML 正式接线。

计划：

```text
Bootstrap 注入 NotesViewModel / NoteListModel
删除 EmptyNotesViewModel 运行时使用
QML 全部改用正式 ViewModel
创建/更新/删除使用 Signal 驱动导航
保留 220ms 搜索 debounce
错误时保留用户输入
QML Smoke 和真实数据库交互验证
```

建议提交：

```text
feat(ui): add asynchronous notes view model
```

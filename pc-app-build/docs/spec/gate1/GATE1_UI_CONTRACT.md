# Gate 1 QML / NotesViewModel Contract

状态：实施候选

## 1. 命名

QML Context Property 统一为：

```text
notesViewModel
notesListModel
deletedNotesListModel
```

不再注册 `notesController`。

`NotesViewModel` 是真正的新实现，不是旧 Controller Adapter。

## 2. Properties

```text
selectedIndex: int
hasSelection: bool
selectedTitle: string
selectedContent: string
selectedTagsText: string
selectedSourceText: string
selectedUpdatedText: string
selectedIsPinned: bool

deletedSelectedIndex: int

activeCategory: string
searchKeyword: string
resultCount: int
deletedResultCount: int

statusMessage: string
errorMessage: string
isBusy: bool
mutationBusy: bool

tagItems: QVariantList
```

删除旧属性：

```text
apiConnected
tagNames
```

## 3. Query Slots

```text
loadAll()
loadCategory(categoryKey)
loadTag(tag)
loadDeleted()
searchNotes(keyword)
refreshCurrentView()
```

这些 Slot 只调度 async task，不阻塞 Qt。

每次新 query：

- `query_generation += 1`；
- 取消上一 task，或让旧结果按 generation 丢弃；
- 最新结果更新 Model；
- 旧结果不得覆盖新页面。

## 4. Selection Slots

```text
selectNote(index)
selectDeletedNote(index)
currentNoteIds() -> QVariantList
currentDeletedNoteIds() -> QVariantList
```

列表刷新后：

- 若原 selected note_id 仍可见，保持选择；
- 否则默认选第一条；
- 空列表 selectedIndex=-1。

选择稳定性使用 note_id，不只使用旧 index。

## 5. Mutation Slots

全部为异步请求，不返回“数据库已成功”的同步 bool：

```text
requestCreateNote(title, content, tagsText, isPinned)
requestUpdateSelectedNote(title, content, tagsText)
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

命令提交前可同步拒绝明显无效输入，并设置 `errorMessage`；数据库结果通过 Signal 返回。

## 6. Signals

```text
noteCreated(int noteId)
noteUpdated(int noteId)
notesSoftDeleted(QVariantList noteIds)
notesRestored(QVariantList noteIds)
notesHardDeleted(QVariantList noteIds)
pinStateChanged(QVariantList noteIds, bool pinned)

tagAdded(string tag)
tagDeleted(string tag)

operationFailed(string operation, string message)
stateChanged()
selectedChanged()
statusChanged()
tagsChanged()
```

QML 导航规则：

- `noteCreated`：回到创建前分类并刷新；
- `noteUpdated`：回到全部或保持当前查询，由产品行为决定；Gate 1 默认保持当前视图；
- `notesSoftDeleted`：回到当前活动列表并刷新；
- 恢复/彻底删除：保持删除页并刷新；
- `operationFailed`：不导航，保留用户输入。

## 7. Busy 语义

```text
isBusy = queryBusy or mutationBusy
```

- Query 允许被新 Query 取代；
- Mutation 串行；
- Mutation 期间禁用修改按钮；
- 允许列表保持可滚动；
- 新 Mutation 在已有 Mutation 时直接拒绝并显示“操作正在进行”。

## 8. Model Roles

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

Qt Model 只接收 Domain Note，不接收 dict/ORM/Pydantic response。

## 9. Main.qml 修改

必须完成：

- 所有 `notesController` 改为 `notesViewModel`；
- 删除人工 startup/category/tag 延迟 Timer；
- 创建、修改、删除不再 `if (slot())`；
- 增加 Connections 监听成功/失败 Signal；
- 保留 220ms 搜索 debounce；
- QML 不保存数据库成功的假状态；
- QML 不直接操作 AppPaths、Session 或 Repository。

## 10. DeletedNotesPage

允许保留 UI 确认遮罩。

彻底删除流程：

```text
用户确认
-> requestBulkHardDeleteDeleted
-> ViewModel async mutation
-> 成功 Signal
-> 刷新删除列表
```

该 UI 确认属于手动操作，不等同于未来 MCP confirmation。

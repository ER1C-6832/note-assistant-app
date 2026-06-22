# PC UI Pages

Phase 4 connects the PC UI to the Notes API for manual note management.

## Implemented Pages

| Page | QML File | Status |
|---|---|---|
| 首页 / 便签总览 | `HomePage.qml` | ✅ |
| 手动新增便签 | `CreateNotePage.qml` | ✅ |
| 手动编辑便签 | `EditNotePage.qml` | ✅ |
| 手动删除确认 | `DeleteConfirmPage.qml` | ✅ |
| 手动模糊查找 / 搜索结果 | `SearchPage.qml` | ✅ |
| 语音助手待机状态 | `AssistantIdlePage.qml` | ✅ |
| 语音新增便签 | `AssistantCreatePage.qml` | ✅ |
| 语音查询 / 模糊查找便签 | `AssistantSearchPage.qml` | ✅ |
| 语音修改便签 | `AssistantUpdatePage.qml` | ✅ |
| 语音删除便签 / 多候选确认 | `AssistantDeletePage.qml` | ✅ |
| 设置页 | `SettingsPage.qml` | ✅ |
| 已删除列表 | `DeletedNotesPage.qml` | ✅ |

## Phase 4 Behavior

The following operations now use the real Notes API:

```text
1. Load notes from GET /api/notes
2. Create note through POST /api/notes
3. Update note through PATCH /api/notes/{id}
4. Soft-delete note through DELETE /api/notes/{id}
5. Search notes through GET /api/notes/search
6. Load deleted notes through GET /api/notes?include_deleted=true
```

The voice assistant pages remain visual states until the Sidecar phase.

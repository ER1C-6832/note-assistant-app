# PC UI Pages

The PC app is now a usable basic note app with real Notes API integration.

## Implemented User Features

```text
1. Load real notes
2. Create notes
3. Edit notes
4. Soft-delete notes
5. Restore deleted notes
6. Pin / unpin notes
7. View pinned notes
8. Fuzzy search notes
```

## Main Pages

| Page | QML File | Status |
|---|---|---|
| 首页 / 便签总览 | `HomePage.qml` | ✅ |
| 新建便签 | `CreateNotePage.qml` | ✅ |
| 编辑便签 | `EditNotePage.qml` | ✅ |
| 删除确认 | `DeleteConfirmPage.qml` | ✅ |
| 搜索结果 | `SearchPage.qml` | ✅ |
| 已删除 | `DeletedNotesPage.qml` | ✅ |
| 设置 | `SettingsPage.qml` | ✅ |
| 语音助手 | `AssistantIdlePage.qml` | ✅ |

## Current Boundary

Manual note management is functional. Voice assistant pages remain visual states
until Sidecar integration.

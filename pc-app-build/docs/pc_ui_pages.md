# PC UI Pages

Phase 3 implements the static PySide6 + QML PC UI based on the Pencil prototype.

## Implemented Pages

| Page | QML File | Status |
|---|---|---|
| PC-01 首页 / 便签总览 | `HomePage.qml` | ✅ |
| PC-02 手动新增便签 | `CreateNotePage.qml` | ✅ |
| PC-03 手动编辑便签 | `EditNotePage.qml` | ✅ |
| PC-04 手动删除确认 | `DeleteConfirmPage.qml` | ✅ |
| PC-05 手动模糊查找 / 搜索结果 | `SearchPage.qml` | ✅ |
| PC-06 语音助手浮窗 - 待机状态 | `AssistantIdlePage.qml` | ✅ |
| PC-07 语音新增便签 | `AssistantCreatePage.qml` | ✅ |
| PC-08 语音查询 / 模糊查找便签 | `AssistantSearchPage.qml` | ✅ |
| PC-09 语音修改便签 | `AssistantUpdatePage.qml` | ✅ |
| PC-10 语音删除便签 / 多候选确认 | `AssistantDeletePage.qml` | ✅ |
| PC-11 设置页 | `SettingsPage.qml` | ✅ |

## Implemented Components

| Component | Purpose |
|---|---|
| `TopBar.qml` | App title, search box, new note button, status badges |
| `Sidebar.qml` | Categories, settings entry, voice assistant entry, service status |
| `NoteList.qml` | Note card list |
| `NoteCard.qml` | Note summary card |
| `DetailPanel.qml` | Note detail panel |
| `AssistantPanel.qml` | Assistant status, transcript, reply, tool result |
| `StatusBadge.qml` | Connection/status badge |
| `VoiceButton.qml` | Floating voice assistant button |

## Phase Boundary

Phase 3 is a static UI and page-switching implementation.

Real data integration starts in Phase 4:

```text
PySide6 App -> Notes API -> SQLite
```

Sidecar event integration starts in Phase 5:

```text
PySide6 App -> PC Assistant Sidecar -> py-xiaozhi
```

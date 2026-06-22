# PC UI Pages

Phase 3.1 refines the static PySide6 + QML PC UI based on the Pencil prototype
and fixes the Phase 3 navigation / visual style issues.

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
| 已删除列表 | `DeletedNotesPage.qml` | ✅ |

## Components

| Component | Purpose |
|---|---|
| `AppButton.qml` | Unified modern button replacing Qt default buttons |
| `SidebarItem.qml` | Sidebar menu item with correct active state |
| `SearchBox.qml` | Modern top search box |
| `TopBar.qml` | App title, search box, service status badges |
| `Sidebar.qml` | Category navigation, assistant/settings entry, service status |
| `NoteList.qml` | Note list with list-level new note button |
| `NoteCard.qml` | Note summary card |
| `DetailPanel.qml` | Right-side note detail panel |
| `AssistantPanel.qml` | Assistant status, transcript, reply, tool result |
| `StatusBadge.qml` | Connection/status badge |
| `VoiceButton.qml` | Floating voice assistant button |

## Phase 3.1 Fixes

```text
1. Fixed sidebar active-state logic.
2. Split deleted list from delete confirmation.
3. Replaced default Qt buttons with AppButton.
4. Replaced sidebar buttons with SidebarItem.
5. Moved New Note from top search area to note list header.
6. Removed top-right Settings button; left sidebar owns Settings navigation.
7. Modernized edit/delete/search/new button styling.
```

## Phase Boundary

Phase 3.1 is still static UI only.

Real data integration starts in Phase 4:

```text
PySide6 App -> Notes API -> SQLite
```

Sidecar event integration starts in Phase 5:

```text
PySide6 App -> PC Assistant Sidecar -> py-xiaozhi
```

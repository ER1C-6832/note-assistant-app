# Gate 1：单进程便签恢复规格

状态：实施候选  
目标：恢复手动便签，并建立 Assistant 后续可直接复用的本地业务边界。

## 1. 成功定义

Gate 1 完成后：

```text
一个 Python 进程
├─ PySide6 / QML
├─ qasync
├─ NotesViewModel
├─ NoteCommandService
├─ NoteQueryService
├─ SqlAlchemyNoteRepository
├─ TagCatalog
└─ SQLite
```

必须满足：

- App 可正常启动和退出；
- 手动创建、查询、编辑、置顶、软删除、恢复、彻底删除可用；
- 批量操作是单事务；
- QML 不直接访问数据库；
- 无 localhost HTTP；
- 无 Sidecar；
- 无外部 Runtime；
- UI 与未来 MCP 都能调用同一个 `NoteCommandService`；
- 运行时数据位于 `%LOCALAPPDATA%\NoteAssistant\`。

## 2. 非目标

Gate 1 不实现：

- Assistant Controller；
- WebSocket；
- 音频；
- MCP JSON-RPC；
- 语音工具；
- KWS；
- 数据同步；
- 设备管理；
- 云端账户；
- Android 全量 Note Schema；
- 最终打包。

## 3. 目标目录

```text
apps/notes-pyside/
├─ main.py
└─ app/
   ├─ __init__.py
   ├─ bootstrap.py
   ├─ app_paths.py
   ├─ lifecycle.py
   │
   ├─ notes/
   │  ├─ __init__.py
   │  ├─ domain.py
   │  ├─ commands.py
   │  ├─ repository.py
   │  ├─ sqlalchemy_models.py
   │  ├─ sqlalchemy_repository.py
   │  ├─ database_executor.py
   │  ├─ command_service.py
   │  ├─ query_service.py
   │  ├─ tag_catalog.py
   │  └─ migration.py
   │
   ├─ ui/
   │  ├─ __init__.py
   │  ├─ note_list_model.py
   │  └─ notes_view_model.py
   │
   └─ qml/
```

删除并替换当前过渡文件：

```text
app/notes/db.py
app/notes/models.py
app/notes/note_service.py
app/notes/schemas.py
app/notes/search_service.py
app/models/note.py
app/controllers/
app/models/
```

旧代码只作为行为参考，不形成兼容层。

## 4. 模块依赖

```text
QML
  -> NotesViewModel
      -> NoteCommandService / NoteQueryService / TagCatalog
          -> NoteRepository Protocol
              -> SqlAlchemyNoteRepository
                  -> SQLAlchemy / SQLite
```

约束：

- `notes/` 禁止导入 PySide6；
- `ui/` 允许导入 PySide6；
- Repository 禁止返回 ORM Row；
- ViewModel 禁止持有 SQLAlchemy Session；
- QML 禁止调用 Repository；
- Bootstrap 是唯一 Composition Root。

## 5. 领域模型

```python
@dataclass(frozen=True, slots=True)
class Note:
    id: int
    title: str
    content: str
    tags: tuple[str, ...]
    is_pinned: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    source: NoteSource
```

```python
class NoteSource(StrEnum):
    MANUAL = "manual"
    VOICE_PC = "voice_pc"
    VOICE_ANDROID = "voice_android"
    IMPORTED = "imported"
```

Gate 1 不新增 Android 的 todo type、archive、revision 等字段。PC 当前“待办”继续使用受保护标签 `待办` 表达。

## 6. 输入命令

```python
@dataclass(frozen=True, slots=True)
class CreateNoteCommand:
    title: str
    content: str
    tags: tuple[str, ...]
    is_pinned: bool = False
    source: NoteSource = NoteSource.MANUAL

@dataclass(frozen=True, slots=True)
class UpdateNoteCommand:
    note_id: int
    title: str
    content: str
    tags: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class SetPinnedCommand:
    note_ids: tuple[int, ...]
    is_pinned: bool

@dataclass(frozen=True, slots=True)
class SoftDeleteCommand:
    note_ids: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class RestoreCommand:
    note_ids: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class HardDeleteCommand:
    note_ids: tuple[int, ...]
```

统一验证：

- title 去除首尾空白；
- title 必填，1～200 字符；
- content 保留内部换行，去除末尾多余空白；
- tags 去空白、去重、保持首次出现顺序；
- note_ids 转为正整数、去重；
- 空批量输入失败；
- Repository 不负责 UI 文案验证。

## 7. 服务边界

### NoteCommandService

异步公开接口：

```python
async def create(command: CreateNoteCommand) -> Note
async def update(command: UpdateNoteCommand) -> Note
async def set_pinned(command: SetPinnedCommand) -> tuple[Note, ...]
async def soft_delete(command: SoftDeleteCommand) -> int
async def restore(command: RestoreCommand) -> int
async def hard_delete(command: HardDeleteCommand) -> int
```

所有写操作：

- 进入单线程 DB Executor；
- 每个 command 一个事务；
- 批量操作一次提交；
- 失败整体回滚；
- 返回领域对象或计数；
- 不返回 ORM 实体。

### NoteQueryService

```python
async def list_all() -> tuple[Note, ...]
async def list_pinned() -> tuple[Note, ...]
async def list_deleted() -> tuple[Note, ...]
async def list_by_tag(tag: str) -> tuple[Note, ...]
async def search(query: str, limit: int = 100) -> tuple[Note, ...]
async def get(note_id: int, include_deleted: bool = False) -> Note | None
```

排序：

```text
is_pinned DESC
updated_at DESC
id DESC
```

删除列表忽略 pin 排序，仅按 `updated_at DESC, id DESC`。

## 8. Repository 契约

Repository 是同步接口，只能在 DB Executor 中调用。

```python
class NoteRepository(Protocol):
    def create(self, command: CreateNoteCommand) -> Note: ...
    def update(self, command: UpdateNoteCommand) -> Note: ...
    def list_active(self) -> tuple[Note, ...]: ...
    def list_deleted(self) -> tuple[Note, ...]: ...
    def get(self, note_id: int, include_deleted: bool = False) -> Note | None: ...
    def set_pinned_many(self, ids: tuple[int, ...], value: bool) -> tuple[Note, ...]: ...
    def soft_delete_many(self, ids: tuple[int, ...]) -> int: ...
    def restore_many(self, ids: tuple[int, ...]) -> int: ...
    def hard_delete_many(self, ids: tuple[int, ...]) -> int: ...
```

Repository 内部必须使用 Session transaction scope，不允许每条记录单独 commit。

## 9. SQLite Schema

保持旧表兼容：

```text
notes
├─ id INTEGER PRIMARY KEY
├─ title VARCHAR(200) NOT NULL
├─ content TEXT NOT NULL
├─ tags TEXT NOT NULL DEFAULT '[]'
├─ is_pinned BOOLEAN NOT NULL DEFAULT 0
├─ is_deleted BOOLEAN NOT NULL DEFAULT 0
├─ created_at DATETIME NOT NULL
├─ updated_at DATETIME NOT NULL
└─ source VARCHAR(50) NOT NULL DEFAULT 'manual'
```

Gate 1 不做破坏性 schema migration。

Engine 初始化：

```text
journal_mode=WAL
synchronous=NORMAL
foreign_keys=ON
busy_timeout=3000
```

SQLAlchemy Session：

```text
autoflush=False
expire_on_commit=False
Session 每次操作创建并关闭
```

## 10. 日期时间

数据库兼容旧 naive UTC：

- 写入 UTC naive datetime；
- 读取时若无 timezone，解释为 UTC；
- Domain 中使用 timezone-aware UTC；
- UI 显示系统本地时间；
- 不在 Domain 固定 UTC+8。

## 11. 标签

`TagCatalog` 负责用户标签，不依赖 Qt。

默认标签：

```text
客户
报价
屏幕
样机
游戏手柄
测试
包装
跟进
```

受保护标签：

```text
待办
```

规则：

- 标签目录保存在 `%LOCALAPPDATA%\NoteAssistant\data\custom_tags.json`；
- 添加标签时拒绝空值和系统分类名；
- 删除受保护标签失败；
- 有任何活动或已删除便签引用时，标签不可删除；
- 从数据库观察到的新标签自动补入 Catalog；
- 删除 Catalog 标签不修改便签；
- 精确标签匹配，禁止 JSON 字符串子串误匹配。

## 12. 查询与搜索

搜索范围：

- title；
- content；
- tags。

Gate 1 使用 SQLite LIKE，limit 默认 100。

要求：

- 搜索结果不包含软删除；
- 空搜索退回全部列表；
- 快速连续搜索只显示最新 generation 的结果；
- 过期查询结果必须丢弃；
- 搜索失败不清空上一份有效数据。

## 13. App 启动

```text
1. 创建 QGuiApplication
2. 创建 qasync QEventLoop
3. Resolve AppPaths
4. 执行数据库迁移检查
5. 创建 Engine / Session factory
6. 创建 DB Executor
7. 创建 Repository
8. 创建 CommandService / QueryService / TagCatalog
9. 创建 NoteListModel / DeletedNoteListModel
10. 创建 NotesViewModel
11. 注册 QML context
12. 加载 Main.qml
13. QML ready 后调度 load_all
```

删除旧 QML 的：

- 260ms startup timer；
- 30ms category timer；
- 30ms tag timer。

保留 220ms 搜索 debounce，或移动到 ViewModel；两者只能保留一个。

## 14. App 关闭

```text
1. 禁止接受新 mutation
2. 取消当前 query task
3. 等待当前 mutation，最多 1 秒
4. shutdown DB Executor
5. dispose SQLAlchemy Engine
6. 退出 qasync/Qt
```

禁止扫描或结束其他 Python 进程。

## 15. 依赖

Gate 1 添加：

```text
qasync
```

开发依赖添加：

```text
pytest-qt
```

Gate 1 不添加：

```text
websockets
sounddevice
numpy
opuslib
```

这些属于后续 Runtime Gate。

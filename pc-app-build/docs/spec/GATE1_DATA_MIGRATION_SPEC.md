# Gate 1 数据路径与迁移规格

状态：实施候选

## 1. 目标路径

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\
│  ├─ notes.db
│  └─ custom_tags.json
├─ logs\
└─ backups\
```

若 `LOCALAPPDATA` 不存在，开发环境 fallback：

```text
~/.note-assistant/
```

生产 Windows 不应触发 fallback。

## 2. AppPaths

```python
@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data_dir: Path
    notes_db: Path
    custom_tags: Path
    logs_dir: Path
    backups_dir: Path
```

`AppPaths.resolve()` 只计算路径；`ensure_directories()` 显式创建目录。

测试必须允许注入临时 root。

## 3. 迁移触发

仅当目标 `notes.db` 不存在时尝试迁移。

候选来源按优先级：

1. 环境变量 `NOTE_ASSISTANT_LEGACY_DB_PATH`；
2. 当前 Worktree 内历史路径；
3. 同级 legacy Worktree：
   `..\note-assistant-app\pc-app-build\services\notes-api\data\notes.db`；
4. 当前迁移阶段可能生成的：
   `apps\notes-pyside\app\data\notes.db`。

## 4. 候选选择

- 0 个有效来源：创建空数据库；
- 1 个有效来源：执行迁移；
- 多个不同来源：拒绝自动选择，输出候选列表；
- 多个路径指向同一文件：视为一个来源。

不得用“最新修改时间”自动猜测用户数据。

## 5. 源数据库验证

迁移前：

```sql
PRAGMA quick_check;
```

必须返回 `ok`。

并验证：

- 存在 `notes` 表；
- 必需列齐全；
- 文件可读；
- 文件非目标路径本身。

验证失败：

- 不创建目标；
- 不修改源；
- 显示可诊断错误。

## 6. 复制方式

优先使用 SQLite backup API：

```python
source_connection.backup(target_connection)
```

不在数据库可能被占用时直接 `shutil.copyfile`。

流程：

```text
source
-> target.tmp
-> quick_check target.tmp
-> atomic replace target
```

源文件永不删除、永不移动。

## 7. 目标保护

若目标已存在：

- 不覆盖；
- 不重新迁移；
- 正常打开目标。

若目标存在但 quick_check 失败：

- 将其复制到 backups；
- 阻止应用继续写入；
- 要求用户显式处理；
- 不自动用 legacy 覆盖损坏目标。

## 8. 标签迁移

`custom_tags.json`：

- 目标不存在时才迁移；
- 候选逻辑与 DB 类似；
- JSON 必须为字符串数组；
- 规范化、去空、去重；
- 迁移后与数据库观察标签合并。

## 9. 备份

首次成功启动目标 DB 后，创建：

```text
backups\notes-pre-gate1-YYYYMMDD-HHMMSS.db
```

若迁移源已在 legacy 目录中，源本身已是保留副本，但仍记录迁移报告。

## 10. 迁移报告

写入：

```text
logs\migration-gate1.json
```

字段：

```text
started_at
finished_at
source_db
target_db
source_size
target_size
quick_check
notes_count
tags_source
status
error
```

不得包含便签正文。

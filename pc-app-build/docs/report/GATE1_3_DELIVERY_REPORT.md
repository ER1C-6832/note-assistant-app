# Gate 1.3 交付报告

## 1. 交付范围

本次严格执行 Gate 1.3，不提前实现 Application Service、NotesViewModel 或 QML 数据接线。

新增：

```text
app/notes/migration.py
app/notes/tag_catalog.py
tests/gate1_3/
```

更新：

```text
app/notes/__init__.py
```

## 2. 数据迁移

### 2.1 数据位置

目标继续使用 Gate 1.1 的 `AppPaths`：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\notes.db
├─ data\custom_tags.json
├─ backups\
└─ logs\migration-gate1.json
```

### 2.2 数据库候选

按规格发现：

1. `NOTE_ASSISTANT_LEGACY_DB_PATH`；
2. 当前 Worktree 的旧 `services/notes-api/data/notes.db`；
3. 同级 legacy Worktree；
4. 过渡期 `app/data/notes.db`。

候选只按真实文件去重。多个不同候选同时存在时直接失败，不根据修改时间猜测。

### 2.3 验证与迁移

源数据库和现有目标数据库都会检查：

- 文件存在且为普通文件；
- `PRAGMA quick_check` 返回 `ok`；
- 存在 `notes` 表；
- 旧 Schema 必需列完整；
- 可读取便签计数。

迁移使用 Python SQLite Backup API：

```text
source -> .notes.db.gate1.tmp -> quick_check -> os.replace(target)
```

源文件不删除、不移动、不修改。

### 2.4 目标保护

- 目标已存在且有效：不覆盖、不重新迁移；
- 目标损坏：复制到 `backups/notes-corrupt-*.db` 后阻止继续；
- 首次成功准备：创建 `backups/notes-pre-gate1-*.db`；
- 已有成功报告时重复运行不会重复创建首次备份。

### 2.5 迁移报告

报告只记录：

```text
时间
源/目标路径
文件大小
quick_check
便签数量
标签来源
备份路径
状态
错误
```

不记录标题、正文或其他便签内容。

## 3. TagCatalog

实现：

- 缺失文件时一次性写入默认标签；
- 已存在文件不重新注入被用户删除的默认标签；
- 标签去空、去重并保持顺序；
- `待办` 作为受保护标签；
- `全部/置顶/已删除` 作为系统分类名；
- 观察数据库标签时只追加新标签；
- 删除时必须显式传入活动和已删除便签的完整 `used_tags`；
- 精确成员判断，`客户` 不会误匹配 `客户服务`；
- JSON 通过临时文件和 `os.replace` 原子写入；
- 非数组、非字符串成员等损坏文件不会被自动覆盖。

## 4. 暂不接入 Bootstrap 的原因

Gate 1.3 的实施计划输出是迁移模块和 TagCatalog。当前 Bootstrap 仍使用 EmptyNotesViewModel，Repository 也尚未由 Composition Root 实例化。

因此本次不在启动时执行真实迁移，避免在 Application Service 和最终错误呈现尚未建立时提前产生用户数据副作用。Gate 1.4 组合 CommandService/QueryService 时再统一接入：

```text
AppPaths
-> prepare_gate1_local_data
-> Engine / SessionFactory
-> DatabaseExecutor
-> Repository
-> TagCatalog
-> Application Services
```

## 5. 自动验证

交付文件实际执行：

```text
Black --check：通过
Ruff：通过
compileall：通过
Gate 1.2 + Gate 1.3：46 passed
```

Gate 1.3 自身包含 22 个测试，覆盖：

- 无源创建空数据库；
- 单源迁移；
- 数据库多候选冲突；
- 同文件候选去重；
- 损坏源；
- 缺列旧 Schema；
- 已有目标不覆盖；
- 损坏目标取证备份；
- 标签源迁移；
- 标签多候选冲突；
- 标签 JSON 错误；
- 幂等与首次备份；
- 默认标签；
- 观察标签；
- 精确使用判断；
- 删除持久化；
- 架构禁止 PySide6；
- 报告不包含正文数据字段。

## 6. 本地验收标准

```bat
python -m black --check apps\notes-pyside\app\notes tests\gate1_3
python -m ruff check apps\notes-pyside\app\notes tests\gate1_3
python -m pytest tests\gate1_1 tests\gate1_2 tests\gate1_3 -q
```

`main.py` 能继续启动即可。Gate 1.3 不要求 UI 展示真实数据库内容。

## 7. 下一步

下一工作包为 Gate 1.4：

```text
NoteCommandService
NoteQueryService
DatabaseExecutor 调用边界
Bootstrap 组合迁移、Repository、TagCatalog 和 Service
```

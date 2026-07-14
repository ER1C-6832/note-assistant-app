# Gate 1.2 交付报告：Domain 与 Persistence

## 交付范围

本次只完成 Gate 1.2：

- 框架无关的 `Note` Domain；
- 经过规范化的 Mutation Commands；
- `NoteRepository` Protocol；
- 兼容旧表的 SQLAlchemy ORM；
- SQLite Repository；
- 单线程 `DatabaseExecutor`；
- Repository、事务、PRAGMA、UTC 和架构测试；
- 清理 editable install 产生的 `note_assistant.egg-info`。

未接入 Bootstrap、QML 或 EmptyNotesViewModel。App 在 Gate 1.2 后仍显示空列表，这是计划内状态；Gate 1.4/1.5 才接入 Service 和 ViewModel。

## 架构落实

```text
Qt/qasync 主线程
    -> 后续 Application Service
        -> DatabaseExecutor(max_workers=1)
            -> SqlAlchemyNoteRepository
                -> SQLite
```

`app/notes` 中没有 PySide6 导入。Repository 是同步接口，只允许在后续 Application Service 中通过 DatabaseExecutor 调用。

## 数据与事务

- 保持旧 `notes` 表字段兼容；
- SQLite 使用 WAL、NORMAL synchronous、foreign_keys、3000ms busy_timeout；
- Session 使用 `autoflush=False`、`expire_on_commit=False`；
- 每次 Repository 操作创建并关闭自己的 Session；
- 批量置顶、软删除、恢复、彻底删除均为单事务；
- 缺失 ID 或状态错误会在任何修改前失败；
- 彻底删除只允许作用于已软删除便签；
- 标签按 JSON 解析后精确匹配，不使用 `%tag%` 作为分类匹配；
- 旧 naive datetime 按 UTC 解释，Domain 对外始终返回 timezone-aware UTC。

## egg-info 处理

`note_assistant.egg-info` 是 editable install 自动生成的构建元数据，不属于源码，不应提交。

本交付：

- 在 `.gitignore` 中加入 `*.egg-info/`；
- 要求删除当前已跟踪目录；
- 后续执行 `pip install -e` 仍会在本地生成该目录，但 Git 不再显示它。

## 测试

本包包含：

- 命令输入规范化；
- CRUD；
- source 保留；
- active/pinned/deleted/restore；
- hard delete 状态保护；
- 精确标签；
- title/content/tag 搜索；
- 批量缺失 ID 回滚；
- 批量状态错误回滚；
- 排序；
- legacy naive UTC；
- SQLite PRAGMA；
- 单线程 Executor 串行性；
- Executor 关闭后拒绝新任务；
- Notes Package 禁止 PySide6；
- egg-info ignore。

## 手工复制

本包不提供覆盖脚本。将 `payload` 下的内容按相同目录复制到仓库根目录，然后按 `DELETE_THESE_PATHS.txt` 删除旧文件。

## 建议提交

```text
refactor(notes): rebuild in-process note domain and repository
```

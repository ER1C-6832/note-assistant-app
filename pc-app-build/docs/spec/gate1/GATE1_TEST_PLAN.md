# Gate 1 测试计划

状态：实施候选

## 1. 测试层级

### Unit

不启动 Qt：

- tag 解析与去重；
- title/content 验证；
- AppPaths；
- Domain/ORM mapper；
- Repository CRUD；
- 批量事务；
- 精确标签过滤；
- 查询排序；
- 搜索；
- Migration discovery；
- SQLite quick_check；
- TagCatalog。

### ViewModel

使用 `pytest-qt` 和 Fake Service：

- Property 初始值；
- Selection；
- 成功 Signal；
- 失败 Signal；
- busy 状态；
- stale query 丢弃；
- mutation 串行；
- Model role 输出。

### Integration

使用临时 SQLite：

- CommandService -> Repository -> DB；
- QueryService -> Repository -> DB；
- UI 与未来 MCP 使用同一 CommandService 实例的 Composition Test；
- 旧 schema DB 迁移；
- QML offscreen load。

### Manual

Windows 真机：

- 启动；
- CRUD；
- 标签；
- 多选；
- 已删除；
- 重启持久化；
- legacy 数据迁移；
- 退出无残留进程。

## 2. Repository 必测

1. create；
2. get；
3. update；
4. list active；
5. list pinned；
6. exact tag；
7. search title；
8. search content；
9. search tag；
10. soft delete；
11. restore；
12. hard delete；
13. bulk pin atomic；
14. bulk delete atomic；
15. missing ID rollback；
16. sorting；
17. source preservation；
18. old naive UTC conversion。

## 3. 批量事务

构造 3 个 ID，其中 1 个不存在。

Gate 1 决策：

- `set_pinned_many`：若任一 ID 不存在，整体失败并回滚；
- `soft_delete_many`：同上；
- `restore_many`：同上；
- `hard_delete_many`：同上。

不能出现“前两条已提交、第三条失败”。

## 4. Query Generation

测试：

```text
Query A 启动
Query B 启动
B 先返回
A 后返回
```

最终 UI 必须显示 B。

## 5. Migration

必须覆盖：

- 目标缺失 + 无源；
- 目标缺失 + 单一有效源；
- 多源冲突；
- 源 quick_check 失败；
- 源缺列；
- 目标已存在；
- 目标损坏；
- 标签 JSON 非数组；
- 迁移幂等；
- 迁移不删除源。

## 6. QML Smoke

环境：

```text
QT_QPA_PLATFORM=offscreen
```

断言：

- `Main.qml` 加载成功；
- 无 missing context property；
- `notesViewModel` 已注册；
- 两个 ListModel 已注册；
- 无 `notesController` 残留；
- 无旧 Timer；
- 创建页、编辑页、删除页组件可实例化。

## 7. 静态检查

```text
ruff
black --check
pytest
```

额外 grep：

```text
notesController
NotesApi
sidecar
py-xiaozhi
FastAPI
uvicorn
```

Gate 1 源码中必须无命中，文档历史说明除外。

## 8. 手工验收矩阵

| 场景 | 预期 |
|---|---|
| 首次无旧数据启动 | 创建空 DB，UI 正常 |
| 有 legacy DB 首次启动 | 数据完整迁移，源不变 |
| 创建普通便签 | 当前分类显示 |
| 创建待办便签 | 待办分类显示 |
| 编辑 | 当前视图刷新且选择稳定 |
| 置顶 | 排序立即变化 |
| 搜索快速输入 | 只显示最后关键词 |
| 单条删除 | 进入已删除 |
| 批量删除 | 单事务完成 |
| 恢复 | 返回活动列表 |
| 彻底删除 | 目标消失 |
| 标签仍被引用 | 不允许删除 |
| 重启 | 数据和标签持久化 |
| 退出 | 无第二 Python 进程 |

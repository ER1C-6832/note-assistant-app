# ADR-005：SQLite 单线程 Executor

状态：Accepted for Gate 1

## 决策

所有 SQLAlchemy/SQLite 操作通过一个 `ThreadPoolExecutor(max_workers=1)` 执行。

## 原因

- Qt/qasync 主线程不能执行阻塞 SQL；
- SQLite 写操作天然需要序列化；
- Session 和 connection 线程所有权更容易审计；
- 不需要为本地便签引入第二进程。

## 后果

- Repository 保持同步；
- Application Service 提供 async 接口；
- 批量操作必须一个 Executor 调用、一个事务；
- 关闭时必须有界 shutdown。

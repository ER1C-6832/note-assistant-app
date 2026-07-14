# ADR-006：QML 异步命令契约

状态：Accepted for Gate 1

## 决策

QML mutation Slot 只提交请求，数据库成功或失败通过 Qt Signal 返回；不再同步返回 bool 表示完成。

## 原因

旧 UI 在同步 HTTP 写入后立即根据 bool 导航。新架构要求数据库离开 Qt 主线程，因此同步成功语义不再成立。

## 后果

- 创建、编辑、删除页面监听成功 Signal；
- 失败时页面和输入保持不变；
- ViewModel 管理 busy 和 mutation 串行；
- QML 不推断数据库结果。

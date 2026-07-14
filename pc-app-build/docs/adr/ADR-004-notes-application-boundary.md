# ADR-004：统一便签应用边界

状态：Accepted for Gate 1

## 决策

手动 UI 和未来 MCP 工具共同调用 `NoteCommandService`，查询共同使用 `NoteQueryService`。

## 原因

旧架构中 QML 和语音分别通过 HTTP 进入 Notes API，造成进程和协议成本。新架构需要一个进程内可信业务边界。

## 后果

- ViewModel 不直接写 Repository；
- MCP 不直接写 Repository；
- 验证、事务和错误语义集中；
- Gate 1 必须先恢复这条边界，再开发 Assistant。

# Gate 5 Specification Index

状态：实施候选（Implementation Candidate）  
目标分支：`rewrite/single-process-runtime`  
制定基线：`c6666558970a9acc09841ae9eb594ef479defb3c`

## 1. Gate 5 目标

Gate 5 在现有单进程 PC Runtime 内接通 Xiaozhi MCP，使助手能够通过真实、可确认、可审计的工具链操作当前 PC 便签功能。

本 Gate 不增加 Sidecar、localhost HTTP、外部 MCP 进程或第二个 Runtime。

冻结工具数量：**31 个**。

```text
8  note read / resolve
8  note mutation
5  tag tools
7  UI tools
3  confirmation tools
= 31 tools
```

Android 当前 Phase 4 契约包含 39 个工具。PC Gate 5 复用其中有真实业务支撑的 31 个；其余 8 个依赖 PC 当前不存在的 archive、done、revision 或 tag rename 能力，不得伪装为可用工具。

## 2. 文档清单

| 文件 | 用途 |
|---|---|
| `GATE5_MCP_NOTES_TOOLS_SPEC.md` | 总规格、31 工具目录、协议、安全、并发和生命周期契约 |
| `GATE5_IMPLEMENTATION_PLAN.md` | 5 个子阶段的实施顺序、交付物和退出条件 |
| `GATE5_TEST_AND_ACCEPTANCE_PLAN.md` | Automated、Fake、Real、异常矩阵和最终签字标准 |

## 3. 对既有文档的关系

本规格在 Gate 5 范围内 supersede `docs/spec/gate0/MCP_NOTE_TOOL_SCOPE.md` 的“三工具 MVP”数量定义。

仍然保留 Gate 0 的以下约束：

- MCP 与手动 UI 共用 `NoteCommandService` / `NoteQueryService`；
- 未注册工具 fail-closed；
- 删除默认软删除；
- 高风险操作必须显式确认；
- request id 去重；
- 单进程、单 Controller state writer、单 WebSocket sender；
- 不得直接调用 Repository、SQLite、QML 或 DAO。

Gate 0 的三个工具不是错误，而是早期 smoke scope；Gate 5 的正式产品范围以本目录为准。

## 4. Gate 5 子阶段

Gate 5 固定为 5 个子阶段，避免过度拆分：

```text
5.0  MCP protocol core and 31-tool registry
5.1  Read / resolve and UI navigation
5.2  Note and tag mutations
5.3  Confirmation and high-risk closure
5.4  Cumulative, Real acceptance and freeze
```

不得在 5.0 之前并行实现真实写工具；不得在 5.3 之前把高风险工具标为可执行完成。

## 5. 完成定义

Gate 5 只有同时满足以下条件才可标记 Accepted：

- Real `initialize`、`tools/list`、`tools/call` 闭环；
- `tools/list` 精确返回 31 个可执行描述符；
- 真实创建、读取、搜索、修改、标签、置顶、软删除、拒绝、确认、恢复闭环；
- UI 无需重启或手动刷新即可反映 MCP 变更；
- 重复请求不产生重复写入；
- 高风险操作在确认前零写入；
- 原始 note content、MCP arguments、token 和完整 identity 不进入普通日志、AssistantState 或报告；
- disconnect、disable、shutdown 后没有 MCP worker、tool task、pending confirmation、response sender 或第二 Python 进程残留；
- Gate 1 through Gate 5 累计自动回归通过。


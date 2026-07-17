# Gate 5.4 Implementation Report

状态：实现候选，等待 Windows 全量与 Real 人工验收  
基线：`3ec36d9fe90e57e1b49daeb4e8ce8f7779b7b719` (`confirmation tool`)

## 实现内容

- 31 个工具名和 schema 不变，工具描述升级为中文 intent-routing cards；
- 增加文件/系统记事本负向路由、模糊目标先 resolve/search、确认前先 list pending 等规则；
- 新增安全口语 query 归一化和明确 ID 提取；
- `notes.search` 支持清理后的精确主题优先、fallback terms 有界搜索；
- `notes.resolve` 支持长句明确 ID、引号标题和口语主题；纯“刚才那条”多候选不猜；
- 新增 31-tool 真实语言验收目录；
- 新增不自动发命令的 Real 手工记录器；
- 新增 Gate 5.4 freeze 与 cumulative verifier；
- 新增 ADR-009 和最终验收报告模板。

## 参考与未采用内容

参考旧 main 的丰富 trigger descriptions、便签与文件工具分流、含糊目标先 search；参考旧阶段/Android 工具面的 read-before-write、UI action 和 confirmation 语义。

未复制：Sidecar、HTTP NotesApiClient、py-xiaozhi decorator、PC-only alias、全局上下文、Android archive/done/revision 工具。

## 本地自动验证范围

本地环境可运行 framework-neutral MCP/SQLite 测试、Black、Ruff、compileall 和 freeze verifier。由于当前容器没有完整 Windows Qt/audio/credential 环境，Real UI、麦克风和真实 endpoint 结果必须由 Windows 日志签字。

## 接受条件

Gate 5 只有在以下全部满足后才能标记 Accepted：

- Windows `pytest -W error tests` 全绿；
- Gate 5.0～5.4 cumulative 全绿；
- 真实 `tools/list == 31`；
- 用户自由自然语言覆盖 CRUD、标签、UI、确认/拒绝和恢复；
- 高风险确认前零写入，确认/拒绝只产生一个终态；
- terminal resource matrix 全零。

## 本次候选包本地证据

```text
Black / Ruff / compileall: passed
Framework-neutral Gate 5.0 through Gate 5.4 behavior tests: 49 passed
Gate 5.3 + Gate 5.4 architecture tests: 8 passed
Gate 5.3 confirmation verifier: fake_gate_complete
Gate 5.4 freeze verifier: gate5_4_freeze_complete
Tool count: 31
Name-set SHA-256: 58840e01b41f8f3cf08a406428bab9261d07a664be7212d3d650e5016da22693
Serialized tools/list catalog: 16103 bytes
Unsupported Android-only tools advertised: 0
```

Windows 全量 `pytest`、Qt 信号/槽、Real endpoint、麦克风和实际 UI/数据库效果仍未在本地容器签字，因此本报告保持“实现候选”。

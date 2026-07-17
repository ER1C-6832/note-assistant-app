# Gate 5.0 Implementation Report

状态：Implementation Complete，等待目标 Windows 工作树累计与 Real protocol probe 签字。  
基线：`176a5da63473a556de8a8e7851aa30bbdca9b818`。

## 1. 已实现

- 新增 `app/assistant/mcp/` 私有协议运行时；
- typed JSON-RPC request、notification、response 和 error；
- `initialize`、`notifications/initialized`、`tools/list`、`tools/call`；
- 冻结 31 个 descriptor、inputSchema、risk、mutates 和 confirmation metadata；
- 31 个已注册工具在 Gate 5.0 明确返回 `blocked/gate_not_ready`，不假成功；
- capacity 16 request queue、单 worker、capacity 64 completed dedupe cache；
- generation/session/typed request-id 去重和 canonical arguments fingerprint；
- same id/different payload 返回 `-32600`，零重复执行；
- private MCP payload 不进入 AssistantState 或普通日志；
- Fake transport 使用同一 registry/coordinator；
- Real transport 继承 Gate 4 playback transport，并复用既有 `_enqueue_and_wait` sender；
- generation close 时有界停止 worker，清空 queue、in-flight future、waiter 和 dedupe；
- 新增 Fake verifier、Real initialize/list probe 和累计 verifier。

## 2. 未实现

Gate 5.0 不接入 `NoteQueryService`、`NoteCommandService`、`TagCatalogService`、`UiCommandBus` 或 PendingConfirmationService。真实读取、写入、UI 和确认分别属于 Gate 5.1、5.2、5.3。

## 3. 验证命令

```powershell
python tools/verify_gate5_0_cumulative.py
python tools/verify_gate5_0_protocol.py
python tools/verify_gate5_0_real_protocol.py
```

可将两个 Real 验收纳入累计入口：

```powershell
python tools/verify_gate5_0_cumulative.py --include-gate4-real --include-gate5-real
```

退出码：通过 `0`；环境阻塞 `2`；协议或行为失败 `1`。

## 4. 本包构建环境证据

```text
compileall: passed
Black: passed
Ruff: passed
isolated MCP core tests: 18 passed
Fake adapter stub integration: passed
Real single-sender adapter stub integration: passed
```

构建环境没有完整仓库工作树、Windows 音频设备或真实 Xiaozhi endpoint，因此未声称完整 Gate 1～5 pytest、Gate 4 Real stop 或 Gate 5 Real initialize/list 已在此环境执行。

## 5. 预期终态

```text
request_queue_size == 0
mcp_worker_alive == false
inflight_request_count == 0
dedupe_waiter_count == 0
response_future_count == 0
no second sender
no second Python process
payload_persisted == false
```

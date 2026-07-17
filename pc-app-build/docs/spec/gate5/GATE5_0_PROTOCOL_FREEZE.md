# Gate 5.0 Protocol Freeze

状态：实现冻结候选  
实施基线：`176a5da63473a556de8a8e7851aa30bbdca9b818`

## 1. 范围

Gate 5.0 只实现 MCP 协议内核、31-tool descriptor registry、私有有界队列、单 worker、request-id 去重、Fake/Real transport 接入和资源关闭。

Gate 5.0 不读取或修改便签、标签或 UI。31 个工具均可发现；`tools/call` 对已注册工具返回业务结果 `blocked/gate_not_ready`。真实 handler 从 Gate 5.1 开始按阶段接入。

## 2. Wire 冻结

- JSON-RPC 版本：`2.0`。
- MCP protocolVersion：`2024-11-05`。
- serverInfo：`note-assistant-pc / 5.0`。
- 支持方法：`initialize`、`notifications/initialized`、`tools/list`、`tools/call`。
- 唯一允许的无 id notification 是 `notifications/initialized`；其他 notification 零执行、零响应。
- request id 只接受 JSON integer 或 string；boolean、float、null 拒绝。
- integer `1` 与 string `"1"` 是不同去重 key。
- `tools/list.nextCursor` 固定为 `null`；非空 cursor 返回 `-32602`。
- 未知 method 与未注册 tool 返回 `-32601`。
- 已注册但尚未接入 handler 的 tool 返回合法 `tools/call` result：`blocked/gate_not_ready`。
- MCP payload string 的 JSON 解析失败返回 `-32700`；外层 WebSocket JSON 损坏继续走既有 protocol-invalid 路径。

## 3. 容量和所有权

```text
request queue capacity     16
completed dedupe entries   64
duplicate waiters per key  16
maximum outer MCP message  64 KiB
maximum tool result        32 KiB
MCP workers                1 per active generation
```

- receiver 只做一次 MCP outer parsing、同步校验和 `submit_nowait`，不等待 handler。
- worker 串行执行 request。
- Real response 只调用现有 `_enqueue_and_wait`，不新增 websocket `.send()` 调用者或 sender task。
- generation/session/request-id 共同定义去重所有权。
- 同 key 同 fingerprint 共享首次执行结果；不同 fingerprint 返回 `-32600`，零二次执行。
- reconnect 不重放 completed 或 queued mutation。

## 4. 隐私

私有 MCP event 的 payload、session id、request params 和 tool arguments 均不出现在 dataclass `repr`。AssistantState 只接收 sanitized `ProtocolMessageObserved`，字段限于 request-id hash、method、tool、risk、status 和 duration。

不记录 raw MCP JSON、title、content、query、token、完整 session/device/client identity 或音频 payload。

## 5. 退出条件

- Fake initialize/list/call 通过；
- `tools/list` 精确 31 names，且与 8 个 unsupported Android tools 无交集；
- in-flight duplicate 只执行一次；
- queue overflow、unknown、invalid、oversized fail-closed；
- Real response 只走既有 sender；
- close/reconnect 后 request queue、worker、in-flight future 和 duplicate waiter 全零；
- Real endpoint 主动完成 initialize + tools/list probe。

# Gate 2 协议兼容矩阵

参考基线：`note-assistant-android@974a477c`

## 1. 兼容原则

- 协议字段按 Android 和其审计来源实现，不凭记忆创造。
- PC 的平台字段允许有意差异，但必须记录并真实验证。
- Fake 和 Real 必须共用 MessageBuilder、MessageRouter 和 Controller 状态机。
- `session_id` 非空前不能进入 Connected。

## 2. 矩阵

| 项目 | Android 行为 | PC Gate 2 目标 | 验证 |
|---|---|---|---|
| WebSocket Authorization | `Bearer <token>` | 完全一致 | Fake + Real |
| Protocol-Version | `1` | 完全一致 | Unit + Real |
| Device-Id | identity.deviceId | 完全一致语义 | Unit + Real |
| Client-Id | identity.clientId | 完全一致语义 | Unit + Real |
| Client hello | type hello/version 1/MCP/audio params | 完全一致 | Builder test + Real |
| hello audio params | opus/16000/1/20ms | Gate 2 即发送完整字段 | Unit + Real |
| Server hello | 必须返回 session_id | 非空才 Connected | Fake + Real |
| Text input | listen/detect + text | 完全一致 | Unit + Real |
| Listen start | listen/start + manual/realtime | Gate 3 激活，Gate 2 Builder 预留 | Unit |
| Listen stop | listen/stop | Gate 3 激活 | Unit |
| Abort | abort + reason | Gate 3/4 激活，Gate 2 预留 | Unit |
| MCP envelope | type=mcp,payload object | Gate 2 parse + blocked | Unit + Fake |
| Binary downlink | audio bytes | Gate 2 typed route，不播放 | Unit |
| Unknown JSON | Raw/Unknown event | 不断线 | Unit |
| Invalid JSON | ProtocolError | 不断线，记录错误 | Unit |
| Normal close 1000 | 不自动重连 | 一致 | Unit + Fake |
| Abnormal close | 有界重连 | 一致并增加退避 | Unit + Fake |

## 3. Hello 结构

```json
{
  "type": "hello",
  "version": 1,
  "features": {"mcp": true},
  "transport": "websocket",
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 20
  }
}
```

PC 使用 dict + `json.dumps(..., separators=(",", ":"))`，不手写字符串转义。

## 4. 文本输入

```json
{
  "session_id": "...",
  "type": "listen",
  "state": "detect",
  "text": "用户输入"
}
```

不设计 `chat.text`、REST 文本接口或本地 HTTP 控制路径。

## 5. Router 事件

```text
ServerHello
AssistantText
TtsState
ListenState
McpRequest
BinaryAudio
UnknownJson
ProtocolError
```

`stt`、`llm`、`text` 消息需要保留原始 type，避免后续 transcript 拼接和 TTS 文本处理失去来源。

## 6. Activation 差异

Android OTA payload 使用 Android board/app 标识。PC 不应原样伪装成 Android：

```text
Android: board.type=android, app=note-assistant-android
PC target: board.type/windows 或服务端认可值，app=note-assistant-pc
```

这是有意偏差，Gate 2.0 必须通过真实服务端或服务端文档确认；未经确认不能声称 Real Activation 完成。

需要对齐：

- OTA headers；
- Device-Id/Client-Id；
- activation version；
- websocket url/token 解析；
- optional activation code/challenge；
- HMAC-SHA256 challenge；
- token 日志脱敏。

## 7. WebSocket Adapter 依赖选择

Gate 2.0 实现前进行小型 spike，候选：

- `websockets`；
- `aiohttp.ClientWebSocketResponse`。

选择标准：

- Python 3.10；
- Windows 稳定；
- async cancellation 明确；
- header 支持；
- binary/text route；
- close code/reason；
- 无第二事件循环；
- 测试可替换。

最终依赖必须锁定版本范围并进入 `pyproject.toml`，不能运行时临时安装。

## 8. MCP Gate 2 边界

支持解析：

```text
initialize
notifications/initialized
tools/list
tools/call
```

Gate 2 对 `notes.*`、`tags.*`：

```text
status = blocked/not_ready
database unchanged
websocket remains connected
```

Gate 5 才接 `NoteCommandService`。

## 9. Gate 2.3 实施状态

- Adapter：`websockets>=16.0,<17` asyncio API；
- TLS：默认系统证书验证；
- Headers：Authorization / Protocol-Version / Device-Id / Client-Id；
- Client hello：与 Android Builder 字段一致；
- Connected：仅非空 `session_id`；
- Sender：单有界队列、单 owner；
- Receiver：单 owner；
- Unknown/invalid JSON：typed event，连接保持；
- Binary：typed route，Gate 4 前不播放；
- Real 验收：`RUN_GATE2_3_REAL_WEBSOCKET_HELLO.ps1` 返回 0 才算 hello/session 通过。

## 10. Gate 2.4 文本回合实施状态

- Outgoing：共享 Builder 生成 `listen/detect`；
- Concurrency：同一 session 单 active turn，快速连续发送 fail-closed；
- Local correlation：本地 `turn_token` 不写入 wire JSON；
- STT：独立记录，不覆盖文本输入；
- LLM：纯表情/情绪标记不进入产品 transcript；
- Text/TTS text：可读正文合并进入助手 transcript；
- Gate 4 前：TTS 与二进制音频只记录，不播放；
- Late events：无 active token、token/session 不匹配时归档；
- Real 验收：`RUN_GATE2_4_REAL_TEXT.ps1` 返回 0 且 `real_text_verified=true`。

服务端当前不回显 PC 本地 turn token，本地关联依赖“单 active turn + session + 发送屏障 + settle 窗口”，不等同于服务端强 turn-id 关联。

## 11. Gate 2.5 Recovery / Error / Shutdown 实施状态

- Normal close `1000`、disabled、manual disconnect：不自动重连；
- Abnormal close / retryable failure：最多三次；
- Base backoff：`0.5s / 1.5s / 3.0s`；
- Jitter：按 connection generation、attempt 与触发事件的 monotonic timestamp 计算确定性有界抖动，Reducer 对相同输入保持可复现；
- Timer：Controller 只持有一个 `reconnect_timer_task`，timer 只发 `ReconnectTimerFired`，不直接写 State；
- Generation：timer、socket 和 hello 事件均携带 generation，陈旧事件无副作用；
- Manual reconnect：先取消自动 timer，再关闭旧 generation，再打开新 generation；
- Non-retryable failures：缺凭据、配置错误、runtime mode mismatch 不进入无意义重试；
- Shutdown：停止接收 command、取消 timer/effects、有界 close、停止 event pump；
- Real 验收：`RUN_GATE2_5_REAL_RECOVERY.ps1` 在真实 socket 上强制一次 `1012` 异常关闭，并要求新 generation 完成真实 hello/session。

Gate 2.5 的 Real Gate 不重新执行 OTA/activation，不修改设备身份，也不通过 Fake transport 代替第二次真实握手。

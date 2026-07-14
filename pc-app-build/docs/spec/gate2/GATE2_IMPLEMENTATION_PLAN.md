# Gate 2 Runtime 实施计划

## 总目标

在不依赖真实音频的前提下，建立完整 Assistant Runtime 骨架、真实身份/激活/WebSocket/文本链路，以及未来 Gate 3～6.5 可直接扩展的完整状态和并发模型。

## Gate 2.0：契约和审计

输出：

```text
GATE2_00_DIRECTION_DECISION.md
GATE2_FULL_STATE_CONTRACT.md
GATE2_CONTROLLER_CONCURRENCY_SPEC.md
GATE2_PROTOCOL_COMPATIBILITY.md
CROSS_DEVICE_SYNC_COMPATIBILITY.md
```

验收：

- Android 全部状态字段有 PC 映射；
- Android Controller 全部能力有目标 Gate；
- 无功能被标记为“PC 不做”；
- 协议字段和有意偏差明确；
- 同步与设备本地状态边界明确。

## Gate 2.1：完整 Runtime Core

新增：

```text
assistant/state.py
assistant/events.py
assistant/effects.py
assistant/transitions.py
assistant/state_machine.py
assistant/controller.py
assistant/testing/scripted_transport.py
assistant/testing/fake_clock.py
```

完成：

- 完整嵌套 State；
- 不变量校验；
- 单 event pump；
- reducer；
- effect runner；
- Fake Transport；
- target capability registry；
- Gate 2 能力 active，后续能力 not_ready/inactive。

验收：

- Core 不依赖 PySide6；
- StateMachine 纯单测；
- Controller 只有一个状态写入路径；
- disable/shutdown 可取消全部 Fake tasks；
- 后续完整状态字段存在且默认正确。

## Gate 2.2：Identity / Config / Activation

新增：

```text
assistant/identity/models.py
assistant/identity/store.py
assistant/identity/manager.py
assistant/activation/models.py
assistant/activation/parser.py
assistant/activation/client.py
assistant/activation/fake_client.py
assistant/runtime_config.py
```

完成：

- 稳定 device/client identity；
- serial/hmac secret 本地保存；
- runtime config schema version；
- fake activation；
- real OTA parser；
- optional activation required；
- redacted diagnostics。

验收：

- 重启身份不变；
- reset 后 generation 增加；
- token/secret 不出现在普通日志和 QML；
- Fake 不污染 Real 配置；
- parser 使用固定 fixture 测试。

## Gate 2.3：WebSocket hello/session

新增：

```text
assistant/network/transport.py
assistant/network/websocket_transport.py
assistant/network/fake_transport.py
assistant/protocol/message_builder.py
assistant/protocol/message_router.py
assistant/protocol/events.py
```

完成：

- headers；
- socket open；
- hello；
- hello timeout；
- session_id；
- typed receive；
- single sender；
- binary typed route；
- close code/reason。

验收：

- socket open 不等于 Connected；
- 空 session_id 失败；
- disable during hello 忽略旧结果；
- unknown/invalid JSON 不崩溃；
- sender 只有一个 owner。

## Gate 2.4：文本回合

完成：

```text
send_text
-> listen/detect
-> thinking
-> assistant text events
-> connected
```

明确 transcript 规则：

- 用户文本进入 last_user_text；
- `stt/llm/text/tts.text` 的产品显示规则分开；
- 不把协议 debug JSON 当产品 transcript；
- 新回合有 turn token，旧回合文本可被拒绝或归档。

验收：

- 空文本不发；
- 未连接策略固定；
- 快速连续发送策略固定；
- Fake/Real 共用 Builder/Router；
- 真实文本收到后返回 Connected 或按 TTS 状态进入 Speaking（Gate 4 前只记录）。

## Gate 2.5：Recovery / Error / Shutdown

新增：

```text
assistant/network/reconnect_policy.py
assistant/errors.py
```

策略：

```text
normal close 1000: no reconnect
disabled: no reconnect
abnormal close/failure: max 3 attempts
backoff: 0.5s, 1.5s, 3.0s + bounded jitter
```

验收：

- 自动与手工重连不并行；
- disable 取消 timer；
- connection generation 生效；
- shutdown 有界；
- app 退出无 traceback、无残留 task/进程。

## Gate 2.6：AssistantViewModel / QML

新增：

```text
ui/assistant_view_model.py
qml/components/AssistantPanel.qml
```

普通用户功能：

- enabled；
- connect/disconnect；
- 状态；
- 文本输入；
- 最近回复；
- 错误和重试。

Developer 折叠区：

- Fake/Real；
- identity；
- activation；
- redacted protocol trace；
- 模拟断线/失败；
- capability 状态。

不提前显示可点击但未实现的 PTT/KWS 产品按钮。

## Gate 2.7：总验收

### Fake Gate

- 完整 State 默认值；
- Fake activation；
- Fake hello/session；
- Fake text；
- invalid/unknown JSON；
- MCP blocked；
- abnormal close/reconnect；
- disable/shutdown；
- Notes DB 不变。

### Real Gate

- 真实 identity/OTA；
- 真实 headers；
- 真实 hello/session；
- 真实文本回复；
- 真实 close/error；
- protocol compatibility report 更新。

凭据或服务不可用时只能标记：

```text
Fake Gate complete
Real Gate blocked
```

不得声称 Gate 2 全完成。

## 后续 Gate 激活表

| 能力 | 状态/接口何时冻结 | 副作用何时实现 |
|---|---|---|
| PTT | Gate 2.1 | Gate 3 |
| TTS playback | Gate 2.1 | Gate 4 |
| MCP notes | Gate 2.1/2.3 parse | Gate 5 |
| Streaming conversation | Gate 2.1 | Gate 6 |
| VAD | Gate 2.1 | Gate 6 |
| Barge-in | Gate 2.1 | Gate 6 |
| Microphone lease | Gate 2.1 contract | Gate 3/6.5 |
| KWS | Gate 2.1 contract | Gate 6.5 |
| Full metrics | Gate 2.1 base | Gate 3～7 |

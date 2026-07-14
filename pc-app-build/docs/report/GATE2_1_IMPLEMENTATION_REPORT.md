# Gate 2.1 Runtime Core 实施报告

## 完成范围

本 Gate 按 `docs/spec/gate2` 冻结契约完成：

- 完整、不可变、版本化的嵌套 `AssistantState`；
- Android 现有 Runtime 状态语义和未来能力注册表；
- 完整公开 Controller command/event 名称；
- 单个有界 `asyncio.Queue` 和单 event pump；
- 纯 `ConversationStateMachine.reduce(state, event)`；
- `Transition = next_state + effects`；
- Effect Runner；
- Scripted Fake Transport；
- Fake hello/session、Fake 文本回合；
- connection/capture/playback/streaming/wakeword/microphone lease generation；
- 旧 generation 事件失效；
- disable、disconnect、reconnect、shutdown 的任务取消骨架；
- MCP 修改工具模拟请求 fail-closed；
- 未来 PTT、TTS、MCP、连续对话、VAD、barge-in、KWS 能力明确为 `not_ready`；
- `app.assistant` 导入不再通过 `app.__init__` 顶层加载 PySide6 Bootstrap。

## 本 Gate 明确不实现

以下不是删除，而是按计划留待后续 Gate 激活真实副作用：

- Gate 2.2：Device Identity、Config、OTA/Activation；
- Gate 2.3：真实 WebSocket、协议 Builder/Router、单 sender；
- Gate 2.4：真实文本回合；
- Gate 2.5：自动重连退避；
- Gate 2.6：AssistantViewModel/QML；
- Gate 3+：真实音频、TTS、MCP、连续对话、KWS。

## 状态所有权

唯一写入路径：

```text
AssistantController._event_pump
-> ConversationStateMachine.reduce
-> self._state = transition.state
-> subscriber notification
```

Transport、Effect、Timer 和未来 Audio/MCP Coordinator 只能投递 Event，不能直接替换 State。

## 验证

交付环境完成：

```text
Black: passed
Ruff: passed
compileall: passed
Gate 2.1 tests: 23 passed
ZIP extraction recheck: passed
```

由于交付环境无法通过 DNS 获取完整 GitHub checkout，本地只执行了 Gate 2.1 完整测试；`VERIFY_GATE2_1.ps1` 会在 Windows 完整仓库中执行 Gate 1.1～1.7 与 Gate 2.1 全量回归。

## 已知限制

- Real Runtime 默认模式存在，但连接会明确返回 `capability_not_ready`，不会误用 Fake Transport；
- Scripted Fake Transport 不实现真实 JSON 协议，真实 Builder/Router 属于 Gate 2.3；
- 自动重连尚未激活，异常关闭进入结构化可恢复错误；
- 本 Gate 不修改 QML 和 Bootstrap Composition。

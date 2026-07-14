# Gate 2 Controller 与并发所有权规范

## 1. 目标 Controller API

PC 最终 `AssistantController` 的能力面与 Android 对齐，并增加显式 abort/shutdown：

```text
enable_assistant
disable_assistant
use_fake_runtime          # developer only
use_real_runtime          # developer only
connect
reconnect
disconnect
send_text
set_voice_interaction_mode
set_streaming_barge_in_enabled
start_push_to_talk
stop_push_to_talk
start_streaming_conversation
stop_streaming_conversation
abort_current_turn
handle_system_audio_interruption
handle_system_audio_recovered
ensure_device_identity
reset_device_identity
run_fake_activation       # test only
run_real_activation
simulate_incoming_tool_call
simulate_incoming_tools_list
simulate_connection_closed
simulate_connection_failure
simulate_audio_failure
shutdown
```

Gate 2 QML 只暴露已实现方法；未进入对应 Gate 的方法不做虚假成功。

## 2. 内部组件

### AssistantControllerFacade

- 接收公开 command；
- command 立即转换成 Event；
- 管理 event pump 的启动和关闭；
- 发布不可变 State Snapshot；
- 自身不执行网络、音频、数据库 I/O。

### AssistantEventPump

- 一个 `asyncio.Queue[AssistantEvent]`；
- 一个长期 consumer task；
- 唯一允许调用 Reducer 并替换当前 State 的位置；
- 队列容量建议 256；
- 高价值控制事件不得静默丢弃。

### ConversationReducer

纯函数：

```text
reduce(current_state, event) -> Transition
Transition = next_state + effects
```

不得：

- await；
- 打开 socket；
- 访问文件；
- 创建 Task；
- 调 Qt；
- 调 SQLAlchemy。

### EffectRunner

按 Effect 类型调用 adapter，并把结果重新投递成 Event。

### Coordinators

- SessionCoordinator；
- RecoveryCoordinator；
- AudioCoordinator；
- McpCoordinator；
- WakeWordCoordinator。

Coordinator 不持有独立 AssistantState，只保留资源句柄、task、queue、generation 和 lease。

## 3. 事件来源

```text
UI Command
Transport Event
Protocol Event
Activation Event
Audio Event
MCP Event
Reconnect Timer
System Audio Event
Application Lifecycle Event
```

全部进入同一个 event pump。

## 4. 任务所有权

### Controller Runtime Group

```text
event_pump_task
effect_tasks set
```

### WebSocket Transport

```text
receiver_task
sender_task
optional heartbeat_task
```

### Recovery

```text
single reconnect_timer_task
```

### Audio（Gate 3+）

```text
capture task/adapter handle
encoder worker
upload task
playback task
```

### KWS（Gate 6.5）

```text
kws capture handle
kws inference worker
```

每个长期任务都必须：

- 有唯一 owner；
- 可取消；
- 有 generation；
- 注册到 ApplicationLifecycle；
- 有界关闭。

## 5. 单写者规则

唯一状态写入路径：

```text
AssistantEventPump
-> reducer
-> state snapshot replacement
-> subscribers notified
```

禁止：

- WebSocket callback 修改 State；
- Audio callback 修改 State；
- QML 修改 State；
- AssistantViewModel 维护第二套 phase；
- MCP executor 修改 State；
- reconnect timer 修改 State。

## 6. Generation 设计

至少包含：

```text
connection_generation
capture_generation
playback_generation
streaming_generation
wakeword_generation
```

事件携带 generation。Reducer 收到旧 generation 时返回原状态和空 effects。

## 7. WebSocket 单发送者

所有文本和二进制发送统一经过：

```text
bounded outbound queue
-> one sender_task
-> socket.send
```

优先级：

1. close/abort/stop；
2. hello 和控制消息；
3. MCP response；
4. 用户文本；
5. 音频 packet。

实现可采用两个有界队列加公平调度，或带优先级的 envelope；不能由多个 task 并发调用 socket send。

## 8. 麦克风所有权

完整保留 Android 的 Lease 思路：

```text
MicrophoneOwnershipCoordinator
owner = none | wakeword_kws | assistant_capture
lease = owner + generation
```

- PTT/流式对话启动前必须拿到 AssistantCapture lease；
- KWS 启动前必须拿到 WakeWordKws lease；
- lease generation 不匹配时 release 无效；
- TTS 播放期间默认抑制 KWS；
- system audio interruption 可 force release，但必须产生事件和审计原因。

## 9. Shutdown 顺序

```text
1. dispatch ShutdownRequested
2. enabled=false，取消重连
3. 停止接收新 command
4. 停止 KWS/连续对话/PTT
5. 清空或终止音频 generation
6. 关闭 WebSocket sender/receiver
7. 关闭 activation HTTP work
8. 等待 effect tasks 有界结束
9. 停止 event pump
10. AssistantViewModel close
11. DatabaseExecutor close
12. SQLAlchemy engine dispose
```

Gate 2 实现前六项中的非音频部分，顺序不得与后续 Gate 冲突。

## 10. Backpressure

- Event queue 满：产生 RuntimeOverloaded 错误，不静默丢控制事件。
- WebSocket control queue 满：本轮失败并关闭连接。
- PCM queue 满：Gate 3 按总计划丢最旧帧并记录指标。
- Opus queue 满：终止当前音频轮次并显示错误。
- Playback queue 满：按 generation 终止旧播放，不无限增长。

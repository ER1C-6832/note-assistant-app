# Gate 2 完整 Assistant State 契约

## 1. 原则

PC 从 Gate 2.1 开始建立完整目标状态结构。后续 Gate 只激活字段和转换，不重建第二套 State。

推荐使用不可变 dataclass 和嵌套子状态：

```text
AssistantState
├─ schema_version
├─ phase
├─ enabled
├─ runtime_mode
├─ connection
├─ activation
├─ identity
├─ audio
├─ conversation
├─ protocol
├─ recovery
├─ mcp
├─ diagnostics
├─ status_text
├─ error
└─ last_event_at_ns
```

## 2. 顶层枚举

### AssistantPhase

完整保留 Android 语义：

```text
disabled
idle
activating
connecting
connected
listening
uploading_audio
thinking
speaking
reconnecting
error
```

### AssistantRuntimeMode

```text
fake
real
```

Fake 仅用于开发和自动化验收；普通产品 UI 默认不向用户暴露模式切换。

### AssistantConnectionStatus

```text
disconnected
connecting
connected
closing
```

### AssistantActivationStatus

```text
unknown
required
activating
activated
failed
```

### AssistantAudioStatus

```text
idle
recording
playing
error
```

### VoiceInteractionMode

```text
hold_to_talk
streaming_conversation
```

### AssistantEntrySource

```text
text
push_to_talk
streaming_button
wakeword
```

### StreamingConversationState

```text
inactive
starting
listening_for_speech
user_speaking
submitting_turn
thinking
speaking
waiting_for_next_turn
stopping
recovering
error
```

### VoiceActivityState

```text
disabled
warmup
waiting_for_speech
speech_detected
speech_active
end_of_speech
no_speech_timeout
```

### MicrophoneOwner

```text
none
wakeword_kws
assistant_capture
```

## 3. 完整子状态

### ConnectionState

```text
status
session_id
websocket_url_public
connection_generation
opened_at_ns
hello_sent_at_ns
hello_received_at_ns
close_code
close_reason
```

约束：

- `status=connected` 必须同时满足 `session_id` 非空；
- generation 不匹配的旧回调不得改变当前状态；
- URL 可显示，token 不进入公开 State。

### ActivationState

```text
status
activation_code
message
authorization_url
last_attempt_at_ns
```

secret、challenge、hmac key 不放入公开 State。

### IdentityPublicState

```text
device_id_masked
client_id_masked
identity_ready
identity_generation
```

完整身份由 DeviceIdentityStore 保管，State 只暴露脱敏视图。

### AudioState

```text
status
capture_generation
playback_generation
captured_frames
encoded_frames
uploaded_frames
decoded_frames
played_frames
last_audio_summary
push_to_talk_stop_latency_ms
microphone_owner
```

Gate 2 默认全部为 idle/0，但字段从第一版即存在。

### ConversationState

```text
preferred_voice_mode
active_entry_source
last_user_text
last_assistant_text
streaming_state
streaming_session_active
streaming_session_id
streaming_turn_index
streaming_idle_timeout_ms
streaming_barge_in_enabled
barge_in_monitor_active
barge_in_trigger_count
vad_state
vad_status_text
```

### ProtocolState

```text
last_client_json_redacted
last_server_json_redacted
last_protocol_event
last_unknown_message_type
last_protocol_error
```

正式日志必须脱敏；完整 token、HMAC、Authorization Header 不得出现。

### RecoveryState

```text
reconnect_attempt
last_reconnect_decision
next_reconnect_at_ns
runtime_error_count
manual_disconnect_requested
```

### McpRuntimeState

```text
last_tool_name
last_tool_status
last_request_id
last_command_log_id
last_confirmation_id
real_tool_call_verified
```

Gate 2 中所有修改便签的 tool call 必须 `blocked/not_ready`，但 MCP 状态字段保留。

### RuntimeDiagnostics

```text
gate_real_handshake_verified
gate_real_text_verified
gate_real_audio_upload_verified
gate_real_audio_playback_verified
last_event_name
last_event_at_ns
metrics_sample_count
```

这些是诊断/验收状态，不是产品业务状态，也不跨设备同步。

### AssistantError

```text
code
message
category
recoverable
source_event
occurred_at_ns
details_redacted
```

不只保存字符串。错误码必须稳定，供 QML、日志和自动化测试使用。

## 4. Android 字段到 PC 路径映射

| Android 字段 | PC 路径 | 处理 |
|---|---|---|
| phase | `state.phase` | 完整保留 |
| connection | `state.connection.status` | 完整保留 |
| activation | `state.activation.status` | 完整保留 |
| audio | `state.audio.status` | 完整保留 |
| statusText | `state.status_text` | 完整保留 |
| errorMessage | `state.error.message` | 结构化增强 |
| lastUserText | `state.conversation.last_user_text` | 完整保留 |
| lastAssistantText | `state.conversation.last_assistant_text` | 完整保留 |
| lastEventAt | `state.last_event_at_ns` | 改用 monotonic ns |
| sessionId | `state.connection.session_id` | 完整保留 |
| reconnectAttempt | `state.recovery.reconnect_attempt` | 完整保留 |
| assistantEnabled | `state.enabled` | 完整保留 |
| fakeRuntime/runtimeMode | `state.runtime_mode` | 合并为枚举 |
| deviceId/clientId | `state.identity.*_masked` | 完整值留在 Store |
| activationCode | `state.activation.activation_code` | 完整保留 |
| websocketUrl | `state.connection.websocket_url_public` | 保留公开 URL |
| lastClientJson/lastServerJson | `state.protocol.*_redacted` | 脱敏保留 |
| lastProtocolEvent | `state.protocol.last_protocol_event` | 完整保留 |
| audioCapturedFrames | `state.audio.captured_frames` | 完整保留 |
| audioEncodedFrames | `state.audio.encoded_frames` | 完整保留 |
| audioUploadedFrames | `state.audio.uploaded_frames` | 完整保留 |
| pushToTalkStopLatencyMs | `state.audio.push_to_talk_stop_latency_ms` | 完整保留 |
| lastAudioSummary | `state.audio.last_audio_summary` | 完整保留 |
| lastCloseCode/Reason | `state.connection.close_*` | 完整保留 |
| lastReconnectDecision | `state.recovery.last_reconnect_decision` | 完整保留 |
| runtimeErrorCount | `state.recovery.runtime_error_count` | 完整保留 |
| Gate verification flags | `state.diagnostics.*` | 完整保留 |
| MCP fields | `state.mcp.*` | 完整保留 |
| preferredVoiceMode | `state.conversation.preferred_voice_mode` | 完整保留 |
| activeEntrySource | `state.conversation.active_entry_source` | 完整保留 |
| microphoneOwner | `state.audio.microphone_owner` | 完整保留 |
| streaming* | `state.conversation.streaming_*` | 完整保留 |
| bargeIn* | `state.conversation.barge_in_*` | 完整保留 |
| vad* | `state.conversation.vad_*` | 完整保留 |

## 5. 状态不变量

- Disabled：无连接、无 session、无录音、无播放、无重连任务。
- Connected：连接状态为 connected 且 session_id 非空。
- Listening/UploadingAudio：必须持有 AssistantCapture 麦克风租约。
- Speaking：audio.status 为 playing。
- streaming_session_active=false 时，streaming_state 必须为 inactive/stopping/error 中之一。
- KWS 持有麦克风时，AssistantCapture 不可同时持有。
- `enabled=false` 时任何自动重连事件都必须被 reducer 拒绝。
- 旧 generation 的 socket/audio/playback 事件必须无副作用。
- MCP Gate 2 blocked 结果不能修改 Notes 数据。

## 6. 持久化规则

只持久化经过明确分类的配置：

- assistant enabled（是否跨设备同步另行决定）；
- runtime endpoint 配置；
- activation 状态；
- device identity 和 secrets（仅设备本地）；
- preferred voice mode；
- streaming idle timeout；
- barge-in preference；
- KWS preference（后续）。

不持久化瞬时 phase、session、当前重连次数、当前 VAD 状态和 frame counter。

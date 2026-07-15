# Gate 3 State / Event / Effect 契约

## 1. 原则

Gate 2 已建立完整 State 外形。Gate 3 只激活已有字段并增加缺失的 generation/token，不创建第二套 VoiceState 或 StreamingController。

所有转换仍是：

```text
Adapter / UI / Timer
-> immutable AssistantEvent
-> Controller queue
-> pure ConversationStateMachine.reduce
-> new AssistantState + Effects
```

## 2. State 激活

### AudioState

现有字段继续使用：

```text
status
capture_generation
captured_frames
encoded_frames
uploaded_frames
last_audio_summary
push_to_talk_stop_latency_ms
microphone_owner
```

建议补充：

```text
pcm_drop_oldest_count
uplink_overflow_count
active_capture_mode
input_device_public_name
```

不得放入原始 PCM、token 或平台对象。

### ConversationState

激活：

```text
preferred_voice_mode
active_entry_source
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

补充：

```text
streaming_generation
active_streaming_turn_token
last_completed_streaming_turn_token
```

### Capability

Gate 3 分阶段激活：

```text
MICROPHONE_OWNERSHIP
PUSH_TO_TALK
VAD
STREAMING_CONVERSATION
```

`TTS_PLAYBACK` 与 `BARGE_IN` 在 Gate 4 激活。

## 3. UI-only State

以下不进入 AssistantState：

```text
launcher_x_ratio
launcher_y_ratio
assistant_panel_expanded
developer_panel_expanded
aurora animation phase
```

它们属于 ViewModel/QML shell。

## 4. Commands / Events

### Preferences

```text
AssistantPreferencesLoadRequested
AssistantPreferencesLoaded
AssistantPreferencesPersistFailed
VoiceInteractionModeRequested
StreamingIdleTimeoutRequested
StreamingBargeInRequested
```

### Microphone

```text
MicrophoneAcquireRequested
MicrophoneLeaseAcquired
MicrophoneLeaseRejected
MicrophoneLeaseReleased
```

### Capture

```text
PushToTalkStartRequested
PushToTalkStopRequested
AudioCaptureStarted
AudioCaptureStopped
AudioCountersUpdated
AudioCaptureFailed
AudioUplinkOverflow
```

所有 capture 事件携带 `capture_generation`；与 socket 相关的事件同时携带 `connection_generation`。

### Streaming

```text
StreamingConversationStartRequested
StreamingConversationStopRequested
StreamingSessionStarted
StreamingSessionStopped
StreamingTurnStarted
VoiceActivityChanged
StreamingTurnSubmitRequested
StreamingTurnSubmitted
StreamingTurnDiscarded
StreamingResponseTimeout
StreamingNextTurnRequested
```

Streaming 事件携带：

```text
streaming_generation
turn_token（与具体 turn 相关时）
```

### Playback 衔接（Gate 4）

```text
PlaybackStarted
PlaybackEnded
BargeInTriggered
```

需要携带 playback generation、streaming generation、turn token。

## 5. Effects

```text
LoadAssistantPreferences
PersistAssistantPreferences
AcquireMicrophone
ReleaseMicrophone
StartAudioCapture
StopAudioCapture
CancelAudioCapture
SendListenStart
SendListenStop
SendAbort
StartAudioUplink
StopAudioUplink
ScheduleStreamingResponseTimeout
CancelStreamingResponseTimeout
ScheduleNextStreamingTurn
CancelNextStreamingTurn
```

Gate 4 增加：

```text
StartPlayback
StopPlayback
StartBargeInMonitor
StopBargeInMonitor
```

## 6. Reducer 规则

### VoiceInteractionModeRequested

- 非活动：更新 preferred mode，产生 Persist effect；
- streaming active 且切到 PTT：先进入 stopping，产生 StopStreaming composite effects，完成后更新 mode；
- PTT active：不得并行启动 streaming；可以拒绝并给出稳定错误，或按冻结流程先 abort PTT；
- capability 未激活时允许保存偏好，但不得把未实现会话标为 active。

### PushToTalkStartRequested

要求：

```text
enabled
real/fake mode permitted
connected or effect can establish connection
preferred mode == hold_to_talk
no active streaming session
no microphone lease
phase in connected/idle
```

成功只产生 Effects；实际 `Listening` 必须等待 `AudioCaptureStarted` 和协议 start 条件满足。

### StreamingConversationStartRequested

要求：

```text
enabled
preferred mode == streaming_conversation
streaming capability active
no PTT capture
no active streaming session
```

Reducer 生成新 streaming generation 和 starting State；设备成功后由事件进入 listening。

### VoiceActivityChanged

- generation/token 不匹配：只计 stale diagnostic，不改变产品状态；
- speech detected/active：更新 VAD/streaming state；
- end of speech：仅一次产生 submit effects；
- no speech timeout：产生 abort/stop effects。

### StreamingNextTurnRequested

只有以下全部满足时有效：

```text
streaming session active
same streaming generation
same latest completed turn
connected
no capture
no playback
mode still streaming
not shutting down
```

## 7. Error codes

建议稳定错误码：

```text
audio_device_open_failed
audio_capture_start_failed
audio_capture_stop_timeout
audio_encoder_failed
audio_pcm_overflow
audio_uplink_overflow
microphone_busy
voice_mode_conflict
streaming_start_failed
streaming_no_speech_timeout
streaming_response_timeout
streaming_reconnect_exhausted
preferences_load_failed
preferences_save_failed
```

错误必须脱敏并标记 recoverable/category/source_event。

## 8. Controller 所有权

Controller 新增长期任务引用：

```text
audio_uplink_task
streaming_response_timer_task
streaming_next_turn_task
```

最多各一个。Audio worker thread 不属于 asyncio Task，但必须由 AudioEngine 持有并在 shutdown 有界 join。

Controller 不允许出现另一份 `_voice_state`、`_streaming_state` 或 QML 镜像状态。

## 9. Shutdown

```text
ShutdownRequested
-> invalidate connection/capture/streaming/playback generations
-> cancel reconnect / streaming timers / uplink
-> stop capture/playback
-> release microphone
-> close transport
-> await tasks/workers
-> stop event pump
```

验收要求：无 pending runtime task、无打开 PyAudio stream、无第二 Python 进程。

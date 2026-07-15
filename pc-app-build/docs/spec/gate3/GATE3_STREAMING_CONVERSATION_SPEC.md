# Gate 3 连续对话 Spec

## 1. 范围决策

连续对话从旧 Gate 6 前移到 Gate 3/4 主线：

- Gate 3：真实连续上行、VAD、自动提交、停止/恢复边界；
- Gate 4：真实 TTS 播放后自动恢复下一轮、两轮闭环、简单插话。

它不再等待 MCP 完成。

## 2. 模式

```text
VoiceInteractionMode.HOLD_TO_TALK
VoiceInteractionMode.STREAMING_CONVERSATION
```

设置切换的是默认模式。切换本身不自动开启麦克风。

## 3. Session 与 Turn

连续对话有本地 session：

```text
streaming_session_id: UUID
streaming_generation: monotonic int
streaming_turn_index: 0..N
active_streaming_turn_token: monotonic int
```

- `streaming_session_id` 只用于本地诊断/上下文，不写 wire JSON；
- 服务端 WebSocket `session_id` 仍由 hello 决定；
- 一次断线恢复可能更换服务端 session，但本地 streaming session 是否延续由 Recovery 事件明确决定；
- 旧 turn 的 TTS/text/playback 事件不得结束新 turn。

## 4. 状态链路

Gate 3 上行阶段：

```text
inactive
-> starting
-> listening_for_speech
-> user_speaking
-> submitting_turn
-> thinking
```

Gate 4 完整阶段：

```text
thinking
-> speaking
-> waiting_for_next_turn
-> listening_for_speech
```

恢复：

```text
任何活动状态
-> recovering
-> listening_for_speech 或 error/inactive
```

停止：

```text
任何活动状态
-> stopping
-> inactive
```

## 5. 启动

```text
StreamingConversationStartRequested
-> validate enabled / real runtime / capability
-> ensure activation and connection through existing commands
-> allocate streaming_generation + UUID
-> acquire microphone
-> send listen/start(mode=manual)
-> start shared capture with streaming config
-> StreamingSessionStarted event
```

不允许 UI 直接按顺序调用 transport/audio；Controller Effects 负责协调。

## 6. VAD

第一版采用本地 VAD，产生不可变事件：

```text
warmup
waiting_for_speech
speech_detected
speech_active
end_of_speech
no_speech_timeout
```

VAD 只读取 PCM frame，不修改 State。

建议第一版可配置：

```text
warmup: 200~400 ms
min speech: 240 ms
end silence: 600~900 ms
no speech timeout: default 8000 ms
```

具体阈值需通过真实设备验收确定，不在 QML 硬编码。

## 7. 自动提交

在 `end_of_speech`：

```text
invalidate current capture generation
-> stop capture bounded
-> release microphone
-> if useful audio and min packet count met:
     send listen/stop
     StreamingTurnSubmitted
     phase=thinking
   else:
     send abort(streaming_empty_turn)
     schedule next turn or stop according to policy
```

同一 turn 只能 finalize 一次；VAD、stop callback 和用户停止并发时使用 turn token 去重。

## 8. 无语音超时

默认策略：

- 第一轮或下一轮等待超过 `streaming_idle_timeout_ms`；
- 发送 `abort(streaming_no_speech_timeout)`；
- 停止整个 streaming session；
- 返回 Connected/Idle；
- 不无限自动重开麦克风。

后续可以提供“持续待命”策略，但不进入第一版。

## 9. 回复与下一轮

### Gate 3

收到文本/TTS 状态可更新 transcript 和 thinking/speaking 语义，但不会在没有真实播放完成信号时声明完整连续闭环。

### Gate 4

下一轮只能由以下条件触发：

```text
TTS stop observed
AND playback buffer drained
AND PlaybackEnded event accepted for current turn/generation
```

不能仅凭 `tts/stop` 立即重新开麦。

## 10. 网络异常

活动 streaming session 遇到异常断开：

```text
invalidate capture generation
-> stop capture
-> release microphone
-> streaming_state=recovering
-> existing ReconnectPolicy handles socket
```

重连成功后：

- 只有 streaming generation 仍活动、用户未 stop、mode 仍是 streaming 时才恢复；
- 只启动一个 next-turn task；
- 不自动重发上一轮已提交的音频；
- 服务端 session 更新后旧事件全部丢弃；
- 达到 reconnect exhausted 时 streaming session 进入 error 并停止。

## 11. Mode change / Disable / Shutdown

以下命令全部使 streaming generation 失效：

- 切换到 PTT；
- assistant disable；
- manual disconnect；
- runtime mode change；
- identity reset；
- app shutdown。

停止流程必须取消：

```text
capture
VAD callbacks
response watchdog
next-turn timer
barge-in monitor
playback resume trigger
```

## 12. Barge-in

Gate 4.2 第一版：

- 默认关闭；
- 只在 streaming session + speaking/playback active 时允许；
- 使用同一 microphone ownership；
- 开启 monitor 后，在 speech detected 前不上传音频；
- 确认插话后停止 playback、发送 abort、send listen/start，再上传当前 capture；
- 必须用 generation/token 防止旧播放结束事件误启动下一轮。

无 AEC 时需要真实扬声器回采测试；误触发不可接受时维持默认关闭。

## 13. UI 语义

Aurora 中心标签建议：

```text
待命
连接
聆听
说话中
思考
回复
恢复
停止中
重试
```

标签来自 ViewModel 投影，不由 QML 根据多个布尔字段拼接。

## 14. Real Acceptance

Gate 3 Real：

1. 设置切换到连续模式；
2. 点击全局悬浮按钮开始；
3. 真实麦克风检测一句话；
4. VAD 自动 stop；
5. 真实 Opus 上行；
6. 服务端返回可读文本/TTS state；
7. 用户停止或 session 正常结束；
8. 无残留 capture/task。

Gate 4 Real 完整连续：

1. 第一轮用户语音；
2. 真实 TTS 播放；
3. PlaybackEnded 后自动重新 Listening；
4. 第二轮用户语音；
5. 第二轮真实 TTS 播放；
6. 停止后无录音/播放残留。

少于两轮不得声明连续对话完整通过。

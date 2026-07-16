# Gate 3 连续对话 Spec

状态：Gate 3.4 冻结  
解释基线：`9f204735e338ff7e87010ca58e628406673e13ae`

## 1. 范围

连续对话从旧 Gate 6 前移到 Gate 3/4：

- Gate 3：真实连续上行、local VAD、自动提交、transcript、停止/恢复边界；
- Gate 4：真实 TTS 播放、真实 PlaybackEnded、自动下一轮、两轮闭环、可选简单插话。

Gate 3 不实现 TTS decode/playback、自动第二轮或 barge-in。

## 2. 模式

```text
VoiceInteractionMode.HOLD_TO_TALK
VoiceInteractionMode.STREAMING_CONVERSATION
```

设置切换默认模式。切换本身不自动打开麦克风。

## 3. Session、generation 与 turn

```text
connection_generation
streaming_session_id: local UUID
streaming_generation: monotonic int
capture_generation: monotonic int
streaming_turn_index: 1..N
active_streaming_turn_token: monotonic int
```

- 本地 streaming UUID 不写 wire JSON；
- 服务端 session_id 来自 hello；
- 陈旧 connection/streaming/capture/session/turn 事件为 no-op；
- 同一 generation + turn 最多 finalize 一次；
- 断线恢复不得重发已提交音频。

## 4. Gate 3 状态链路

```text
inactive
-> starting
-> listening_for_speech
-> user_speaking
-> submitting_turn
-> thinking
-> waiting_for_next_turn
```

`WAITING_FOR_NEXT_TURN` 在 Gate 3 的含义：本轮已收到有效 assistant text/TTS transcript，session 仍由用户手动控制，但没有活动 capture、uplink、VAD、response timer 或 microphone lease。

恢复：

```text
active state
-> recovering
-> exactly one listening_for_speech
   or error/inactive
```

停止：

```text
active/waiting/error state
-> stopping
-> inactive
```

## 5. 启动

```text
StreamingConversationStartRequested
-> validate enabled/connected/capability/mode
-> allocate streaming generation + UUID + turn token
-> acquire one microphone lease
-> send one listen/start(mode=manual)
-> start shared capture with VAD
-> StreamingSessionStarted
```

重复 start 不能创建第二个 capture、VAD task、uplink task、lease 或 listen/start。

## 6. VAD

状态：warmup、waiting_for_speech、speech_detected、speech_active、end_of_speech、no_speech_timeout。

当前默认参数：

```text
warmup: 300 ms
minimum speech: 240 ms
end silence: 700 ms
no speech timeout: 8000 ms
```

VAD 只读取 PCM 并产生不可变事件，不直接修改 AssistantState。

## 7. 自动提交

`end_of_speech`：

```text
stop capture bounded
-> drain encoded packets
-> release microphone
-> useful audio: one listen/stop + StreamingTurnSubmitted
-> no useful audio: one abort + stop session
```

end_of_speech、用户 stop、response timeout 和 disconnect 的排列由单事件泵确定。stop/cancel/finalize 可重复调用，但协议发送、turn completion 和 session completion不得重复。

## 8. 回复冻结语义

### 8.1 有效回复

当前 turn 收到可读 assistant text 或带可读文本的 TTS transcript：

```text
streaming_state = WAITING_FOR_NEXT_TURN
streaming_session_active = true
audio.status = idle
streaming_response_deadline = none
CancelStreamingResponseTimeout
```

同时必须满足：

- capture 已停止；
- audio uplink task 已停止；
- VAD task 已停止；
- audio worker 已结束；
- microphone lease 已释放；
- 不产生 `StartStreamingConversation`；
- 不自动递增 turn index；
- 重复/迟到回复不重复完成 turn。

### 8.2 TTS state

Gate 3 只记录 TTS transcript/state。它不表示实际播放已经开始或结束。

### 8.3 Gate 4 唯一续轮入口

Gate 4 引入实际 playback 后：

```text
current PlaybackEnded
AND playback buffer drained
AND current streaming generation/session still active
-> exactly one next-turn StartStreamingConversation
```

不能只凭 assistant text、`tts/stop` 或 TTS transcript 开麦。

## 9. no-speech / short speech / overflow

- no speech timeout：一个 abort，结束 session，不无限重开；
- 过短语音：按 no-useful-audio 处理，不发送 listen/stop；
- encoded/uplink overflow：当前 turn 进入可见 audio error，取消 capture/uplink/VAD，释放 lease；
- 所有失败均不得留下 assistant audio task 或未处理 asyncio exception。

## 10. 网络异常

活动 session 异常断开：

```text
invalidate connection/capture generation
-> cancel capture/uplink/VAD/response timer
-> release microphone
-> streaming_state=recovering
-> existing ReconnectPolicy schedules at most one timer
```

恢复条件：用户未 stop、mode 仍为 streaming、streaming generation 仍有效。成功后 timer 消失且最多启动一次 capture。

## 11. Mode change、disable、shutdown

切到 PTT、disable、manual disconnect、runtime mode change、identity reset、shutdown 均使旧 callback 无效。

正常 session stop 但连接保留时，transport sender/receiver 可存在。disable/shutdown 完成后，transport、reconnect timer、streaming timer、capture、worker、uplink、VAD、lease 和 `assistant-*` task 必须全部归零。

## 12. Real acceptance

Gate 3.3 Real 只验证一轮：

1. streaming 模式手动开始；
2. 真实麦克风与 WebSocket；
3. local VAD 自动提交；
4. 真实 Opus 上行；
5. readable STT；
6. readable assistant/TTS transcript；
7. WAITING_FOR_NEXT_TURN 不自动开麦；
8. 用户手动 stop；
9. 音频资源和 pending runtime task 清理。

少于两轮并不阻塞 Gate 3，因为真实两轮属于 Gate 4；但不得声称“完整连续对话闭环已通过”。

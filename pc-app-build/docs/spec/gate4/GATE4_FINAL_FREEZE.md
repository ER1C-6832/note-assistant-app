# Gate 4 Final Freeze

状态：Gate 4 实现完成；当前工作树通过 4.4 verifier 后可标记 Accepted  
收口基线：`9f37041cc5a955d0f943e552a465a8e9b02046a0`

## 1. 完成范围

Gate 4 已实现：

- 真实 ServerHello downlink format 校验；
- 原始 Opus binary 私有有界 ingress；
- PyAV Opus decode 和显式 resample/remix；
- PyAudio callback output；
- actual `PlaybackStarted` 与 physical `PlaybackEnded`；
- buffering/speaking/error Runtime 投影；
- actual PlaybackEnded 唯一自动续轮；
- exactly-once turn/capture allocation；
- 真实两轮连续对话；
- 用户 stop、mode switch、disconnect、disable、shutdown 优先级；
- bounded queues、watchdog、失败与取消回收；
- 无 payload 持久化和无 Runtime binary payload。

## 2. 唯一 physical end 定义

只有同时满足以下条件才产生 natural `ActualPlaybackEnded`：

```text
input terminal
AND encoded ingress empty
AND decoder flush complete
AND PCM buffer empty
AND final real sample consumed
AND output stream inactive
AND current generation/token matches
AND not failed/cancelled
```

`tts/stop`、transcript、最后一个 packet、decoder queue empty、动画结束和 timer 都不是 physical end。

## 3. 自动续轮

自动下一轮唯一来源是当前自然物理 `ActualPlaybackEnded`。Reducer 一次性分配：

```text
turn_token + 1
capture_generation + 1
streaming_turn_index + 1
-> STARTING
-> exactly one StartStreamingConversation
```

Controller 使用有界 `(streaming_generation, capture_generation, turn_token)` ledger 防止 effect 重复执行。

## 4. 取消和 precedence

- stop during buffering/playing：先取消并关闭 playback，再停止 streaming session；
- user stop / mode switch / disconnect / disable / shutdown 在先：迟到 PlaybackEnded no-op；
- PlaybackEnded 在先、stop 在后：合法 next capture 最多启动一次，后续 stop 立即取消；
- failure/cancel/non-natural end：不续轮；cancelled state 后迟到 physical-end 也必须 no-op；
- stale connection/playback/streaming generation：no-op；
- next capture start failure：进入现有 `AudioCaptureFailed` 和 session 回收链路。

取消只产生 cancelled 语义，不伪造 natural PlaybackEnded。

## 5. 资源终态

关闭完成后必须满足：

```text
playback output inactive
playback worker stopped
encoded ingress empty/closed
PCM buffered bytes = 0
capture inactive
microphone lease released
uplink task stopped
VAD task stopped
response timer stopped
transport generation closed when requested
assistant-* pending tasks = []
```

## 6. 已归档 Real 证据

- Gate 4.0：`real_gate_complete`，24 kHz mono 20 ms，130 packets，PyAV decode 成功；
- Gate 4.2：`real_gate_complete`，628 packets，602,880 decoded/played frames，人工听感通过；
- Gate 4.3：`real_gate_complete`，两轮播放、两次 auto-next、无 capture/playback overlap、无残留任务；
- Gate 4.4：由 `verify_gate4_4_real_stop_during_playback.py` 在当前目标工作树补齐 stop-during-playback 证据。

## 7. 非目标

Gate 4 不实现全双工声学插话、AEC、KWS、MCP 或完整设备热插拔恢复。播放期间默认不开麦；未来任何 interruption 功能必须先完成 playback cancel/close，再申请麦克风。

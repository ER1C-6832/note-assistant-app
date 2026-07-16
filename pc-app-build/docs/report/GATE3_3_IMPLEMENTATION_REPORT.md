# Gate 3.3 Streaming Conversation Uplink Implementation Report

原实施基线：`018949c14d1c3ac7e429205c9390f3970d40a5ba`  
Gate 3.4 收口基线：`9f204735e338ff7e87010ca58e628406673e13ae`

## 1. 范围

```text
manual streaming start
-> microphone lease
-> shared PyAudio capture
-> local VAD
-> shared PyAV Opus encoder/uplink
-> VAD end of speech
-> one listen/stop
-> readable STT / assistant transcript
-> WAITING_FOR_NEXT_TURN
-> manual session stop
```

本 Gate 不实现 TTS decode/playback，也不自动启动第二轮。完整播放和 PlaybackEnded 自动续轮属于 Gate 4。

## 2. 架构边界

- PTT/streaming 共用 AssistantAudioEngine；
- one audio worker、one uplink task、one WebSocket sender、one microphone lease；
- callback/worker 不写 AssistantState；
- event pump 是唯一有序入口；
- Controller 是唯一 state writer；
- connection/streaming/capture/session/turn token 拒绝陈旧回调；
- 本地 streaming UUID 不上 wire。

## 3. VAD

当前第一版：300 ms warmup、240 ms minimum speech、700 ms end silence、8 s no-speech timeout。真实结果只证明该设备/环境的一轮链路，不等于完成所有噪声和设备调优。

## 4. Gate 3.4 冻结的等待语义

有效 assistant text/TTS transcript 后：

- streaming state = WAITING_FOR_NEXT_TURN；
- session active = true；
- audio idle；
- capture/uplink/VAD/response timer/worker/lease 已停止；
- 不产生 next-turn capture；
- 用户手动 stop 才结束 Gate 3 session。

TTS transcript 不是 TTS playback。

## 5. 真实人工运行证据

以下数据来自用户提供的 Gate 3.3 真实人工运行验收，已脱敏；本收口环境未重新打开真实麦克风：

| 项目 | 结果 |
|---|---:|
| WebSocket handshake | success |
| real microphone capture | success |
| local VAD speech started/end | success |
| captured frames | 250 |
| encoded frames | 250 |
| uploaded frames | 250 |
| dropped PCM frames | 0 |
| uplink overflow | 0 |
| first PCM latency sample | 162 ms |
| first Opus latency sample | 165 ms |
| first Opus upload latency sample | 165 ms |
| stop listen latency sample | 49 ms |
| STT | readable text observed |
| assistant transcript | readable text observed |
| final status | `real_gate_complete` |

这些 latency 是单次样本，不是 p95。STT 可读只证明服务端返回可用文本，不声明识别准确率指标已经达标。

人工 stop 后确认已清理：capture、audio uplink、VAD、audio worker、response timer、microphone lease、pending assistant task。

## 6. 验收入口

自动：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

真实人工：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_3_REAL_STREAMING.ps1
```

Real runner 传播 0/1/2，且不输出未脱敏 token、完整 identity、密钥或完整 session id。

## 7. Gate 4 未实现

- binary TTS downlink decode；
- PyAudio output playback；
- actual PlaybackStarted/PlaybackEnded；
- PlaybackEnded automatic next turn；
- real two-turn continuous conversation；
- barge-in。

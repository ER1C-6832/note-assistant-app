# Gate 4 测试与验收计划

状态：Draft，随 Gate 4.0 Probe 冻结  
范围：TTS binary downlink、decode/resample、output、actual PlaybackEnded、auto next turn、real two-turn

## 1. 测试分层

```text
Static architecture
Pure models/format validation
Protocol router/transport ordering
Queue/backpressure unit
Decoder/resampler unit
Fake output deterministic drain
Reducer/Event/Effect ordering
Controller + Fake transport/playback integration
Offscreen QML
Windows real protocol probe
Windows real one-turn playback
Windows real two-turn
Shutdown/leak
Latency samples
```

真实线程 race 不作为自动测试手段。并发通过 Fake clock、barrier 和事件排列确定性覆盖。

## 2. 累计回归

每个 Gate 4 verifier 必须继续执行：

- Gate 1.7；
- Gate 2.1～2.7；
- Gate 3.1～3.4；
- 已完成的 Gate 4.x；
- Gate 2.7 Fake；
- Gate 3.1 offscreen QML；
- Gate 3.2 Fake PTT；
- Gate 3.3 Fake streaming；
- 当前 Gate 4 Fake runner。

根目录 PowerShell wrapper 是否被 Git 跟踪不属于 architecture acceptance。版本化测试只能要求 canonical Python verifier/tests/docs 存在。用户可在本地使用 ignored PowerShell wrapper 组合命令。

## 3. Gate 4.0 Protocol Probe 测试

### 3.1 ServerHello audio_params

覆盖：

- valid opus/mono/supported rate/frame duration；
- missing audio_params；
- audio_params 非 object；
- unsupported codec；
- zero/negative/invalid rate；
- unsupported channels；
- unknown extra fields；
- redaction 保持；
- connection generation stale。

### 3.2 TTS/binary ordering

覆盖：

```text
start -> binary -> stop
start -> many binary -> stop
start -> stop -> no binary
binary without start
duplicate start
duplicate stop
old stream binary after new start
disconnect before stop
unknown TTS state
```

真实 probe 必须把实际 observation 写入报告，Fake 不能替代格式结论。

### 3.3 Probe 隐私

- 不创建 `.opus/.pcm/.wav`；
- JSON 无 token/完整 identity/session；
- 不打印 binary repr/base64/hex；
- failure message 脱敏；
- output 明确 `payload_persisted=false`。

## 4. Gate 4.1 Foundation 测试

### 4.1 Models

- invalid generation/sequence rejected；
- empty packet rejected or classified；
- PCM alignment；
- format/channel/sample width validation；
- summary counters non-negative；
- monotonic timestamp only。

### 4.2 Encoded ingress

- begin once；
- offer in order；
- early packet bounded staging；
- end once；
- abort idempotent；
- overflow fail-current-stream；
- stale stream drop；
- close wakes waiting worker；
- no unbounded allocation。

### 4.3 PCM buffer/output

- callback consumes exact real samples；
- partial chunk consumption；
- underflow pads silence and counts；
- terminal+empty signals drain once；
- cancel does not signal natural drain；
- callback never blocks；
- close idempotent。

### 4.4 Decoder/resampler

使用确定性 PCM fixture 经 Opus encoder 生成 packet：

- decode produces PCM；
- expected rate/channels；
- sample count within codec tolerance；
- non-silent RMS；
- multiple packet order；
- flush；
- corrupt packet failure；
- resample source->device rate；
- no external process。

不要断言有损 Opus bit-exact。

## 5. actual PlaybackStarted/Ended 测试

### 5.1 Start

分别证明以下事件不会过早产生 PlaybackStarted：

- TTS start；
- assistant text；
- first binary arrival；
- first decode completion。

只有 FakeOutput 消费首个真实 PCM 时产生一次 PlaybackStarted。

### 5.2 End

为每个前置条件单独构造未满足场景：

- input terminal=false；
- encoded queue non-empty；
- decoder not flushed；
- PCM non-empty；
- last sample not consumed；
- stale playback generation；
- failed/cancelled。

任何一项未满足都不得自然 PlaybackEnded。全部满足时只产生一次。

### 5.3 Zero audio

- transcript retained；
- no played samples；
- no PlaybackEnded；
- no auto next；
- visible no-audio status；
- manual stop remains possible。

## 6. StateMachine/Controller 主矩阵

至少覆盖：

| 场景 | 关键断言 |
|---|---|
| transcript before TTS start | text updates; no speaking/no next |
| TTS start | buffering; one StartPlayback |
| duplicate TTS start | no second playback worker |
| first PCM consumed | actual speaking |
| TTS stop while PCM queued | no PlaybackEnded yet |
| final PCM consumed | one PlaybackEnded |
| non-streaming PlaybackEnded | connected; no capture |
| streaming PlaybackEnded | exactly one next capture |
| duplicate PlaybackEnded | no second capture |
| stale PlaybackEnded | unchanged/no effect |
| user stop during buffering | cancelled/inactive/no next |
| user stop during speaking | cancelled/inactive/no next |
| stop vs PlaybackEnded both orders | deterministic 0/1 next according to first terminal owner |
| disconnect buffering/speaking | cancel, no natural end/no next |
| mode switch | cancel before preference update |
| disable | playback/capture/timers zero |
| shutdown | transport/output/worker/tasks zero |
| playback failure | visible error/no next |
| next capture start failure | session error, no retry storm |

## 7. Queue/设备异常矩阵

至少覆盖：

- encoded ingress overflow；
- PCM overflow；
- isolated underflow；
- sustained underflow；
- corrupt Opus；
- decoder init failure；
- resampler failure；
- output device unavailable；
- unsupported output format；
- output open/start failure；
- callback status error；
- output close timeout；
- stream start watchdog；
- decoder progress watchdog；
- drain watchdog；
- cancellation during each blocking boundary。

所有异常要求：错误可见、资源释放、无 PlaybackEnded、无 next turn、无 unhandled task exception。

## 8. 真实一轮播放验收

### 8.1 人工流程

1. 使用真实 endpoint 连接；
2. streaming 或 PTT 说一句命令；
3. 服务端返回 TTS；
4. 用户确认听到完整、非静音、速度/音调合理的回复；
5. 等待 actual PlaybackEnded；
6. Gate 4.2 阶段手动停止 session，不自动第二轮；
7. 检查资源。

### 8.2 机器断言

```text
real_handshake_verified=true
binary_packets_received>0
decoded_samples>0
played_samples>0
playback_started_count=1
playback_ended_count=1
playback_cancelled=false
playback_failed=false
encoded_overflow_count=0
audio_output_active=false at final
playback_worker_alive=false at final
playback_task_running=false at final
queues_empty=true at final
pending assistant playback tasks=[]
```

用户听感确认不能被 counters 完全替代；counters 也不能被“我听到了”替代。

## 9. 真实两轮验收

### 9.1 流程

1. 用户手动开始 streaming；
2. 说第一句，保持安静；
3. VAD 自动提交；
4. 听到第一轮完整 TTS；
5. 不点击 start；
6. actual PlaybackEnded 自动启动第二轮 capture；
7. 用户说第二句；
8. 听到第二轮完整 TTS；
9. 用户手动结束 session。

### 9.2 机器断言

```text
streaming_turn_count=2
listen_start_count=2
listen_stop_count=2
playback_started_count=2
playback_ended_count=2
auto_next_turn_count=1
auto_next_source=PlaybackEnded
duplicate_next_turn_count=0
capture_playback_overlap_ms=0 (default mode)
uploaded_frames_each_turn>0
decoded_samples_each_turn>0
played_samples_each_turn>0
final streaming_session_active=false
all audio/runtime resources released
```

若第二次 capture 是 `tts/stop`、assistant text、timer 或人工 click 触发，Real two-turn 失败。

## 10. 资源终态

### A. 正常 playback 完成、连接保留

允许 transport sender/receiver 保留；必须无：

```text
active playback worker
active output stream
playback watchdog
encoded/PCM queued data for completed generation
stale decoder/resampler object
```

### B. streaming 自动进入下一轮

```text
previous playback fully closed
one microphone lease
one capture
one uplink
one VAD
no output stream
no playback/capture overlap
```

### C. disable/shutdown

必须无：

```text
reconnect timer
streaming/response/playback timer
audio uplink/VAD task
capture stream/audio worker/microphone lease
downlink ingress/playback worker/output stream
encoded/PCM queued data
transport sender/receiver
pending assistant-* asyncio task
second Python runtime process
```

## 11. QML 验收

- buffering、speaking、error visual 可区分；
- actual PlaybackStarted 前不显示“正在播放”；
- stop 在 buffering/speaking 可用；
- teardown 不访问已销毁 ViewModel；
- transcript 先到不触发 QML 自动开麦；
- offscreen smoke 不打开真实 output device；
- capability 未 active 时 UI fail-closed。

## 12. 性能记录

每次 Real runner 输出：

- first binary latency；
- first decode latency；
- first packet -> playback start；
- terminal -> drain；
- PlaybackEnded -> next capture request/start；
- buffer peak；
- underflow/overflow；
- stop/cancel/close latency。

单次只叫 sample。Gate 7 再执行 3 次预热 + 30 次正式样本并报告 p50/p95/max。

## 13. 建议版本化验收入口

```text
pc-app-build/tools/verify_gate4_0_real_downlink_probe.py
pc-app-build/tools/verify_gate4_1_fake_playback.py
pc-app-build/tools/verify_gate4_2_real_playback.py
pc-app-build/tools/verify_gate4_3_fake_two_turn.py
pc-app-build/tools/verify_gate4_3_real_two_turn.py
```

本地可选：

```text
VERIFY_GATE4.ps1
RUN_GATE4_REAL_PLAYBACK.ps1
RUN_GATE4_REAL_TWO_TURN.ps1
```

本地 wrapper 可 ignored，但必须 fail-fast 并传播 0/1/2：

- 0：pass；
- 1：implementation/acceptance failure；
- 2：environment/device/network/activation/operator blocked。

## 14. Gate 4 最终通过条件

- Black/Ruff/compileall 全绿；
- pytest `-W error` 累计 Gate 1.7～4.4 全绿；
- 所有 Fake runner 返回 0；
- QML smoke 返回 0；
- Gate 4.0 Real Probe 返回 0；
- Gate 4.2 Real Playback 返回 0；
- Gate 4.3 Real Two-turn 返回 0；
- 真实报告记录当前 HEAD 与环境；
- 无敏感音频/配置进入交付包；
- actual PlaybackEnded 与 auto-next 唯一性有自动和 Real 双重证据；
- shutdown/leak matrix 全通过；
- 未实现 acoustic barge-in/AEC/KWS/MCP 不得写成已完成。


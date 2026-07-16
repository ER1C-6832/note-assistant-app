# Gate 4 TTS Playback 与真实两轮连续对话 Spec

状态：Draft，等待 Gate 4.0 Real Protocol Probe 冻结  
规划输入基线：`93f022fd22d77a059380410fc14e4cf990afc12a`

## 1. 目的

Gate 4 在现有单进程 Runtime 内完成真实 TTS 二进制下行、Opus 解码、扬声器播放、物理播放完成检测和连续对话自动第二轮。

Gate 4 的完成定义不是“收到 TTS 文本”或“收到二进制包”，而是：

```text
真实服务端回复
-> 真实 Opus binary downlink
-> 真实 decode/resample
-> 真实 output device consumption
-> actual PlaybackEnded
-> exactly one next-turn capture
-> 第二轮真实语音和真实回复播放
```

## 2. 当前差距

Gate 3 结束时：

- `XiaozhiMessageRouter.route_binary()` 只保留 `size_bytes`，不保留 payload；
- `BinaryAudioReceived` 只更新协议诊断；
- `PlaybackStarted`、`PlaybackEnded`、`PlaybackCountersUpdated` 是 not-ready placeholder；
- 没有 decoder、resampler、encoded downlink queue、PCM playback buffer 或 output adapter；
- `ServerHello` 尚未保存服务端 `audio_params`；
- `AudioState` 已预留 `playback_generation`、`decoded_frames`、`played_frames`，但未激活；
- streaming 回复停在 `WAITING_FOR_NEXT_TURN`，等待手动 stop。

因此 Gate 4 必须先完成协议和热路径设计，不能直接在 `BinaryAudioReceived` 中调用 PyAudio。

## 3. 强制架构

### 3.1 数据路径

```text
RealWebSocketTransport receiver
-> DownlinkAudioIngressPort.begin_stream / offer_packet / end_stream
-> bounded EncodedDownlinkQueue
-> one AssistantPlaybackEngine worker
-> PyAV Opus decoder
-> optional PyAV AudioResampler
-> bounded PCM PlaybackBuffer
-> PyAudio output callback
-> local drain confirmation
-> PlaybackEnded event
-> Controller event pump
```

### 3.2 控制路径与热路径分离

Runtime event queue 只允许小型不可变控制事件：

- TTS stream begin/end metadata；
- `PlaybackStarted`；
- 节流后的 `PlaybackCountersUpdated`；
- `PlaybackFailed`；
- `PlaybackEnded`。

以下内容禁止进入 Runtime event queue 或 AssistantState：

- Opus payload；
- PCM payload；
- 每个 20/60 ms packet 对应的 Effect task；
- PyAV frame 对象；
- PyAudio stream 对象。

### 3.3 所有权

| 对象 | 唯一所有者 | 允许工作 | 禁止工作 |
|---|---|---|---|
| WebSocket receiver | RealWebSocketTransport | 按 wire 顺序解析 TTS 与 binary、非阻塞投递 ingress | decode、device write、AssistantState 写入 |
| Encoded ingress | DownlinkAudioIngress | 有界保存当前 stream 的 Opus packet | 无界缓存、阻塞 receiver |
| Playback worker | AssistantPlaybackEngine | decode、resample、统计、协调关闭 | 修改 AssistantState、调用 QML、创建第二 event loop |
| PyAudio output callback | PyAudioOutputAdapter | 从 PCM buffer 读取、补零、报告 consumed samples | decode、JSON、网络、状态写入、阻塞等待 |
| Controller event pump | AssistantController | Reducer、状态发布、粗粒度 Effect 协调 | Opus/PCM 热路径 |

AssistantPlaybackEngine 必须是独立播放组件，不把下行 decode/output 逻辑塞入现有 capture/VAD worker。两者可以共用 audio models/queue utilities，但生命周期、generation 和 worker 分离，为以后 AEC/设备恢复保留边界。

## 4. 下行格式与协议探测

### 4.1 不能假设上下行参数相同

当前 client hello 请求：

```text
format=opus
sample_rate=16000
channels=1
frame_duration=20ms
```

这只冻结当前上行契约，不足以证明官方云下行也是 16 kHz / 20 ms。Gate 4.0 必须在当前真实 endpoint 上采集：

- ServerHello 是否包含 `audio_params`；
- codec；
- sample rate；
- channels；
- frame duration；
- `tts` state 顺序；
- binary packet count、size 分布与到达间隔；
- terminal TTS state 与最后一个 binary 的相对顺序；
- 一次真实 payload 是否可被 PyAV Opus decoder 解码。

探测默认只输出脱敏 metadata，不保存用户语音、TTS payload 或解码 PCM。

### 4.2 格式选择优先级

实现冻结后，格式来源优先级为：

1. 当前 connection 的有效 ServerHello `audio_params`；
2. Gate 4.0 已明确验证并记录的 endpoint compatibility profile；
3. 否则 fail closed，显示 `downlink_audio_format_unknown`。

禁止：

- 静默使用上行 16 kHz 作为下行格式；
- 看到 packet 大小后猜采样率；
- decode 失败后循环尝试多个采样率而不记录；
- 把 endpoint 特例硬编码进 QML。

### 4.3 支持范围

第一版接受：

- codec：Opus；
- channels：mono；
- sample rate：Opus 合法值中的 Gate 4.0 已验证集合；
- frame duration：Gate 4.0 已验证集合。

收到 unsupported codec/channel/rate/duration 时终止当前 playback，产生可见错误，不自动进入下一轮。

## 5. Stream correlation

### 5.1 标识

每个下行 stream 至少携带：

```text
connection_generation
transport_stream_sequence
playback_generation
server session_id
local turn_token
streaming_generation（若属于连续对话）
packet_sequence
```

- `transport_stream_sequence` 由当前 transport generation 按 wire TTS stream 顺序单调递增；
- `playback_generation` 由 Runtime/StateMachine 单调分配；
- 两者建立一对一映射；
- 本地 token 不写入 wire；
- 任一 generation/token 不匹配的 packet、callback、timer 或 drain 事件都是 no-op，并计入 stale diagnostics。

### 5.2 Ingress ordering

推荐顺序：

```text
wire tts/start
-> transport increments stream_sequence
-> ingress.begin_stream(context)
-> enqueue small TtsStreamStarted event

wire binary
-> ingress.offer_packet(stream_sequence, bytes, received_at_ns)

wire terminal tts state
-> ingress.end_stream(stream_sequence, reason)
-> enqueue small TtsStreamInputEnded event
```

Ingress 可以在 `StartPlayback` Effect 实际执行前有界暂存同一 stream 的早到 packet，避免 receiver/event/effect 调度之间的竞态。

若真实探测发现 binary 可能早于 `tts/start`，必须在 Gate 4.0 报告中记录并冻结明确 fallback；否则 unarmed binary 是协议错误，不得归属到旧 stream。

## 6. 建议模型与 Ports

名称可以根据现有代码风格微调，但角色和边界不得合并。

### 6.1 Models

```text
DownlinkAudioFormat
TtsStreamContext
EncodedDownlinkPacket
DecodedPcmChunk
PlaybackMetrics
PlaybackSummary
PlaybackFailure
```

关键字段：

- format/rate/channels/frame duration；
- connection/stream/playback/turn generation；
- sequence；
- monotonic timestamps；
- payload length；
- decoded/played samples；
- queue depth/overflow/underflow；
- output device public name；
- terminal/drain/cancel reason。

### 6.2 Ports

```python
class DownlinkAudioIngressPort(Protocol):
    def begin_stream(self, context: TtsStreamContext) -> None: ...
    def offer_packet(self, packet: EncodedDownlinkPacket) -> bool: ...
    def end_stream(self, stream_sequence: int, reason: str) -> None: ...
    def abort_stream(self, stream_sequence: int, reason: str) -> None: ...

class OpusDecoderPort(Protocol):
    def decode(self, packet: EncodedDownlinkPacket) -> tuple[DecodedPcmChunk, ...]: ...
    def flush(self) -> tuple[DecodedPcmChunk, ...]: ...
    def close(self) -> None: ...

class AudioOutputPort(Protocol):
    def open(self, output_format, pcm_source, consumed_callback) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
```

Fake ingress/decoder/output 必须可替换真实实现，Controller/Reducer 测试不得打开真实设备。

## 7. 队列、buffer 与 backpressure

### 7.1 基本原则

- encoded ingress 与 PCM buffer 都必须有界；
- receiver 投递不得等待 output device；
- 不允许 drop-oldest 后继续播放破损 TTS；
- encoded overflow 结束当前 playback 并产生 `downlink_overflow`；
- PCM producer 可以在 playback worker 内有界等待 callback 消费，但必须响应 cancel/stop；
- output callback 永不阻塞等待 decoder；
- underflow 时输出短静音并计数，不读取无效内存；
- 持续 underflow 或 drain watchdog 超时必须失败关闭。

### 7.2 初始预算

Gate 4.0 冻结 frame duration 后，将容量换算为时间而非只写 packet 数：

```text
encoded buffered audio budget: <= 2000 ms
PCM buffered audio budget: <= 2000 ms
startup prebuffer: 1～2 个已验证 frame，目标 <= 120 ms
```

最终 packet capacity、PCM chunk capacity、startup prebuffer 和 watchdog 数值必须写入 Gate 4.0 报告及实现常量。改变这些值需要测试更新，不得藏在 magic number 中。

## 8. Decode、resample 与 output

### 8.1 Decoder

- 使用 PyAV/FFmpeg Opus decoder；
- 不新增外部 ffmpeg subprocess；
- decode 在唯一 playback worker 中执行；
- corrupt packet 产生可见、脱敏错误；
- terminal 后调用 decoder flush；
- 不要求 PCM bit-exact，但 sample count、format、channel 和非静音能量应可测试。

### 8.2 Resample

Decoder 源格式来自协商结果。Output adapter 优先尝试设备支持的源采样率；若设备不支持，则通过 PyAV AudioResampler 在 playback worker 中转换到 adapter 明确选择的设备格式。

Core 不硬编码 Windows API，也不假设 macOS/Windows 默认设备都支持 24 kHz。平台能力查询属于 Adapter；格式选择结果通过 public diagnostics 暴露。

### 8.3 Output callback

- 只消费 PCM16；
- mono 到设备 channel layout 的转换在 worker/resampler 完成；
- 记录实际 consumed samples；
- input terminal 且 PCM 完全消费后发出 thread-safe drain signal；
- callback 不直接 emit Controller event，由 playback coordinator 转换为粗粒度事件。

## 9. actual PlaybackStarted / PlaybackEnded

### 9.1 PlaybackStarted

只有第一批真实 PCM 已提交给已启动的 output stream，才允许发出 `PlaybackStarted`。以下均不算开始播放：

- 收到 `tts/start`；
- 收到 assistant transcript；
- 收到首个 binary；
- 首个 packet decode 完成但 output 未启动。

### 9.2 PlaybackEnded

只有同时满足以下条件，才允许发出 actual `PlaybackEnded`：

```text
current TTS input is terminal
AND encoded ingress is empty
AND decoder flush is complete
AND PCM playback buffer is empty
AND output callback consumed the last real sample
AND current connection/stream/playback generation still matches
AND playback was not failed or cancelled
```

以下均不得单独产生 `PlaybackEnded`：

- `tts/stop`、`tts/end` 或其他 terminal JSON；
- 最后一个 binary 入队；
- decoder queue 为空但 PCM 尚未播放；
- 根据文本长度估算的 timer；
- user stop、disconnect、disable、shutdown；
- device failure。

取消和失败使用 `PlaybackCancelled`/`PlaybackFailed` 语义，不得伪装成自然播放完成。

### 9.3 Zero-audio response

如果收到 TTS transcript/terminal，但没有任何可播放 PCM：

- 保留可读 transcript；
- 产生 `playback_no_audio` 或等价可见诊断；
- streaming session 可以停在 `WAITING_FOR_NEXT_TURN` 等待用户手动处理；
- 不自动开麦；
- 不伪造 `PlaybackEnded`。

## 10. Runtime 状态语义

### 10.1 建议新增状态

在 `StreamingConversationState` 增加：

```text
BUFFERING_PLAYBACK
```

当前 `SPEAKING` 保留，但必须由 actual `PlaybackStarted` 进入。

### 10.2 连续模式主链路

```text
LISTENING_FOR_SPEECH
-> USER_SPEAKING
-> SUBMITTING_TURN
-> THINKING
-> TtsStreamStarted
-> BUFFERING_PLAYBACK
-> actual PlaybackStarted
-> SPEAKING
-> actual PlaybackEnded
-> STARTING next turn
-> LISTENING_FOR_SPEECH
```

### 10.3 Gate 3 兼容语义调整

Gate 3 中，可读 assistant text/TTS transcript 会直接进入 `WAITING_FOR_NEXT_TURN`，因为当时没有播放能力。

Gate 4 激活 TTS playback capability 后：

- transcript 只更新文本并取消 response timeout；
- 若已经观察到当前 TTS stream，进入/保持 `BUFFERING_PLAYBACK`；
- transcript 自身不完成 playback；
- 若在协议 watchdog 内没有任何可播放 stream，则进入 zero-audio 处理；
- 不得继续沿用“看到文本就认为本轮物理播放结束”的 Gate 3 临时语义。

### 10.4 非连续模式

PTT 或文本 turn 的真实 TTS 播放完成后：

```text
PlaybackEnded -> audio idle -> phase connected
```

不自动打开麦克风。

## 11. PlaybackEnded 唯一续轮规则

自动下一轮必须同时满足：

```text
event is actual PlaybackEnded
AND event.playback_generation == current playback_generation
AND event.turn_token == current completed streaming turn
AND event.connection_generation == current connection_generation
AND streaming_session_active == true
AND preferred_voice_mode == STREAMING_CONVERSATION
AND assistant enabled and connected
AND no user stop / mode switch / disconnect / disable / shutdown
AND no playback failure/cancel
AND next turn has not already been allocated
```

满足时 Reducer 一次性：

- 标记上一 playback generation 完成；
- `streaming_turn_index += 1`；
- 分配新的 turn token 与 capture generation；
- 进入 `STARTING`；
- 产生且只产生一个 `StartStreamingConversation` Effect。

重复 `PlaybackEnded`、迟到 callback 和旧 generation no-op。

以下事件绝不是续轮源：

- `AssistantTextReceived`；
- `TtsStateReceived`；
- `TtsStreamInputEnded`；
- terminal `tts/stop`；
- `VoiceTurnCompleted`；
- playback timer；
- decoder flush；
- queue empty observation。

## 12. Interruption 与 barge-in 边界

### 12.1 Gate 4 必须支持

- 用户在 playback 时点击 stop：取消 playback、清空 buffer、结束 streaming session，不续轮；
- mode switch：先取消 playback/session，再持久化 mode；
- disable/shutdown：有界关闭 output、worker 和队列；
- manual disconnect：取消 playback，不重放旧回复。

### 12.2 可选简单 interruption

Gate 4.4 可选实现“先停止播放，再打开麦克风”的显式用户操作。必须先收到当前 playback cancel 完成，才能申请 microphone lease。

### 12.3 非目标

Gate 4 不实现扬声器播放期间持续开麦的 acoustic/full-duplex barge-in。没有 AEC 时不得为追求插话把 capture 与 playback 默认重叠。真正声学 barge-in、AEC 和 echo reference 属于 Gate 6。

`BARGE_IN` capability 在未完成独立真实验收前保持 not-ready/default-off，不阻塞 Gate 4.3 两轮闭环。

## 13. Recovery 与错误

### 13.1 Disconnect

disconnect during buffering/speaking：

- invalidate connection/playback generation；
- abort ingress；
- stop output；
- clear PCM/encoded buffers；
- cancel playback watchdog；
- 不产生 PlaybackEnded；
- 不基于旧 playback 自动续轮；
- transport 可以按既有 ReconnectPolicy 恢复连接，但不得重放已丢失的旧 TTS。

第一版推荐结束当前 streaming session并显示 recoverable error；不要在回复播放到一半后静默重新开麦。

### 13.2 Device failure

output device open/start/callback/close failure：

- error 可见且脱敏；
- current playback failed；
- no next turn；
- 资源释放；
- transport 是否保持 connected 由错误类别决定，不能因为本地扬声器失败强制破坏正常 socket。

### 13.3 Watchdogs

至少需要：

- stream start/binary arrival watchdog；
- decoder progress watchdog；
- terminal drain watchdog；
- bounded output close timeout。

Watchdog 只产生 failure/cancel event，不产生自然 PlaybackEnded。

## 14. State/Event/Effect 契约

### 14.1 State

在现有 AudioState 或独立 PlaybackState 中记录：

```text
playback_generation
active_stream_sequence
active_playback_turn_token
downlink_format_public
output_device_public_name
encoded_packets_received
decoded_samples / decoded_frames
played_samples / played_frames
encoded_overflow_count
pcm_underflow_count
pcm_overflow_count
first_downlink_packet_latency_ms
first_decoded_pcm_latency_ms
playback_start_latency_ms
playback_duration_ms
last_playback_end_reason
```

不得把 payload、完整设备敏感标识或 PyAudio/PyAV 对象放入 state。

### 14.2 Events

推荐激活/新增：

```text
TtsStreamStarted
TtsStreamInputEnded
PlaybackStarted
PlaybackCountersUpdated
PlaybackEnded
PlaybackCancelled
PlaybackFailed
DownlinkAudioOverflow
PlaybackUnderflowObserved（节流）
```

所有 event 包含足够 generation/token 进行 stale rejection。

### 14.3 Effects

推荐新增：

```text
StartPlayback
CancelPlayback
SchedulePlaybackWatchdog
CancelPlaybackWatchdog
```

Binary packet 不对应 Effect。`StartStreamingConversation` 只能由用户 start、现有 recovery 合法路径或 actual PlaybackEnded 合法路径产生。

## 15. UI 投影

- actual `PlaybackStarted` 后 Aurora 才进入 Speaking visual；
- buffering 与 speaking 使用不同状态文本；
- transcript 可以先显示，但不能让 UI 声称“播放完成”；
- playback failure 显示可恢复错误；
- playback 时 stop 控件可用；
- full-duplex barge-in 设置不在本 Gate 默认暴露；
- Developer diagnostics 显示脱敏格式、设备名、packet/sample/counter、underflow/overflow 和 latency sample。

QML 不直接持有 decoder/output/stream，也不根据动画结束推断 PlaybackEnded。

## 16. 指标

必须使用 `time.perf_counter_ns()` 或现有 monotonic clock：

```text
tts_stream_started
first_downlink_packet
first_decoded_pcm
output_opened
playback_started
tts_input_terminal
last_pcm_consumed
playback_ended
next_capture_requested
next_capture_started
```

派生：

- first packet -> first decoded PCM；
- first packet -> actual playback start；
- terminal -> actual drain；
- PlaybackEnded -> next capture request/start；
- buffer peak；
- underflow/overflow；
- cancel/close latency。

Gate 4 单次真实运行只报告 sample。p50/p95/max 属于 Gate 7，不能用单次结果宣称 p95。目标仍是 TTS packet 到实际播放 p95 < 120 ms。

## 17. 安全、隐私与日志

- 默认不持久化 Opus/PCM；
- 报告只记录 packet size/count/timing、format 和脱敏错误；
- 不输出 token、authorization、完整 device/client/session identity；
- 用户 spoken/TTS 内容只按既有 transcript 隐私策略处理；
- debug dump 必须显式 opt-in、默认关闭且不进入交付包；
- queue/decoder 错误不得打印原始 binary。

## 18. 跨平台约束

- Core、StateMachine、models、ports 不导入 Windows/macOS 专用 API；
- PyAudio/PyAV concrete adapter 位于平台边界；
- 第一轮真实 Gate 可以以 Windows 为必过目标；
- 设计不得阻止后续 macOS output device acceptance；
- output sample rate/channel 必须通过 adapter/format planner 决定，不以 Windows 默认值写死；
- 不启动外部 ffmpeg 进程。

## 19. Gate 4 完成定义

Gate 4 只有同时满足以下条件才完成：

1. Gate 4.0 真实协议探测已归档；
2. Fake decode/output/drain 全通过；
3. 真实一轮 TTS audible playback 通过；
4. actual PlaybackEnded 由设备 drain 产生；
5. 真实两轮连续对话通过；
6. 第二轮只由第一次 actual PlaybackEnded 触发一次；
7. 默认 capture/playback 不重叠；
8. stop/disconnect/disable/shutdown 不产生自动续轮；
9. 全异常矩阵和累计 Gate 1.7～4.x 回归通过；
10. shutdown 后无 playback/capture/transport/assistant task 泄漏；
11. 单进程、单 event loop、单 sender、单 Controller state writer 保持；
12. 文档不把 transcript、`tts/stop` 或 queue empty 描述成物理播放完成。


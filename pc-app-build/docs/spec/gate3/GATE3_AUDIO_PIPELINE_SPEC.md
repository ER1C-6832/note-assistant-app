# Gate 3 共用音频管线 Spec

## 1. 目标

构建一套供 PTT 和连续对话共同使用的 PC 音频上行管线。两种模式只改变会话策略、VAD/停止条件和协议命令，不创建两套 AudioEngine。

## 2. 总链路

```text
PyAudio Input Callback
-> fixed PCM16 frame copy
-> bounded thread-safe PCM ingress
-> Audio Worker
   -> meters / VAD
   -> Opus encode
-> bounded encoded packet queue
-> qasync Audio Uplink Effect owner
-> RealWebSocketTransport binary send queue
-> one WebSocket sender
```

Audio callback 不调用 asyncio、不发送 WebSocket、不修改 AssistantState。

## 3. 平台与格式

第一版：

```text
input API: PyAudio / PortAudio
sample format: PCM16 little-endian
sample rate: 16000 Hz
channels: 1
frame duration: 20 ms
samples/frame: 320
bytes/frame: 640
Opus application: VOIP
uplink target bitrate: 24 kbps
```

如果设备不原生支持 16 kHz，Adapter 可以在平台层显式转换，但必须记录实际设备参数；不得让协议层感知具体声卡。

## 4. 模块边界

建议目录：

```text
assistant/audio/
├─ ports.py
├─ models.py
├─ engine.py
├─ capture.py
├─ opus_codec.py
├─ vad.py
├─ queues.py
├─ fake_audio.py
└─ pyaudio_adapter.py
```

### Core / Port

定义不可变数据和 Protocol：

```text
PcmFrame
EncodedAudioPacket
VoiceActivitySnapshot
AudioCapturePort
OpusEncoderPort
VoiceActivityDetectorPort
AudioClock
```

### Adapter

`PyAudioCaptureAdapter` 只处理：

- 设备打开/关闭；
- callback 中固定长度复制；
- callback 时间戳；
- 向线程安全 ingress 投递。

### Engine

`AssistantAudioEngine` 负责：

- capture generation；
- worker 生命周期；
- PCM queue；
- VAD/Opus；
- packet queue；
- 统计事件；
- stop/abort 有界等待。

它不写 AssistantState，不直接调用 QML。

## 5. 执行域

| 执行域 | 工作 | 禁止 |
|---|---|---|
| Qt/qasync 主线程 | Controller、Effects、WebSocket 协调 | 阻塞设备、CPU 编码 |
| PortAudio callback thread | 复制 PCM、try_put | JSON、日志格式化、状态转换、网络 |
| Audio worker thread | VAD、Opus、统计 | QML、Repository、直接 State 写入 |
| qasync uplink task | 从 packet queue 取包并提交 Transport | 编码、设备调用 |

不创建第二个长期 asyncio loop。

## 6. 队列与溢出

### PCM ingress

```text
capacity: 8 frames (~160 ms)
overflow: drop oldest
callback: never block
metrics: pcm_drop_oldest_count
```

### Encoded packet queue

```text
capacity: 16 packets
overflow: fail current turn
result: RuntimeOverloaded / AudioUplinkOverflow event
```

不能无限扩容或静默丢新 Opus 包，因为会破坏语音时序。

### WebSocket sender queue

沿用 Gate 2 单 sender。音频包和文本/控制消息必须通过 Transport 既有所有权串行化；不能另开一个 socket sender。

## 7. Generation

至少区分：

```text
connection_generation
capture_generation
streaming_generation
turn_token
```

每个 PCM frame 和 Encoded packet 携带 capture generation；旧 generation 到达 worker、uplink task 或 callback 时直接丢弃并计数。

stop、abort、mode change、disable、disconnect、shutdown 都必须使当前 capture generation 失效。

## 8. 麦克风所有权

State 已保留：

```text
none
wakeword_kws
assistant_capture
```

Gate 3 只激活 `none` 和 `assistant_capture`；KWS owner 保留但不启动。

Controller 通过 `AcquireMicrophone` Effect 获取 lease；AudioEngine 不能自行抢占。第一版同一时刻只允许一个 capture session。

## 9. PTT 策略

```text
PTT down
-> validate enabled/connected/mode/capability
-> acquire microphone
-> send listen/start manual
-> start capture
-> Listening / Recording

PTT up
-> stop capture with budget
-> if useful audio: send listen/stop -> Thinking
-> else: send abort -> Connected
-> release microphone
```

目标：

- down 到首帧 PCM p95 < 150 ms；
- down 到首个 Opus 上行 p95 < 220 ms；
- up 到 stop listen 发出 p95 < 80 ms；
- stop capture 有硬超时并可见失败。

## 10. 连续对话策略

连续模式复用同一 capture：

- 使用 streaming capture config；
- VAD 预热；
- speech start/end 自动事件；
- no speech timeout；
- 一轮结束后停止当前 capture 并释放麦克风；
- 等待回复/播放完成后再创建下一 capture generation。

不允许在 Thinking/Speaking 时保留普通上行录音，除非 Gate 4.2 明确启动 barge-in monitor。

## 11. 关闭顺序

```text
invalidate generation
-> stop accepting callback frames
-> stop/close PyAudio stream
-> wake worker
-> cancel/await uplink task
-> drain/drop old queues
-> terminate codec resources
-> release microphone lease
```

- 所有步骤有界；
- callback 在 close 后到达也只能因 generation 失效而被丢弃；
- shutdown 后无 audio worker、uplink task 或打开设备。

## 12. Fake Audio

Gate 3.1 先实现可脚本化 Fake Audio：

- 固定 PCM frames；
- speech/no-speech 序列；
- 编码成功/失败；
- queue overflow；
- start/stop delay；
- stale generation frame；
- device open failure。

Fake 与 Real 使用相同 Controller Event 和 reducer 路径。

## 13. 禁止项

- `PttAudioEngine` 与 `StreamingAudioEngine` 两套实现；
- callback 直接 `asyncio.run_coroutine_threadsafe(send...)`；
- AudioEngine 直接修改 `self._state`；
- 无界 PCM/Opus 队列；
- stop 后复用旧 generation；
- PyAudio adapter 中硬编码 listen/start/stop；
- 为编码性能默认引入多进程。

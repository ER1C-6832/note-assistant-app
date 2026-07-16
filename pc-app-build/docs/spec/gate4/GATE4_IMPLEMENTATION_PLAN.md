# Gate 4 分阶段实施计划

状态：Gate 4 实现完成；4.4 Final Acceptance Candidate  
目标：真实 TTS Playback + actual PlaybackEnded + 真实两轮连续对话

## 1. 实施原则

- 一次只推进一个可验收子 Gate；
- 每阶段先写/更新 Spec 与测试，再实现；
- 每阶段继续执行 Gate 1.7、Gate 2.1～2.7、Gate 3.1～3.4 累计回归；
- Real 协议、设备和人工听感不由 Fake 代替；
- 根目录 PowerShell wrapper 可按当前项目策略保持本地 ignored，不作为源码 architecture test 必备资产；
- 版本化 canonical 资产放在 `pc-app-build/tests`、`pc-app-build/tools`、`pc-app-build/docs`；
- 不在 Gate 4 顺带实现 MCP、KWS、AEC 或全双工 barge-in。

## 2. Gate 4.0：Real Downlink Protocol Probe 与 Spec Freeze

### 目标

在不播放声音、不保存音频内容的前提下，确认当前真实 endpoint 的下行协议和可解码性。

### 代码范围

- 扩展 ServerHello typed model/router，解析经过验证的 `audio_params`；
- 新增只保存 metadata 的 downlink probe sink；
- 让真实 transport 能把 binary payload 非阻塞交给专用 sink，而不是 Runtime event queue；
- 不创建 output stream；
- 不激活 TTS_PLAYBACK capability。

### 建议资产

```text
pc-app-build/tools/verify_gate4_0_real_downlink_probe.py
pc-app-build/tests/gate4_0/
pc-app-build/docs/report/GATE4_0_REAL_PROTOCOL_PROBE_REPORT.md
```

### Probe 输出

```text
server hello audio format
observed TTS state sequence
binary packet count
min/max/median packet size
packet arrival interval sample
first/last binary relative to TTS terminal
PyAV decode success
decoded sample rate/channels/sample count
payload_persisted=false
secrets_redacted=true
```

### 自动测试

- valid/missing/invalid hello audio_params；
- unsupported codec/channel/rate；
- TTS state 与 stream_sequence；
- unarmed binary；
- stale connection generation；
- bounded probe sink overflow；
- Runtime event queue 不携带 binary payload；
- probe 不写 Opus/PCM 文件。

### Real 验收

用户说一句命令，服务端返回一轮 TTS。Probe 必须：

- 捕获至少一个 binary packet；
- 输出可解释的格式；
- 至少解码一个有效 Opus packet；
- 不打开扬声器；
- 不保存 payload；
- 退出后无 transport/probe task。

### 退出条件

- 真实 probe 返回 0；
- Probe Report 填入实际结果；
- `GATE4_TTS_PLAYBACK_AND_TWO_TURN_SPEC.md` 中格式、TTS 状态和容量参数由 Draft 更新为 Frozen；
- 若官方云与开源 server 行为不同，以真实当前 endpoint 为准并记录差异。

## 3. Gate 4.1：Playback Foundation、Ports、Queues 与 Fake

### 目标

建立完全可 Fake、无真实设备依赖的下行播放基础。

### 代码范围

建议新增：

```text
app/assistant/playback/
├─ __init__.py
├─ models.py
├─ ports.py
├─ queues.py
├─ engine.py
├─ opus_decoder.py
├─ format_planner.py
├─ pyaudio_output.py       # 本阶段可只有 concrete scaffold，测试不打开设备
└─ fakes.py
```

也可位于现有 `assistant/audio/playback/`，但 capture engine 与 playback engine 必须保持独立生命周期。

实现：

- DownlinkAudioFormat；
- TtsStreamContext；
- encoded/PCM bounded queues；
- DownlinkAudioIngress；
- OpusDecoderPort/Fake；
- AudioOutputPort/Fake；
- AssistantPlaybackEngine；
- begin/offer/end/cancel；
- actual drain detection；
- counters/summary/failure；
- generation/stale rejection；
- shutdown/close 幂等。

### State/Event/Effect

- 增加 `BUFFERING_PLAYBACK`；
- 激活 playback events/effects，但 capability 仍可保持 not-ready，直到 Real 4.2；
- `PlaybackStarted` 只由 Fake output 首次消费真实 PCM 产生；
- `PlaybackEnded` 只由 terminal + full drain 产生；
- transcript/tts-stop 不产生 next turn。

### 自动验收

- deterministic fake Opus/PCM stream；
- ordered start/decode/play/end；
- early packets before StartPlayback Effect；
- corrupt packet；
- encoded overflow；
- underflow；
- cancel before start/during buffering/during playing；
- duplicate terminal/drain；
- stale generation；
- zero-audio response；
- disable/shutdown no worker/task/queue leak；
- no payload in Runtime event queue；
- no subprocess/multiprocessing。

### 退出条件

- Fake 一轮从 TTS start 到 actual PlaybackEnded 通过；
- `PlaybackEnded` 重复/迟到 no-op；
- 所有队列有界；
- Fake output 可证明 last sample consumed；
- Gate 1.7～3.4 累计回归全绿。

## 4. Gate 4.2：PyAV Decode、PyAudio Output 与真实一轮播放

### 目标

在真实 Windows output device 上播放一轮真实服务端 TTS，并获得 actual PlaybackEnded。

### 代码范围

- PyAV Opus decoder；
- PyAV AudioResampler；
- output format planner；
- PyAudio output callback adapter；
- device public diagnostics；
- first packet/decode/play/end latency；
- playback watchdog；
- Controller composition root wiring；
- Aurora buffering/speaking/error projection；
- TTS_PLAYBACK capability 在成功接入后 active。

### 必须保持

- decode 不在 Qt/qasync 主线程；
- callback 不 decode、不写状态；
- transport receiver 不等待播放完成；
- 不启动外部 ffmpeg；
- 不自动开启下一轮；Gate 4.2 只证明一轮真实播放。

### 建议资产

```text
pc-app-build/tools/verify_gate4_2_fake_playback.py
pc-app-build/tools/verify_gate4_2_real_playback.py
pc-app-build/tests/gate4_2/
pc-app-build/docs/report/GATE4_2_IMPLEMENTATION_REPORT.md
```

### Real runner

用户说一句真实命令并确认听到完整回复。至少验证：

- real handshake；
- real microphone/uplink；
- binary packets > 0；
- decoded samples > 0；
- played samples > 0；
- output callback consumed final sample；
- exactly one actual PlaybackStarted/Ended；
- no overflow；
- underflow 计数可见；
- final audio output/worker/queue/task closed；
- transcript 与 audio 均归属当前 turn；
- 单次 latency 如实报告，不声称 p95。

### 退出条件

- 自动 Fake/Unit/Architecture/QML 全绿；
- 真实 Windows playback runner 返回 0；
- 人工确认非静音、速度/音调合理、没有明显截断；
- stop/disconnect/disable/shutdown 不产生自然 PlaybackEnded；
- Gate 4.2 报告记录真实结果。

## 5. Gate 4.3：PlaybackEnded Auto Next Turn 与真实两轮

### 目标

把 Gate 3 的一轮 streaming session 升级为真实两轮闭环。

### 代码范围

- Reducer 中激活 actual PlaybackEnded 唯一续轮规则；
- allocation ledger/token 防重复；
- new turn index/token/capture generation；
- StartStreamingConversation exactly once；
- no capture/playback overlap；
- stop/mode switch/disconnect/disable precedence；
- two-turn fake transport/audio/output scenario；
- real two-turn runner。

### 状态链路

```text
turn 1 capture/VAD/submit
-> response buffering
-> real playback 1
-> actual PlaybackEnded 1
-> exactly one capture 2
-> turn 2 capture/VAD/submit
-> real playback 2
-> actual PlaybackEnded 2
-> manual session stop
```

### 必测并发排列

- PlaybackEnded then user stop；
- user stop then PlaybackEnded；
- PlaybackEnded then disconnect；
- disconnect then PlaybackEnded；
- PlaybackEnded then mode switch；
- duplicate PlaybackEnded；
- stale playback generation；
- playback failure then terminal；
- disable/shutdown during last drain；
- next capture start failure。

每个排列检查 next-turn start 计数只能为 0 或 1，且由规则确定，不能偶发。

### Real runner

- 用户第一轮说话；
- 听到完整回复；
- 不点击 start，应用自动进入第二轮 listening；
- 用户第二轮说话；
- 听到第二轮完整回复；
- 用户手动结束 session；
- 输出两轮 capture/upload/playback counters 与 generation/token 摘要；
- 证明两轮之间唯一触发源为 PlaybackEnded；
- 最终无 audio/runtime task 泄漏。

### 退出条件

- Fake two-turn 完整通过；
- Real two-turn 返回 0；
- 第二次 capture 只启动一次；
- 默认无 capture/playback overlap；
- 失败/取消不自动续轮；
- streaming capability detail 更新为真实两轮 active。

## 6. Gate 4.4：可选简单 interruption 与总收口

### 必做收口

- 用户 playback 中 stop；
- 资源终态矩阵；
- 全异常矩阵；
- cumulative verifier；
- Gate 4 Final Acceptance Report；
- Master Plan/ADR/README capability 真实性更新；
- 清理 stale Draft/old gate wording。

### 可选、不阻塞

显式用户操作的“停止播放后说话”：

```text
user interrupt
-> cancel current playback and wait closed
-> abort current response
-> allocate new capture
```

不允许播放和 microphone capture 默认重叠。Acoustic/full-duplex barge-in 延后 Gate 6。

### 退出条件

- 累计 Gate 1.7～4.4 全绿；
- Real playback 与 Real two-turn 都有当前 HEAD 证据；
- disable/shutdown 后 playback/capture/transport/assistant task 全归零；
- 文档不声称未实现的 full-duplex barge-in/AEC/KWS/MCP；
- Gate 4 最终报告给出实际 commit、命令、计数、环境与限制。

## 7. 交付包约定

每个子 Gate 的 AI 交付至少包含：

- 保留相对路径的增量覆盖包；
- 修改/新增/删除文件清单；
- Spec/Report 更新；
- 实际执行命令和结果；
- 未执行或环境阻塞项；
- 不包含 `.git`、venv、cache、token、identity、用户配置、日志、Opus/PCM dump；
- 不自动 commit/push，由用户本地验证后提交。

## 8. 估算与顺序

建议按风险而非代码量安排：

| 阶段 | 主要风险 | 建议工作量 |
|---|---|---:|
| 4.0 | 官方云协议/格式未知 | 0.5～1 日 |
| 4.1 | queue/drain/generation 正确性 | 1～2 日 |
| 4.2 | Windows/PyAudio/PyAV 真实设备 | 1～2 日 |
| 4.3 | 自动续轮并发与真实两轮 | 1～1.5 日 |
| 4.4 | 异常矩阵、文档与收口 | 0.5～1 日 |

这是工程估算，不是完成承诺。Gate 4.0 结果可能改变 4.1/4.2 的实现细节。



## 9. Gate 4.4 最终收口实现

Gate 4.4 不新增全双工插话。现有 `StopStreamingConversation` effect 已在执行会话停止前同步取消 playback coordinator，本阶段将该顺序冻结为自动测试和 Windows Real stop runner。

最终新增：

```text
pc-app-build/tests/gate4_4/
pc-app-build/tools/verify_gate4_4_cumulative.py
pc-app-build/tools/verify_gate4_4_real_stop_during_playback.py
pc-app-build/docs/spec/gate4/GATE4_FINAL_FREEZE.md
pc-app-build/docs/report/GATE4_FINAL_ACCEPTANCE_REPORT.md
pc-app-build/docs/adr/ADR-008-gate4-playback-and-auto-next-turn.md
```

4.4 退出条件：

- cumulative verifier 返回 0；
- stop-during-playback Real runner 返回 0；
- 用户 stop 不产生 natural PlaybackEnded，不增加 auto-next request；
- output、playback worker、PCM buffer、capture、uplink、VAD 与 assistant task 终态归零；
- README、Master Plan、ADR 和 Gate 4 文档只声明已验证能力；
- MCP、KWS、AEC 与 full-duplex barge-in 明确留在后续 Gate。

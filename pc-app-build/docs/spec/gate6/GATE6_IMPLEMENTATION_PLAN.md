# Gate 6 Implementation Plan

状态：Frozen  
阶段数：5（6.0～6.4）  
原则：每阶段必须可独立覆盖、回滚、验收；不得把全部音频风险留到 6.4。

当前进度（2026-07-20）：Gate 6.0 `Accepted-Windows`，Gate 6.1 已完成；Gate 6.2 代码、Automated/Fake 与 Windows 修正版已交付，等待修正版 Windows cumulative/Real 回填；Gate 6.3～6.4 未开始；macOS evidence deferred。

## 1. 共同规则

每个阶段交付：

- production code；
- framework-neutral unit/integration tests；
- Fake runner；
- Windows Real runner（涉及真实设备时）；
-当前阶段 cumulative verifier；
- Implementation Report；
- Overlay Manifest；
- 更新后的 Spec/ADR（若真实证据改变冻结值）。

每个 verifier 至少执行：

```text
compileall
Black --check
Ruff
pytest -W error tests
Gate 1 through current Gate cumulative verifiers
QML smoke
current Fake runner
exit-code propagation / fail-fast
```

Real runner 必须交互式明确提示，不自动声称用户听感或设备行为通过。

## 2. Gate 6.0 — Cross-platform Probe and Contract Freeze

### 目标

在修改生产音频拓扑前，用隔离 probe 回答 backend、设备、时钟、打包和 KWS 可行性问题。

### 实施

新增建议入口：

```text
tools/probe_gate6_audio_devices.py
tools/probe_gate6_duplex.py
tools/probe_gate6_aec.py
tools/probe_gate6_kws.py
tools/verify_gate6_0_fake_probe.py
VERIFY_GATE6_0.ps1
```

probe 要求：

- 列出 input/output 和 host API；
- 显式选择 system default 或参数指定设备；
- 探测支持格式、callback timing、reported latency；
- 同时 capture/render 并记录有界 queue；
- 比较 WebRTC APM 与 OS backend capability；
- far-end-only：只播测试语音，用户保持安静；
- double-talk：播放期间用户说固定短句；
- KWS candidate：模型加载、实时 microphone、CPU/RSS、hit/cooldown；
- 默认不写 PCM；
- 输出脱敏 JSON；
- 退出后 stream/thread/task/lease 全零。

Windows 必须真实执行。macOS 若当前无设备，只能记录 `pending_real_macos`，不能伪造结果。

### 交付决策

- Windows default AEC backend；
- macOS target backend；
- backend fallback；
- internal DSP block size；
- supported capture/render formats；
- delay/drift strategy；
- KWS engine/model candidate；
- packaging dependencies；
- PC barge-in VAD 初始 profile；
- numerical queue/watchdog budgets。

这些值写入 `GATE6_0_IMPLEMENTATION_REPORT.md` 和 ADR-010 addendum 后，6.1 才可开始。

### 明确不做

- 不改变现有产品 capture/playback 默认行为；
- 不增加用户设置；
- 不宣称正式 AEC/KWS/barge-in capability active。

### 退出条件

- Fake probe contract 全绿；
- Windows device/duplex/AEC/KWS probe 有真实脱敏结果；
- backend failure 能安全退出；
- 没有 PCM/model dump 进入覆盖包；
- ADR/spec 数值已按真实证据修订；
- 资源终态全零。

## 3. Gate 6.1 — Device Registry, Route Handling and Duplex Foundation

### 目标

把当前独立 capture/output adapter 收口到一个可跨平台的 `AudioSessionSupervisor`，但不启用产品 barge-in。

### 实施

- `AudioDeviceRegistryPort` + Windows concrete adapter + macOS boundary；
- `AudioRouteObserverPort`；
- device descriptor、preference、resolved route 和 route generation；
- `DuplexAudioSessionPort`；
- render-reference bounded queue；
- owner-aware microphone lease；
- capture/playback/processing 正交 state；
- existing PTT/streaming/playback 通过 supervisor compatibility route；
- route change、device-dead、permission/interruption event；
-小型“语音与设备”sheet：input/output、system default、refresh、mic test；
- Developer Diagnostics：route/backend availability/format/counters。

### 迁移规则

- 现有 Gate 3 `AssistantAudioEngine` 可以作为 uplink worker 复用；
- 现有 Gate 4 `PlaybackCoordinator/PyAudioOutputAdapter` 可以包装进 supervisor；
- 不同时保留两套产品 owner；
- migration 完成后 bootstrap 只创建一个 supervisor；
- `AssistantAudioStatus` 只保留投影，测试转向正交 state。

### Real 场景

- system default input/output；
- user pinned input/output；
- pinned device missing -> visible fallback；
- default change while idle；
- device removal during capture；
- device removal during playback；
- USB/headset available 时至少做一次切换；
-重复 refresh/selection 不泄漏 stream。

### 退出条件

- Gate 3/4 Real 行为不回退；
- 默认仍不重叠 capture/playback；
- explicit duplex probe 可同时获得 capture/render/reference；
- route generation 正确拒绝 stale callback；
- UI 不展示完整设备 ID 或 DSP 参数；
- terminal matrix 全零。

## 4. Gate 6.2 — Offline KWS and Owner Handoff

实施状态：代码与 Automated/Fake 已交付；Windows Real 待本地运行并回填报告。

### 目标

在 idle 状态以本地 KWS 唤醒一次 streaming session，并验证长期麦克风所有权、设备恢复和模型打包。

### 实施

- `KeywordSpotterPort` 与 selected concrete adapter；
- model/config registry；
- KWS generation、worker、bounded audio queue；
- `WAKEWORD_KWS` lease；
- KWS -> AssistantCapture 原子 handoff；
- debounce、cooldown、duplicate hit rejection；
- model missing/invalid/native import failure；
- session terminal 后 exactly-once resume；
- 设置 sheet 增加 KWS 开关和 wake phrase/model summary；
- default-off；
- 本地处理，不向服务器持续上传 idle PCM。

### KWS 运行边界

KWS 在以下状态暂停：

- PTT/capture；
- streaming session；
- thinking/speaking；
- playback；
- barge-in monitor；
- route interrupted；
- permission unavailable；
- disabled/shutdown。

KWS 不作为播放期 interruption detector。

### Real 场景

- 多次正确唤醒；
- 背景语音/媒体负样本；
- cooldown 内重复短语；
- wake hit 与 button start 同时；
- wake hit 后 disconnect；
- model missing；
- mic device/default change；
- session stop 后 KWS 恢复一次；
- disable 后不恢复。

### 退出条件

- 一个 hit 最多建立一个 session；
- KWS 不抢 PTT/streaming 麦克风；
- session 中 KWS stream/worker 为零；
- 模型错误不影响手工语音模式；
- package smoke 可加载模型；
- terminal matrix 全零。

## 5. Gate 6.3 — AEC/NS Processing

### 目标

建立可验证的 processed microphone path，并证明播放期 far-end-only 不会被轻易判成近端语音；本阶段不执行真实 barge-in。

### 实施

- concrete `AudioProcessingPort`；
- capture/render format conversion；
- timestamp/delay/drift feed；
- render/capture bounded queues；
- AEC warmup/ready/degraded/failed state；
- conservative NS；
- AGC capability/report，产品保持 disabled；
- processed PCM VAD probe；
- far-end-only/double-talk runner；
- processing metrics；
- failure/watchdog/overflow；
- raw mic fallback prohibition tests。

### VAD profile freeze

6.0 的候选 threshold 必须用 6.3 真实结果修订。不能复制 Android 650 ms/8 frames/peak/RMS 常量，也不能只在一台设备一次成功后宣称普适。

至少分开：

```text
streaming_vad_profile
barge_in_vad_profile
```

### Real 场景

- TTS-only、用户安静；
- TTS + 用户近距离说话；
- TTS + 用户较远说话；
- 低/中/高系统音量；
- input/output device 变化；
- backend unavailable；
- processing overflow；
- delay jump/route generation invalidation。

### 退出条件

- processed path ready 可解释；
- far-end-only 不上传、不触发产品 barge-in；
- double-talk 可被 VAD 观察；
- AEC failure 不退化为 raw-mic product monitor；
- NS/AGC effective state 可诊断；
- Gate 3/4 音频听感和协议不回退；
- terminal matrix 全零。

## 6. Gate 6.4 — Acoustic Barge-in and Final Closeout

### 目标

将 6.3 processed monitor 接入现有 streaming/Playback state machine，实现可靠任意自然语言插话，并完成设置与累计验收。

### 实施

- `BARGE_IN_MONITOR` owner；
- playback start/terminal 驱动 monitor start/stop；
- processed-only strict VAD；
- bounded in-memory pre-roll；
- `AcousticBargeInCandidate/Confirmed/Failed` event；
- playback generation invalidation；
- local cancel + existing sender abort；
- old TTS JSON/binary rejection；
- monitor -> capture 原子 promote；
- exactly-one uplink worker；
- KWS/session/route recovery integration；
- 设置 sheet 增加“允许播放时插话”；
- capability unavailable reason；
- Windows final acceptance；
- macOS runner/spec and pending/real signoff。

### Race matrix

至少实现：

```text
barge-in vs natural PlaybackEnded
barge-in vs user stop
barge-in vs mode switch
barge-in vs disconnect
barge-in vs disable
barge-in vs shutdown
barge-in vs route change
barge-in vs processing failure
duplicate confirmed event
late old TTS/binary/callback
```

### 退出条件

- TTS-only 不自打断；
- 用户真实插话能停止本地 TTS 并进入新上行；
- monitor 帧在确认前零上传；
- cancel 不产生 natural `PlaybackEnded`；
- Gate 4 auto-next 不重复；
- pre-roll 不包含旧 TTS 原始 reference；
- KWS 不参与插话且最终只恢复一次；
- Windows cumulative 全绿后标记 `Accepted-Windows`；
- 真实 Mac 全矩阵通过后才标记 `Accepted-CrossPlatform`。

## 7. Delivery packaging

每个阶段覆盖包：

```text
note-assistant-app-gate6_X-delivery.zip
```

根目录必须是可直接覆盖仓库根的内容布局，不额外包一层随机目录。排除：

```text
.git/
venv/
__pycache__/
.pytest_cache/
models downloaded at runtime
raw PCM/Opus/reference dumps
real identity/config/token/logs
```

manifest 必须列出基线 commit、changed production/tests/docs、验证状态和真实环境限制。未执行 Windows/macOS Real 时必须明确写 pending，不能用 local Fake 代替。

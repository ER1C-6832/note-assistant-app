# ADR-010: Gate 6 Cross-Platform Audio Session and Processing Boundary

状态：Accepted  
适用范围：Gate 6.0～6.4  
基线：`2bd25c3677cf2aecd2784d089e8f971c40bb377e`

## Context

Gate 4 的 capture 和 playback 是默认互斥的独立 PyAudio 路径。声学 barge-in 需要 playback 期间持续捕获麦克风、取得与实际 output 对齐的 render reference，并在不上传回声的前提下运行 AEC/NS/VAD。

Android 已验证系统 AEC/NS、AGC-off、严格 VAD 和上行门控组合，但 Windows/macOS 的设备、路由、时钟和系统 API 不同，不能把 Android implementation 当成 PC backend。

## Decision

1. 在 Controller 之下新增唯一 `AudioSessionSupervisor`，统一拥有设备、route generation、capture、playback、duplex monitor、processing、KWS 和关闭顺序。
2. Core 只依赖 `AudioDeviceRegistryPort`、`AudioRouteObserverPort`、`DuplexAudioSessionPort`、`AudioProcessingPort` 和 `KeywordSpotterPort`。
3. Gate 6.0 通过真实 probe 比较 WebRTC APM 与 Windows/macOS OS backend；ADR 不提前选择 concrete AEC backend。
4. `MicrophoneLeaseCoordinator` 升级为 owner-aware lease，支持 `NONE`、`WAKEWORD_KWS`、`ASSISTANT_CAPTURE`、`BARGE_IN_MONITOR` 和 generation-safe 原子转移。
5. capture/playback/processing 使用正交子状态；旧 `AssistantAudioStatus` 只作为 UI compatibility projection，不再是双工事实的唯一来源。
6. raw PCM、render reference、native frame 和 DSP object 不进入 AssistantState、QML 或 Runtime event queue。
7. KWS idle-only，不能作为 TTS barge-in detector。
8. speaker-route acoustic barge-in 只在 processed path ready 时可用；不可用时 fail closed。
9. AEC/NS automatic，AGC default-off。普通用户不获得 DSP 微调开关。
10. 保持单 Python 进程；native callback/DSP thread 可用，但必须有唯一 owner、有界队列和终态验收。

## Consequences

正面：

- Windows/macOS backend 可替换；
- KWS、AEC 和 barge-in 共用一个音频所有权模型；
- 设备切换与 interruption 不再散落在 capture/playback adapter；
- 可保持 Gate 4 `PlaybackEnded` 与 Gate 5 MCP 语义不变。

代价：

- Gate 6.1 需要重构 AudioState 和 lease，而不是只添加一个 VAD 开关；
- 需要真实 Windows/macOS 设备证据；
- AEC 构建、动态库和签名可能增加打包复杂度；
- Bluetooth 和独立时钟设备必须按 route generation 处理。

## Rejected alternatives

### 播放时直接开启现有 Energy VAD

拒绝。raw mic 无法区分 TTS 与用户语音，容易自打断。

### 直接复制 Android AudioEffect 和阈值

拒绝。Android session、设备几何和 vendor processing 不适用于 PC。

### KWS 同时承担插话检测

拒绝。唤醒词与任意自然语言插话目标不同，并会让 TTS 包含唤醒词时自触发。

### AEC sidecar 或第二音频进程

拒绝。破坏单进程 Runtime、生命周期与资源验收。


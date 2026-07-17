# Gate 6 Android Reference Audit

状态：Frozen reference audit  
参考仓库：`ER1C-6832/note-assistant-android@974a477ce1803efa130cc8b51a493b39796e0ca7`

## 1. 审阅结论

Android 端的插话很少打断自己，不是单一 VAD 参数的结果，而是以下组合：

```text
VOICE_COMMUNICATION capture source
+ platform AcousticEchoCanceler
+ platform NoiseSuppressor
+ AGC disabled
+ playback-only monitor, no uplink
+ stricter dynamic VAD
+ warmup and consecutive-frame confirmation
+ abort/listen state isolation
```

PC Gate 6 应复用该设计原则，但不得复制平台绑定代码和固定阈值。

## 2. Android 已验证实现事实

### 2.1 Capture processing

`AndroidAudioRecorder`：

- 按 `VOICE_COMMUNICATION -> VOICE_RECOGNITION -> MIC` 尝试录音源；
- AEC request 默认 `true`；
- NS request 默认 `true`；
- AGC request 默认 `false`；
- effect 与 `AudioRecord.audioSessionId` 绑定；
- availability、enabled 和 source 进入脱敏 processing report；
- effect 与 AudioRecord 同生命周期 release。

### 2.2 Barge-in monitor

`RealAudioEngine`：

- TTS 播放期允许 capture/VAD 继续运行；
- `suppressUplinkDuringPlayback=true` 时不编码/上传 playback monitor 帧；
- speech 未确认前保留有界 pre-speech packet buffer；
- 插话确认后停止旧播放、发送 abort、进入同一 streaming session 新回合；
- KWS 在 streaming session 中暂停。

### 2.3 Conservative VAD

Android barge-in profile 使用：

```text
warmup                 650 ms
minimum speech         8 x 20 ms frames
speech peak threshold  1800
speech RMS threshold   380
trailing silence       1200 ms
```

并结合 noise-floor EMA 形成动态阈值。这些数值只证明 Android 当前产品策略，不是 PC 冻结常量。

### 2.4 System recovery

Android 后续稳定性实现还包括：

- audio focus 协调；
- Bluetooth/wired route removal；
- runtime microphone permission watchdog；
- KWS read failure bounded retry；
- wake-word debounce；
- interruption 后不自动重放旧回合；
- 系统安全后只恢复一次 KWS。

## 3. PC 不得照搬的原因

| Android 条件 | Windows/macOS 差异 | Gate 6 对策 |
|---|---|---|
| 手机扬声器和麦克风几何结构固定 | PC 可能使用内置、显示器、USB、扩展坞或 Bluetooth 任意组合 | 引入 device registry、route generation 和明确 input/output pairing |
| AudioEffect 按 AudioRecord session 绑定 | PyAudio/PortAudio 没有同等跨平台 AEC session 抽象 | 增加 `AudioProcessingPort`，比较 WebRTC APM 与 OS backend |
| 单一系统音频路由较受控 | Windows 默认设备、通信设备和应用输出可能不同 | pinned/default 语义、route observer、reference output 校验 |
| 平台可能自动提供 vendor AEC | Windows endpoint AEC 支持依设备/系统；macOS 使用不同 voice-processing API | backend capability probe，不按平台名称假定可用 |
| input/output 通常共享设备时钟 | USB mic 与 HDMI/display output 可能是独立时钟 | delay/drift/timebase 探测与有界补偿 |
| 固定 20 ms VAD 参数已真机调优 | PC 设备电平、增益和房间差异大 | 6.0/6.3 真实样本后冻结 PC profile |
| 移动端设置页已经存在 | PC 当前没有完整设置中心 | 使用小型“语音与设备”sheet，不扩建完整设置系统 |

## 4. 必须复用的行为原则

- AEC 与 VAD 是串联关系，不是二选一；
- NS 只辅助环境噪声，不代替 AEC；
- AGC 默认关闭；
- 播放期 monitor 帧不上传；
- KWS 与 barge-in 是不同 detector；
- 插话默认关闭并由用户启用；
- 插话成立前使用有界内存 pre-roll；
- 插话取消旧 playback generation，不产生 natural `PlaybackEnded`；
- 迟到旧回复必须按 generation/session 丢弃；
- interruption 不重放旧 turn；
- KWS 恢复必须 exactly once。

## 5. 不复用的实现细节

- Android `AudioRecord` / `AudioTrack` / `AudioEffect` 类；
- `VOICE_COMMUNICATION` source 常量；
- 650 ms、1800、380、8 帧等固定阈值；
- Android audio focus、SCO/A2DP 事件类型；
- Android foreground service 和权限 watchdog 实现；
- Android 单设备 session id 作为跨平台 identity。

## 6. PC 首版策略

```text
AEC  automatic; speaker-route barge-in requires ready processed path
NS   automatic and conservative
AGC  off; probe/diagnostics only
VAD  separate streaming and barge-in profiles
KWS  idle-only; paused during active voice session and TTS
```

若 AEC/backend 不可用，PC 不得静默退化为 raw-mic playback VAD。UI 应显示声学插话不可用，手工 stop/PTT/连续模式继续可用。


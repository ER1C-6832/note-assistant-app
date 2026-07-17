# Gate 6 Audio Device, KWS, AEC/NS and Acoustic Barge-in Specification

状态：Frozen for implementation  
基线：`note-assistant-app@2bd25c3677cf2aecd2784d089e8f971c40bb377e`  
范围：Gate 6.0～6.4

## 1. 目标

在不破坏 Gate 2～5 已验收语义的前提下，建立 Windows 当前可交付、macOS 可真实落地的统一音频会话边界，并完成：

- input/output 设备枚举、选择、持久化、默认回退和 route change；
- playback/capture 同时运行所需的 duplex monitor；
- 离线 KWS 与安全麦克风所有权交接；
- AEC/NS processed microphone path；
- 播放期间任意自然语言声学插话；
- system interruption、hotplug、Bluetooth 和权限失败的有界恢复；
- 小型“语音与设备”设置面板；
- Windows/macOS 分级真实签字。

## 2. 非目标

Gate 6 不实现：

- 自建 Xiaozhi server；
- 本地 ASR/TTS/LLM；
- Electron 集成；
- 多进程音频 sidecar；
- 自行训练生产 KWS 模型；
- 普通用户可调的 AEC/NS/AGC 参数面板；
- 远场阵列波束成形；
- 用 KWS 代替任意自然语言 barge-in；
- Gate 7 的 p50/p95/长期性能声明。

## 3. Gate 4/5 兼容契约

以下规则不可回退：

1. natural `PlaybackEnded` 仍是连续模式正常自动下一轮的唯一来源；
2. playback cancel/failure/barge-in 不产生 natural `PlaybackEnded`；
3. stop、mode switch、disconnect、disable、shutdown 优先于续轮；
4. stale connection/playback/capture/route generation callback no-op；
5. WebSocket receiver 不等待 decode、device、AEC、KWS 或 physical drain；
6. 原始 Opus/PCM 不进入 Runtime event queue 或 AssistantState；
7. Gate 5 32-tool registry、schema、风险和确认语义不变；
8. 不新增第二 sender、第二 Controller、第二 Runtime 或第二 Python 进程。

## 4. 为什么 PC 不能复制 Android

Android 的系统 `AudioEffect` 能按一个 `AudioRecord` session 绑定 AEC/NS，手机内置扬声器与麦克风位置也较固定。PC 可能同时使用 USB 麦克风、HDMI 显示器扬声器、扩展坞、AirPods 或系统默认设备，input/output 还可能来自独立时钟。

因此 PC 必须显式拥有：

```text
selected input endpoint
selected output endpoint
route generation
capture/render timestamps
render reference
delay/drift handling
processing backend capability
```

Android 的状态门控和安全原则可复用；Android API、session id 和 threshold 不复用。

## 5. 音频处理含义与默认策略

### 5.1 AEC

AEC 使用 output render reference 从 captured microphone 中消除扬声器回授。它是 speaker-route acoustic barge-in 的必要 processed path。

### 5.2 NS

NS 抑制环境噪声，改善 VAD/KWS/ASR，但不能代替 AEC 去除清晰 TTS。

### 5.3 AGC

AGC 改变采集增益，可能同时放大近端小声、底噪和残余回声。Gate 6 只探测 capability 和处理报告，首版产品默认关闭；AGC 不得成为 Gate 6 完成依赖。

### 5.4 冻结顺序

```text
render PCM -------------------------+
                                    v
raw mic PCM -> delay/drift align -> AEC -> conservative NS -> optional AGC(off)
                                                       -> VAD / KWS / Opus
```

具体 backend 可以内部调整 block 顺序，但必须在 diagnostics 中报告有效配置。

## 6. Backend 决策规则

Gate 6.0 必须比较：

- WebRTC Audio Processing Module；
- Windows endpoint/system AEC 能力；
- macOS voice-processing 能力；
- bypass/no-AEC 行为。

比较维度：

```text
Windows availability and packaging
macOS availability and packaging
input/output format support
required frame size
render/capture delay API
clock drift behavior
CPU/RSS
native thread lifecycle
license and redistribution
failure visibility
```

不得只因 import/create 成功就声明 AEC ready。至少需要 far-end-only 和 double-talk 真实证据。

最终 concrete backend 通过 Gate 6.0 report + 新 ADR/ADR-010 addendum 冻结。若 Windows/macOS 需要不同 backend，必须位于同一 `AudioProcessingPort` 后方。

## 7. AudioSessionSupervisor

新增唯一 application-scoped `AudioSessionSupervisor`，拥有：

- `AudioDeviceRegistryPort`；
- `AudioRouteObserverPort`；
- physical capture/output/duplex session；
- microphone lease；
- render-reference queue；
- processing worker；
- KWS worker；
- device/route generation；
- bounded stop/close；
- coarse diagnostics event sink。

Controller 通过 Effects 驱动 supervisor，不直接持有 native stream。QML/ViewModel 不持有设备、stream、model 或 DSP object。

## 8. Ports

角色冻结，名称可按代码风格微调但不得合并职责：

```python
class AudioDeviceRegistryPort(Protocol):
    def snapshot(self) -> AudioDeviceSnapshot: ...
    def resolve(self, preference: DevicePreference) -> ResolvedAudioRoute: ...

class AudioRouteObserverPort(Protocol):
    def start(self, sink: RouteEventSink) -> None: ...
    def stop(self) -> None: ...

class DuplexAudioSessionPort(Protocol):
    def open(self, plan: DuplexAudioPlan, callbacks: DuplexCallbacks) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...

class AudioProcessingPort(Protocol):
    def process_render(self, frame: TimedPcmFrame) -> None: ...
    def process_capture(self, frame: TimedPcmFrame) -> ProcessedPcmFrame: ...
    def metrics(self) -> AudioProcessingMetrics: ...
    def close(self) -> None: ...

class KeywordSpotterPort(Protocol):
    def accept(self, frame: ProcessedPcmFrame) -> KeywordSpotResult | None: ...
    def reset(self, generation: int) -> None: ...
    def close(self) -> None: ...
```

Fake implementations必须不打开真实设备。

## 9. Device identity and selection

### 9.1 Model

`AudioDeviceDescriptor` 至少包含：

```text
opaque_device_id
public_name
platform
host_api
input/output capability
default flags
supported public formats
availability
route_class if reliably known
```

完整 endpoint GUID/UID 不进入普通日志或 UI，可持久化为私有 preference key。PortAudio index 不得被当成跨重启稳定 identity。

### 9.2 Preference

每个方向支持：

```text
follow_system_default
pin_specific_device
```

选择策略：

1. pinned 且可用：使用 pinned；
2. pinned 不可用：fail visible，并按用户策略临时回退 system default；
3. follow default：使用当前系统默认；
4. 无可用设备：audio unavailable，不选择任意列表第一项。

临时回退不得覆盖用户的 pinned preference。

### 9.3 Route generation

以下任一变化递增 `route_generation`：

- selected endpoint 改变；
- default endpoint 改变且 preference 跟随 default；
- device removal/reappearance；
- Bluetooth profile/format 改变；
- device-dead/native invalidation；
- permission/audio-service restart 导致 session 重建。

旧 route generation 的 frame、callback、timer、drain、KWS hit 和 processing result 全部 no-op。

## 10. State model

Gate 6 将音频事实拆成正交状态：

```text
capture_activity   inactive | kws | assistant | barge_in_monitor
playback_activity  inactive | buffering | playing | draining | cancelling
processing_state   bypass | warming | ready | degraded | failed
route_state        unavailable | resolving | ready | interrupted
```

旧 `AssistantAudioStatus` 只保留为 UI projection，不能再用 `RECORDING/PLAYING` 互斥表达全部事实。

新增/扩展 state 只记录：

- generations；
- enum/bool；
-公开设备名称和 capability；
- counts、timings、overflow/underflow；
- backend public name；
- error code/redacted summary。

不得记录 PCM、模型 tensor、native handle、完整设备 ID 或用户音频。

## 11. Microphone ownership

`MicrophoneLeaseCoordinator` 必须升级为 owner-aware：

```text
NONE
WAKEWORD_KWS
ASSISTANT_CAPTURE
BARGE_IN_MONITOR
```

租约键：

```text
owner + lease_generation + route_generation
```

允许的原子转移：

```text
WAKEWORD_KWS -> ASSISTANT_CAPTURE
BARGE_IN_MONITOR -> ASSISTANT_CAPTURE
ASSISTANT_CAPTURE -> WAKEWORD_KWS  only after session terminal
any owner -> NONE                 on stop/disable/interruption/shutdown
```

禁止两个 owner 同时 active。physical stream 是否复用由 adapter 决定，但逻辑转移必须 exactly once。

## 12. Callback, queues and threading

- native callback 不 decode、不跑 KWS/AEC 重模型、不写 state、不阻塞；
- callback 只写 bounded ring/queue、消费 output 和记录原子计数；
- render reference 与 capture ingress 都有界；
- processing worker 每个 active audio generation 最多一个；
- KWS worker 每个 KWS generation 最多一个；
- overflow fail visible，不 drop-oldest 后继续声称高质量 AEC；
- Runtime event pump 只接收粗粒度 started/ready/hit/failed/counters/terminal event；
- shutdown 有界 join，超时产生可见 failure，但不得留下非 daemon product worker。

## 13. KWS contract

### 13.1 Initial candidate

Gate 6.0 首先 probe sherpa-onnx open-vocabulary KWS；它不是 Core 依赖，最终实现位于 `KeywordSpotterPort` 后。

### 13.2 Activation

KWS 只有同时满足以下条件才可运行：

```text
assistant enabled
KWS user preference enabled
microphone permission available
no assistant capture
no barge-in monitor
no active streaming/PTT turn
no active playback
route ready
model ready
```

### 13.3 Wake hit

```text
KeywordDetected(current generation)
-> debounce/cooldown check
-> stop KWS and await lease release
-> atomically acquire ASSISTANT_CAPTURE
-> connect/reuse transport
-> start exactly one streaming session
```

重复或迟到 hit no-op。KWS model missing/invalid 不影响 PTT、button streaming、playback 或 MCP。

### 13.4 Resume

只有活动 voice session terminal、playback inactive、route ready 且 preference 仍开启时恢复 KWS。多个 terminal/recovery callback 只能恢复一次。

## 14. AEC/NS/AGC contract

### 14.1 Render reference

reference 必须代表实际提交给 output device callback 的 PCM，包括 format conversion 后的 channel/rate 和实际提交的 silence padding；不得使用 TTS text、wire Opus 或 decode 前 packet 作为 reference。

### 14.2 Capture processing

capture frame 携带 monotonic timestamp、route/capture generation 和明确 format。backend 内部可转换为所需 block size，例如 10 ms；转换不改变外部 20 ms protocol contract。

### 14.3 Readiness

`processing_state=ready` 至少意味着：

- backend initialized；
- current input/output route supported；
- render/capture formats planned；
- required warmup complete；
- no current overflow/fatal delay error。

### 14.4 Degradation

- AEC unavailable + speaker playback：acoustic barge-in unavailable；
- NS unavailable：可以继续 AEC/barge-in，但报告 degraded；
- AGC unavailable/disabled：不降级 Gate 能力；
- processing overflow/failure：停止 monitor，不上传 raw fallback，保留手工 stop/PTT。

## 15. Acoustic barge-in contract

### 15.1 Eligibility

只有同时满足以下条件才启动 monitor：

```text
streaming session active
current TTS playback buffering/playing
user barge-in preference enabled
current route ready
processed path ready or warming under a bounded watchdog
no stop/mode switch/disconnect/disable/shutdown
```

### 15.2 Monitor

- owner=`BARGE_IN_MONITOR`；
- capture 与 playback 允许物理重叠；
- VAD 只观察 processed PCM；
- monitor PCM 不编码或上传；
- 使用有界内存 pre-roll；
- 单个 impulse、AEC warmup 和旧 generation 不能触发；
- threshold 数值由 Gate 6.0/6.3 Real evidence 冻结，不复制 Android 常量。

### 15.3 Confirmed sequence

```text
AcousticBargeInConfirmed
-> invalidate current playback generation
-> cancel local playback/clear old ingress
-> send abort(streaming_barge_in) through existing sender
-> reject old TTS JSON/binary by generation
-> suppress natural PlaybackEnded and Gate 4 auto-next
-> atomically promote BARGE_IN_MONITOR to ASSISTANT_CAPTURE
-> start/reuse one uplink worker
-> prepend bounded processed pre-roll
-> continue current streaming session as a new user turn
```

不要求等待服务器 abort ack 后才停止本地扬声器；但 wire ordering 和新 listen/start 必须由当前 endpoint probe/协议契约验证。

### 15.4 Race semantics

- `BargeInConfirmed -> PlaybackEnded`：迟到 PlaybackEnded no-op；
- `PlaybackEnded -> BargeInConfirmed`：若 natural end 已先合法分配 next turn，monitor generation 失效，barge-in event no-op；
- `UserStop -> BargeInConfirmed`：barge-in no-op；
- `BargeInConfirmed -> UserStop`：已分配的新 capture 立即停止且只 finalize 一次；
- disconnect/disable/shutdown 任一先到均使 monitor/capture/playback generation 失效。

## 16. Settings and UI

Gate 6 不新增完整设置中心。现有 UI 增加一个小型“语音与设备”sheet/popover：

### Gate 6.1

- input：系统默认或指定设备；
- output：系统默认或指定设备；
- refresh；
- microphone test；
- 当前 route 和 processing availability 摘要。

### Gate 6.2

- KWS enable；
- wake phrase/model summary；
- model missing/error status。

### Gate 6.4

- acoustic barge-in enable；
- 不可用时禁用 switch 并显示简短原因。

普通 UI 不展示 AEC/NS/AGC 开关。Developer Diagnostics 可展示 backend、AEC/NS/AGC effective state、delay/drift、queue counters 和脱敏设备信息。

## 17. Interruption and recovery

### During idle/KWS

route/permission interruption：停止 KWS、释放 lease、显示 paused；安全恢复后 exactly once 恢复。

### During capture

停止上行、发送必要 abort、invalidate generation、释放设备；不得自动重放或续接旧用户语音。

### During playback/monitor

cancel playback 和 monitor，不产生 natural `PlaybackEnded`，不自动新开麦；transport 可按 Gate 2 policy reconnect，但旧 TTS 不重放。

### Device returns

设备恢复只回到安全 idle/KWS。不得恢复被中断的 capture、playback 或 barge-in turn。

## 18. Bluetooth and multi-device policy

- Bluetooth profile/format change 视为 route generation change；
- route remove/add 不自动重放活动 turn；
- input/output 不在同一 host API 或时钟时，duplex adapter 必须报告能力和 drift；
- 不能建立有效 reference pairing 时，barge-in unavailable；
- KWS 可以在可用 input 上运行，不要求 output/AEC ready；
- 使用 headphones 不能成为跳过 processed-path 验收的隐式假设。

## 19. Metrics and privacy

使用现有 monotonic clock，至少记录：

```text
device resolve/open/start/stop/close
first capture/render frame
processing warmup/ready
render/capture queue peak and overflow
estimated delay/drift when available
far-end-only residual sample
KWS detection/handoff sample
barge candidate/confirmed
playback cancel complete
first post-barge uploaded Opus
terminal cleanup complete
```

单次 Real runner 只报告 sample，不宣称 p95。Gate 7 再做分位数。

默认禁止持久化 PCM、render reference、KWS feature 或模型 tensor。显式 debug dump 必须 opt-in、短时、有自动删除说明，并排除交付包和 Git。

## 20. Packaging

- Windows/macOS native library 和模型均需 license/redistribution audit；
- 不在运行时静默从互联网下载模型；
- model/backend missing 显示 capability unavailable；
- 应用仍为一个 Python 产品进程；
- 不启动 ffmpeg、AEC、KWS sidecar；
- package smoke 必须验证 native import、model load、device probe 和 bounded shutdown。

## 21. Sign-off

### Accepted-Windows

Windows 6.0～6.4 Automated/Fake/Real、设备与异常矩阵、设置、真实 KWS、真实 speaker barge-in、terminal zero 和累计 Gate 1～6 均通过。

### Accepted-CrossPlatform

在 Windows 签字基础上，真实 macOS：

- permission；
- device enumerate/select/default change；
- capture/playback/duplex；
- KWS；
- AEC/NS far-end-only + double-talk；
- acoustic barge-in；
- interruption/hotplug；
- package smoke；
- terminal zero

全部通过。没有真实证据不得用设计兼容或 import 成功代替。


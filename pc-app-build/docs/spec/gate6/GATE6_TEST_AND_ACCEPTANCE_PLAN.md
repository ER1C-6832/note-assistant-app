# Gate 6 Test and Acceptance Plan

状态：Frozen  
适用阶段：6.0～6.4

## 1. 证据等级

| 等级 | 说明 | 可证明内容 |
|---|---|---|
| Static | imports、文件、常量、禁止依赖扫描 | 架构形状，不证明运行质量 |
| Unit | state/reducer/queue/selection/DSP adapter fake | 确定性语义 |
| Fake integration | scripted device/audio/backend/transport | 并发、race、failure、cleanup |
| Offline audio lab | 合成/许可 fixture 的 render+mic | 对齐、AEC/NS、VAD 相对行为 |
| Windows Real | 真实设备、扬声器、麦克风、网络 | 当前产品签字 |
| macOS Real | 真实设备、权限、路由、打包 | 跨平台签字 |
| Human observation | 听感、设备切换、真实说话 | 只能由用户确认 |

Fake/Offline 不得替代 Real；Windows Real 不得替代 macOS Real。

## 2. 每阶段自动入口

建议文件：

```text
VERIFY_GATE6_0.ps1
VERIFY_GATE6_1.ps1
VERIFY_GATE6_2.ps1
VERIFY_GATE6_3.ps1
VERIFY_GATE6_4.ps1
```

每个 verifier 必须 fail-fast 并传播首个非零 exit code，至少执行：

```powershell
python -m compileall apps/notes-pyside/app tests tools
python -m black --check apps/notes-pyside/app tests tools
python -m ruff check apps/notes-pyside/app tests tools
python -m pytest -W error tests
python tools/verify_gate6_X_fake_*.py
```

还必须执行当前仓库已存在的 Gate 1.7、Gate 2.1～2.7、Gate 3、Gate 4、Gate 5 cumulative/freeze runner 与 QML smoke。脚本不得因 runner 文件缺失而静默跳过；显式 interactive Real runner 只有在未传 flag 时可以显示 `SKIPPED_INTERACTIVE`，且不能被计为 Real pass。

## 3. Static architecture tests

至少冻结：

- Core/state/controller 不 import Win32/CoreAudio concrete module；
- QML/ViewModel 不 import/创建 PyAudio、WebRTC、KWS、native model；
- WebSocket transport 不持有 AEC/KWS/device manager；
- 只有一个 `AudioSessionSupervisor` product instance；
- 只有一个 owner-aware microphone lease；
- 无 localhost、Sidecar、multiprocessing/subprocess DSP；
- raw PCM/reference/model tensor 类型不进入 AssistantState/event payload；
- user settings 不包含 AEC/NS/AGC threshold 控件；
- AGC default false；
- acoustic barge-in default false；
- KWS default false；
- Gate 5 frozen tool hash 不变。

## 4. Gate 6.0 tests

### Fake

- device list empty/one/many；
- input-only/output-only/duplex descriptors；
- supported/unsupported format；
- backend available/unavailable/create failure；
- 10 ms/20 ms block adaptation；
- render/capture timestamp ordering；
- queue overflow；
- KWS model missing/invalid/hit；
- probe JSON redaction；
- close idempotency。

### Windows Real

必须分别运行：

```text
device inventory
duplex capture/render
AEC far-end-only
AEC double-talk
KWS live microphone
package/import smoke if packaged build exists
```

报告只记录：公开设备名、format、latency sample、backend、availability、counts、CPU/RSS sample、error code。不得保存用户真实语音或完整 endpoint identity。

### Gate 6.0 pass

- 已选择下一阶段 backend strategy；
- Windows Real 有脱敏证据；
- macOS 无真机时明确 pending；
- terminal resources zero；
- ADR/spec 已按结果更新。

## 5. Gate 6.1 device and duplex tests

### Selection

- follow system default；
- pinned device available；
- pinned missing temporary fallback；
- pinned preference 不被 fallback 覆盖；
- no available input/output fail visible；
- duplicate public names 仍可区分；
- PortAudio index 变化不冒充 stable identity；
- selection refresh exactly once。

### Route generation

- default change；
- device add/remove；
- device-dead；
- Bluetooth/profile/format change fake；
- permission revoke/restore fake；
-旧 callback/frame/timer/drain no-op；
- interrupted turn 不恢复或重放。

### Duplex

- capture and render callbacks concurrent；
- bounded reference/capture queues；
- callback never waits DSP；
- format planner success/failure；
- independent timestamp/drift samples；
- stop/close while callback active；
- duplicate stop/close；
- output failure does not leak capture；
- capture failure does not fake playback end。

### UI

- system default and pinned selection；
- missing-device visible status；
- refresh/test microphone；
- no full/private endpoint ID；
- no DSP expert controls；
- QML smoke without real device。

## 6. Gate 6.2 KWS tests

### Functional

- disabled default；
- enable -> one KWS generation/worker/lease；
- correct keyword -> one hit；
- incorrect/background -> no hit；
- cooldown/debounce；
- duplicate hit same generation；
- stale hit after stop/route change；
- KWS -> AssistantCapture atomic handoff；
- button start racing wake hit；
- PTT/streaming ownership denial；
- session terminal -> exactly-one KWS resume；
- disable before resume -> no resume。

### Failure

- model missing/corrupt；
- native import failure；
- microphone read failure；
- queue overflow；
- device remove；
- permission revoke；
- repeated bounded recovery；
- shutdown during model load/listening/handoff。

### Real checklist

记录一组明确的正样本、负样本和 cooldown 场景，但单次手工样本不得被宣传为统计 FAR/FRR。必须确认：

- 不上传 idle microphone；
- TTS/active session 中 KWS paused；
- 一个唤醒只启动一个 session；
-结束后只恢复一次；
- CPU/RSS/latency 作为 sample 输出。

## 7. Gate 6.3 processing tests

### Offline lab

fixture 至少包含：

- render-only；
- capture silence；
- delayed echo；
- echo + near speech double-talk；
- stationary noise；
- impulse/noise burst；
- rate/channel mismatch；
- delay jump/drift；
- truncated/corrupt frame。

断言：

- correct generation/format；
- bounded alignment；
- processed output frame count/format；
- far-end residual 相对 raw 不恶化；
- near speech 不被全部消除；
- NS effective state；
- AGC disabled；
- overflow/failure visible；
- raw fallback prohibition。

禁止用合成 fixture 宣称真实房间 AEC 已完成。

### Windows Real

至少覆盖：

| 场景 | 用户行为 | 必须观察 |
|---|---|---|
| TTS-only low volume | 保持安静 | processed monitor，不上传、不触发产品插话 |
| TTS-only medium | 保持安静 | 同上 |
| TTS-only high | 保持安静 | 同上；失败则 capability degraded/fail closed |
| double-talk near | 播放中说话 | processed VAD 能观察近端语音 |
| double-talk farther | 播放中说话 | 记录样本，不伪造统计结论 |
| route change | 播放/监听中切设备 | generation invalidation、无旧 callback |
| backend unavailable | 强制或真实不可用 | 无 raw-mic product barge-in |

6.3 runner 不执行真实 abort/listen 新回合，只验证 processed path。

## 8. Gate 6.4 acoustic barge-in tests

### State/effect ordering

必须覆盖所有排列：

```text
Confirmed -> PlaybackEnded
PlaybackEnded -> Confirmed
Stop -> Confirmed
Confirmed -> Stop
Disconnect -> Confirmed
Confirmed -> Disconnect
Disable -> Confirmed
Confirmed -> Disable
Shutdown -> Confirmed
Confirmed -> Shutdown
RouteChanged -> Confirmed
ProcessingFailed -> Confirmed
duplicate Confirmed
late old TTS JSON/binary/drain/VAD
```

断言：

- finalize once；
- abort at most once；
- playback cancel at most once；
- no natural `PlaybackEnded` from cancel；
- no Gate 4 auto-next duplication；
- monitor -> capture at most once；
- uplink worker at most one；
- stale event no-op。

### Upload gate

- playback monitor 帧零上传；
- candidate 未 confirmed 时零上传；
- confirmed 后只上传 processed pre-roll + new near speech；
- render reference 不进入 uplink；
- failure 不退化成 raw upload。

### Windows Real checklist

- TTS-only 不说话；
- TTS 开头说话；
- TTS 中间说话；
- TTS 接近结束说话；
- 短噪声/敲击不插话；
- 正常用户插话停止本地 TTS；
- 新命令 STT/assistant response 可读；
- 用户 stop、disconnect、device removal；
- KWS 启动的 session 插话后来源保持；
- button 启动的 session 来源保持；
- session 结束 KWS 恢复一次。

用户必须人工确认扬声器是否停止、首字是否明显丢失、是否自打断和新回复是否正确。

## 9. Cross-platform matrix

### Windows `Accepted-Windows`

至少：

- system default Realtek/当前内置 route；
- 可用时一个 USB/有线/Bluetooth route；
- device selection/default change；
- KWS；
- AEC far-end-only/double-talk；
- real acoustic barge-in；
- interruption/terminal matrix；
- packaged smoke（若项目当前已有打包入口）。

### macOS `Accepted-CrossPlatform`

必须真实运行：

- microphone permission grant/deny/revoke；
- default and selected input/output；
- device add/remove/default change；
- capture/playback/duplex；
- selected AEC/voice-processing backend；
- KWS model/native packaging；
- far-end-only/double-talk；
- acoustic barge-in；
- sleep/wake or available interruption scenario；
- final terminal matrix。

仅有代码分支、CI import 或 fake adapter 时，状态保持 `Pending macOS Real Evidence`。

## 10. Terminal resource matrix

每个 stop、error、disconnect、disable、shutdown 和 device interruption 最终必须满足：

```text
reconnect timer                 0
streaming response timer        0
playback watchdog               0
KWS retry/cooldown timer         0
route debounce timer             0
audio uplink task               0
capture stream                  0
output stream                   0
duplex session                  0
render-reference queue/items    0
capture ingress queue/items     0
processed queue/items           0
audio worker                    0
processing worker               0
KWS worker/model stream         0
route observer                  0
microphone lease                NONE
playback coordinator active     0
transport sender/receiver       0 after shutdown
MCP worker/in-flight task        0 after shutdown
second Python process           0
```

资源项不可只靠 state bool 声明，runner 应读取对应 owner/worker/stream 的实际 diagnostics。

## 11. Privacy and report rules

报告禁止包含：

- raw PCM/Opus/reference；
-完整 transcript/用户便签正文；
- token/authorization；
-完整 device/client/session identity；
-私有 endpoint GUID/UID；
-模型内部 tensor。

允许：

- public device name；
- format/rate/channels；
- counts/latency/CPU/RSS sample；
- backend/effective AEC/NS/AGC；
- masked identity；
- error code/redacted message；
-人工 `pass/fail/not-run`。

## 12. Final sign-off report

`GATE6_FINAL_ACCEPTANCE_REPORT.md` 必须分别列出：

```text
Windows status
macOS status
backend decisions
device matrix
KWS evidence
AEC/NS evidence
barge-in evidence
terminal matrix
known limitations
exact commit
```

允许 `Accepted-Windows / Pending macOS Real Evidence`，不允许模糊写“跨平台设计完成”来代替平台状态。


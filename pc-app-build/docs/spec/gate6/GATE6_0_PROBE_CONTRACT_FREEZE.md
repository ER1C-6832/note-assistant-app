# Gate 6.0 Probe Contract Freeze

状态：Implemented — Pending Windows Real Evidence  
基线：`19953b12d15ad5e76dfd4da0ca3dfa9aa353dec8`  
范围：只冻结跨平台端口、公开数据模型、探测工具和数值候选；不改变现有产品音频拓扑。

## 1. 冻结边界

Gate 6.0 新增四个框架无关模块：

```text
assistant/audio/gate6_contracts.py
assistant/audio/gate6_probe.py
assistant/audio/gate6_pyaudio_probe.py
assistant/audio/gate6_backend_probe.py
```

`gate6_contracts.py` 不导入 PySide、PyAudio、Win32/CoreAudio、AEC/KWS runtime 或应用 State。冻结端口：

```text
AudioDeviceRegistryPort
AudioRouteObserverPort
DuplexAudioSessionPort
AudioProcessingPort
KeywordSpotterPort
```

冻结正交状态：

```text
capture_activity   inactive | kws | assistant | barge_in_monitor
playback_activity  inactive | buffering | playing | draining | cancelling
processing_state   bypass | warming | ready | degraded | failed
route_state        unavailable | resolving | ready | interrupted
```

冻结麦克风 owner：

```text
NONE
WAKEWORD_KWS
ASSISTANT_CAPTURE
BARGE_IN_MONITOR
```

本阶段不替换现有 `MicrophoneLeaseCoordinator`，owner-aware 产品迁移属于 Gate 6.1/6.2。

## 2. Probe 隐私契约

所有入口默认：

- 不写 PCM、Opus、render reference 或模型 tensor；
- 不写完整 endpoint GUID/UID；
- 设备只输出公开名称、Host API、能力、格式、延迟和不可逆短摘要；
- 不输出 Token、Authorization、完整 session/device identity；
- JSON 最大 64 KiB；
- 原生异常只输出类型和稳定 error code；
- real probe 结束后 stream/thread/queue/lease 必须归零。

## 3. 数值候选

这些值是 6.0 probe 默认预算，不是 6.1 最终生产值：

```text
internal DSP block             10 ms
public protocol frame          20 ms
render reference queue         64 frames
capture ingress queue          64 frames
coarse event capacity          128
probe watchdog                 2000 ms
KWS duplicate cooldown         1500 ms
maximum report JSON            64 KiB
```

Windows Real 证据可修订这些值；修订后必须更新 ADR-010 addendum 和实施报告。

## 4. Backend candidate contract

候选矩阵：

```text
WebRTC APM Python/native adapter
Windows endpoint/system AEC capability
macOS voice-processing capability
bypass baseline
```

当前 real AEC runner 对 `aec-audio-processing` 提供可选适配器，要求 reverse/render stream API 实际存在。导入成功或对象创建成功不等于 AEC 通过；必须分别执行 far-end-only 和 double-talk。

KWS 首选候选为 sherpa-onnx `KeywordSpotter`。工具不会下载模型；必须显式传入本地 tokens、encoder、decoder、joiner 和 keywords 文件。

## 5. 真实探测入口

```powershell
python tools/probe_gate6_audio_devices.py
python tools/probe_gate6_duplex.py --duration 3
python tools/probe_gate6_aec.py --scenario capability
python tools/probe_gate6_aec.py --scenario far_end_only --duration 5
python tools/probe_gate6_aec.py --scenario double_talk --duration 6
python tools/probe_gate6_kws.py
```

带本地 KWS 模型：

```powershell
python tools/probe_gate6_kws.py `
  --tokens <tokens.txt> `
  --encoder <encoder.onnx> `
  --decoder <decoder.onnx> `
  --joiner <joiner.onnx> `
  --keywords-file <keywords.txt> `
  --duration 12
```

## 6. 退出与阶段授权

自动/Fake 全绿只能证明契约、隐私、失败和清理语义。Gate 6.1 仍不可开始，直到：

- Windows device inventory、duplex、AEC far-end-only、AEC double-talk、KWS live 有真实脱敏结果；
- 用户完成必要的人类观察；
- backend/fallback/block size/format/delay/drift/KWS/预算被写入报告；
- macOS 明确保持 `Pending macOS Real Evidence` 或提供真实结果；
- terminal resource 全零。

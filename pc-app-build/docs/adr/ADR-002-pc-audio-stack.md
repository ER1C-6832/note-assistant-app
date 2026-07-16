# ADR-002：PC 音频栈

状态：**Superseded by ADR-007-current-pc-audio-and-gate3-boundary**

## 历史决策

Gate 0 候选使用 `sounddevice RawInputStream / RawOutputStream + libopus/opuslib + PCM16 bytes`，上行参数为 16 kHz、mono、20 ms、640 bytes/frame、Opus VOIP 24 kbps。

## 被取代原因

Gate 3.2 实施和真实验收采用 PyAudio/PortAudio capture 与 PyAV/FFmpeg Opus，并由 `pyproject.toml` 管理正式 runtime dependencies。当前 PTT/streaming 共用 AudioEngine、bounded queues、one worker、one uplink owner 和 one microphone lease。

## 替代记录

完整当前决策见：

- `ADR-007-current-pc-audio-and-gate3-boundary.md`；
- `PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE3_AMENDMENT.md` 第 2～3 节；
- `GATE3_IMPLEMENTATION_PLAN.md` Gate 3.2～4.2；
- `GATE3_STREAMING_CONVERSATION_SPEC.md`。

本 ADR 保留用于解释 Gate 0 历史，不再约束当前实现。

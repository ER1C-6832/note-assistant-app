# Gate 4 Spec Index

状态：Gate 4 实现完成；4.4 Final Acceptance Candidate  
最终收口基线：`note-assistant-app@9f37041cc5a955d0f943e552a465a8e9b02046a0`  
目标分支：`rewrite/single-process-runtime`

## 1. 权威文档集合

1. `GATE4_FINAL_FREEZE.md`
   - Gate 4 最终冻结入口，定义已完成能力、资源终态、证据和明确非目标。
2. `GATE4_TTS_PLAYBACK_AND_TWO_TURN_SPEC.md`
   - 下行协议、热路径、actual PlaybackEnded、自动续轮和恢复语义。
3. `GATE4_3_AUTO_NEXT_TURN_FREEZE.md`
   - actual PlaybackEnded 唯一续轮规则及事件排列语义。
4. `GATE4_IMPLEMENTATION_PLAN.md`
   - 4.0～4.4 分阶段范围和退出条件。
5. `GATE4_TEST_AND_ACCEPTANCE_PLAN.md`
   - 自动、Fake、Windows Real、异常和资源终态矩阵。
6. `../../adr/ADR-008-gate4-playback-and-auto-next-turn.md`
   - Gate 4 不可逆架构决策。

发生冲突时，按以下顺序解释：

1. 当前 endpoint 的真实 Probe/Real runner 证据；
2. `GATE4_FINAL_FREEZE.md`；
3. 主 Spec；
4. Accepted ADR；
5. 测试与实施计划；
6. Implementation/Delivery Report；
7. 历史候选报告。

## 2. 已冻结真实事实

### 2.1 Gate 4.0 协议

- ServerHello：Opus / 24,000 Hz / mono / 20 ms；
- 一轮 130 个 binary packet，48～107 bytes，中位数 68 bytes；
- TTS：`start -> sentence_start -> sentence_end -> sentence_start -> stop`；
- 首末 binary 均早于 terminal；
- PyAV 可解码，首 frame 报告 48 kHz / stereo / 960 sample frames；
- payload 未持久化，未打开 output，退出后无残留任务。

wire negotiation 与 decoder/output PCM 是两个层级，必须显式 plan/resample。

### 2.2 Gate 4.2 真实一轮

Windows Real runner 已返回 `real_gate_complete`：

- 628 个 encoded packet；
- decoded/played 均为 602,880 sample frames；
- output device 为 Realtek 扬声器；
- natural physical drain；
- encoded/PCM overflow=0；
- 人工确认非静音、速度和音调正常；
- 退出后 output、worker、buffer、assistant task 归零。

### 2.3 Gate 4.3 真实两轮

Windows Real runner 已返回 `real_gate_complete`：

- turn 1：130 packets，124,800 decoded/played frames；
- turn 2：249 packets，239,040 decoded/played frames；
- auto-next request/start 均为 2；
- capture generation `1 -> 2`，turn token `1 -> 2`；
- capture/playback overlap=0；
- 人工确认两轮听感正常；
- 最终无 output、worker、buffer 或 assistant task 泄漏。

## 3. 最终架构

```text
RealWebSocketTransport receiver
-> private bounded Opus ingress
-> AssistantPlaybackEngine worker
-> PyAV decode/resample
-> bounded PCM buffer
-> PyAudio callback consumption
-> physical output inactive
-> ActualPlaybackEnded
-> exactly-once next streaming capture
```

- Runtime event queue 只承载小型生命周期/计数事件；
- 原始 Opus、PCM、PyAV frame 和 PyAudio stream 不进入 state；
- capture 与 playback 默认不重叠；
- terminal JSON、transcript、queue empty 和 timer 均不能伪造 PlaybackEnded；
- stop、mode switch、disconnect、disable、shutdown、失败和取消均不自动续轮。

## 4. Gate 4.4 最终验收入口

自动累计：

```powershell
python tools/verify_gate4_4_cumulative.py
```

Windows 播放中 stop：

```powershell
python tools/verify_gate4_4_real_stop_during_playback.py
```

4.4 Real stop 必须证明：取消不产生 natural PlaybackEnded、auto-next 计数不增加、session 和全部音频任务/队列归零。

## 5. 明确非目标

Gate 4 不实现：

- MCP；
- KWS；
- AEC/NS/AGC；
- acoustic/full-duplex barge-in；
- 蓝牙或设备热插拔完整恢复；
- 第二 Runtime、第二 event loop、Sidecar 或 localhost bridge。

这些能力不得在 README、UI 或 capability detail 中被描述为 Gate 4 已完成。

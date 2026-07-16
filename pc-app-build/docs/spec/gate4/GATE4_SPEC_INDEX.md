# Gate 4 Spec Index

状态：Frozen for Gate 4.1 Foundation  
冻结输入基线：`note-assistant-app@648cfb8801fefafc5a5d450eb1d98f841b0b0556`  
目标分支：`rewrite/single-process-runtime`

## 1. 文档集合

Gate 4 由以下文件共同定义：

1. `GATE4_TTS_PLAYBACK_AND_TWO_TURN_SPEC.md`
   - 冻结下行协议、播放热路径、状态机、`actual PlaybackEnded`、自动续轮和非目标。
2. `GATE4_IMPLEMENTATION_PLAN.md`
   - 把 Gate 4 拆为 4.0～4.4，定义每阶段入口、交付物和退出条件。
3. `GATE4_TEST_AND_ACCEPTANCE_PLAN.md`
   - 定义自动、Fake、QML、Windows Real、两轮和泄漏验收矩阵。

## 2. 规范优先级

发生冲突时，按以下优先级解释：

1. Gate 4.0 真实协议探测报告中已经确认的 wire 行为；
2. 本目录已冻结的 Gate 4 Spec；
3. `PC_ASSISTANT_RUNTIME_MASTER_PLAN.md` 中已并入的当前决策；
4. Accepted 且未 superseded 的 ADR；
5. Gate 4 实施计划；
6. Delivery/Implementation Report；
7. 旧 Gate 报告、旧 runner 名称和历史候选实现。

若真实官方云行为与本 Draft 的假设冲突，必须先更新 Gate 4 Spec 和协议探测报告，再修改产品代码；不得在 Adapter 中静默加入未记录的兼容分支。

## 3. Gate 3 输入条件

Gate 4 继承以下 Gate 3 已冻结事实：

- 单 Python Runtime 进程；
- Qt 主线程 + 单 qasync event loop；
- 单 Controller 状态写入者；
- 单 bounded Runtime event queue；
- 单 WebSocket sender/receiver owner；
- PyAudio capture + PyAV Opus uplink；
- PTT 与 streaming 共用 capture engine；
- local VAD 自动提交；
- Gate 3 回复停在 `WAITING_FOR_NEXT_TURN`，不自动开麦；
- `AssistantTextReceived`、`TtsStateReceived` 和 `tts/stop` 不是续轮触发源；
- stop、cancel、finalize、lease release 幂等；
- generation/session/turn 的陈旧事件无害。

根目录 PowerShell 文件是否加入 Git 不是 Runtime 架构契约。当前项目允许把本地 PowerShell 包装器写入 `.gitignore`；版本化验收资产应位于 `pc-app-build/tests`、`pc-app-build/tools` 和本目录。Architecture test 不得仅因根目录本地包装器未入库而失败。


## 4. Gate 4.0 已冻结真实事实

Windows 当前真实 endpoint 探测返回 `real_gate_complete`：

- ServerHello 下行格式：Opus、24,000 Hz、mono、20 ms；
- 一轮收到 130 个 binary packet，大小 48～107 bytes，中位数 68 bytes；
- 观察到 TTS 顺序：`start -> sentence_start -> sentence_end -> sentence_start -> stop`；
- 首个和最后一个 binary 均早于 terminal `tts/stop`；
- probe queue overflow=0，unarmed binary=0，stale event=0；
- PyAV 至少解码一个 packet 成功，首个 decoded frame 报告 48,000 Hz、2 channels、960 sample frames；
- `payload_persisted=false`、`output_device_opened=false`，退出后 probe/assistant task 归零。

因此 Gate 4.1 必须区分 wire format 与 decoded PCM format；不得把 24 kHz/mono 直接当成 decoder/output format。

## 5. Gate 4 目标

```text
real WebSocket binary downlink
-> negotiated Opus format
-> bounded encoded ingress
-> PyAV decode/resample
-> bounded PCM playback buffer
-> PyAudio output
-> actual PlaybackStarted / PlaybackEnded
-> exactly one next streaming turn
-> real two-turn conversation
```

## 6. Gate 4 非目标

- 不实现 acoustic full-duplex barge-in；
- 不实现 AEC/NS/AGC；
- 不实现 KWS；
- 不实现蓝牙/热插拔完整恢复；
- 不实现 MCP；
- 不建立第二 Runtime、第二 event loop 或 localhost bridge；
- 不把 Opus/PCM payload 放入 Runtime event queue；
- 不为 Gate 4 顺带重写整个 Controller/StateMachine；
- 不用定时器估算值伪造 `PlaybackEnded`。

## 7. 冻结流程

1. 先完成 Gate 4.0 真实协议探测；
2. 将采样率、frame duration、TTS 状态顺序和 binary 边界写回 Spec；
3. 标记本索引为 `Frozen for Gate 4.1`；
4. 才允许实现真实播放 Adapter；
5. 每个子 Gate 通过累计回归后再进入下一阶段。


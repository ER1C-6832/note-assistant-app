# Gate 3.4 最终收口验收报告

交付基线 HEAD：`9f204735e338ff7e87010ca58e628406673e13ae`  
分支：`rewrite/single-process-runtime`  
交付形式：增量覆盖包，不修改远程仓库。

## 1. 收口范围

- 恢复累计自动入口 `VERIFY_GATE3_3.ps1`；
- 恢复独立真实入口 `RUN_GATE3_3_REAL_STREAMING.ps1`；
- 修正 Gate 3.1 capability 历史测试；
- 移除 Gate 3.2 对旧安装脚本的强制契约；
- 冻结 WAITING_FOR_NEXT_TURN；
- 增加 deterministic state/lifecycle/resource tests；
- 合并 Gate 3 修正案到总纲；
- supersede ADR-002 并新增 ADR-007；
- 更新 Gate 0 现状注记、Gate 3 Spec/计划/报告。

明确非目标：Controller 拆分、TTS playback、auto second turn、barge-in、MCP、KWS、第二 Runtime 或无关重构。

## 2. 状态语义

当前 streaming turn 收到有效 assistant text/TTS transcript 后：

```text
streaming_state = WAITING_FOR_NEXT_TURN
streaming_session_active = true
audio.status = idle
capture/uplink/VAD/response timer/worker/lease = stopped
next-turn capture = not started
```

当前 turn 完成一次。旧 generation/session/turn no-op。Gate 4 引入实际播放后，actual PlaybackEnded 才能成为 auto next-turn 的唯一触发源。

## 3. 异常矩阵

| 场景 | 自动测试/契约 |
|---|---|
| repeated start | controller lifecycle：listen/start 与 capture 仍为 1 |
| stop waiting speech | parameterized controller lifecycle |
| stop user speaking | parameterized controller lifecycle |
| end_of_speech / stop ordering | deterministic Reducer/Event/Effect tests + existing Gate 3.3 integration |
| no speech | existing Gate 3.3 no-speech test |
| short speech | Gate 3.2 engine/controller no-useful-audio tests |
| packet/uplink overflow | Gate 3.1 queue + Gate 3.2 engine/controller overflow tests |
| disconnect listening | existing Gate 3.3 recovery integration |
| disconnect thinking | Gate 3.4 deterministic termination matrix |
| reconnect once | existing Gate 3.3 resume-once assertion |
| streaming -> PTT | existing Gate 3.3 mode-switch test |
| disable | Gate 3.4 lifecycle cleanup |
| shutdown | Gate 3.4 no `assistant-*` tasks |
| timeout/stop/disconnect permutations | deterministic reducer sequence tests |
| stale generation/session/turn | Gate 3.4 stale-event no-op test |

测试不依赖真实线程 race。

## 4. 资源终态矩阵

### A. 正常 session stop、连接保留

必须无 streaming response timer、audio uplink、VAD、capture、audio worker、microphone lease。Transport sender/receiver 可以保留。

### B. 自动恢复

同一 generation 最多一个 reconnect timer；成功后 timer 消失；最多恢复一次 capture。

### C. disable/shutdown

必须无 reconnect/streaming timer、uplink、VAD、capture、worker、lease、sender、receiver、pending `assistant-*` task 和第二 Python Runtime。

## 5. 自动入口

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

顺序：dependency imports、compileall、Black、Ruff、Gate 1.7、Gate 2.1～2.7、Gate 3.1～3.4 pytest、Gate 2.7 Fake、Gate 3.1 offscreen QML、Gate 3.2 Fake PTT、Gate 3.3 Fake streaming。

脚本 fail-fast，并传播原始非零 exit code。

## 6. 本交付环境的实际执行结果

本覆盖包是在 GitHub 应用读取到的 HEAD 文件契约上生成。当前执行容器无法通过 GitHub 应用导出完整仓库快照，也不能从 `github.com` 建立网络 clone，因此没有可供该容器运行完整 Gate 1.7～3.4 的完整工作树。

本环境实际执行：

- `python -m compileall -q apps tools tests`（增量覆盖树）：通过；
- `python -m black --check apps tools tests`（增量覆盖树）：通过；
- `python -m ruff check apps tools tests`（增量覆盖树）：通过；
- `python -m pytest -W error tests/gate3_4/test_gate3_4_architecture.py -q`（GitHub HEAD 契约合成树）：`6 passed`；
- 修改后 `EffectRunner` 的受控并发屏障 harness：`effect_runner_idempotency_verified`；
- PowerShell 累计入口和真实入口静态契约检查：通过；
- 增量 ZIP 的敏感路径、缓存路径和文件清单审计：通过。

第一次 Black 检查发现 7 个新增/修改 Python 文件需要格式化并返回非零；执行 Black 后重新运行，最终 `--check` 通过。该首次失败没有被隐藏。

**不得把上述局部检查描述为全量 verifier 已通过。** 目标 Windows 工作树仍需在覆盖后实际运行累计 PowerShell verifier。自动验收全部返回 0 前，Gate 3.4 的最终关闭状态为“待目标工作树复测”。

## 7. 真实验收摘要

沿用用户提供的 Gate 3.3 真实人工证据：250 captured/encoded/uploaded、drop/overflow 0、first PCM 162 ms、first Opus/upload 165 ms、stop 49 ms、readable STT/assistant transcript、final `real_gate_complete`，且 stop 后音频/runtime 资源已清理。

本交付环境未重新执行真实麦克风、Windows PortAudio、真实 WebSocket 或激活。覆盖后应通过独立 runner 复测；不得将沿用证据伪装成本次环境运行结果。

## 8. Gate 4：未开始

未实现 TTS playback、actual PlaybackEnded、auto next-turn、真实两轮或 barge-in。Transcript 接收不等于播放。

## 9. 已知但不阻塞代码覆盖的问题

- 第一版能量 VAD 尚未完成全设备/噪声泛化；
- 单次 latency sample 不能替代 Gate 7 p95；
- Windows 蓝牙/热插拔/AEC/NS/AGC 属于后续增强；
- 目标工作树全量自动 verifier 和真实 microphone 需由用户覆盖后复测。

## 10. 交付文件与删除清单

完整新增/修改文件清单、测试映射和覆盖后命令见 `GATE3_4_DELIVERY_MANIFEST.md`。

删除文件：无。历史修正案和 ADR-002 均保留；ADR-002 仅标记 superseded 并指向 ADR-007。未创建或删除 `INSTALL_GATE3_2_AUDIO_DEPS.ps1`。

## 11. 验收结论

本增量覆盖包是 Gate 3.4 **收口候选交付**。本容器已完成上述静态、格式、语法和隔离幂等验证；由于缺少完整可执行工作树、Windows PowerShell、PySide6/qasync/PyAudio/PyAV、真实麦克风及目标网络，本环境不能宣布累计自动 verifier 全绿，也不把用户提供的真实证据冒充为本次运行结果。

用户覆盖到完整 Windows 工作树后，只有 `VERIFY_GATE3_3.ps1` 返回 0，才能把 Gate 3.4 最终状态从“待目标工作树复测”改为“完成”。

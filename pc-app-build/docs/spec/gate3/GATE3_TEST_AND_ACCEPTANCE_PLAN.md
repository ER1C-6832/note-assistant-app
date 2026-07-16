# Gate 3 测试与验收计划

状态：Gate 3.4 冻结

## 1. 分层

```text
Static architecture
Unit
Reducer/Event/Effect deterministic ordering
Fake Audio/Transport integration
Offscreen QML
Windows manual UI
Real microphone/WebSocket
Shutdown/leak
Performance samples
```

真实线程竞争不作为确定性自动测试手段。并发终止通过不同事件排列验证。

## 2. Gate 3.1

- global single AssistantOverlay；
- panel 不占主 RowLayout；
- Preferences schema/debounce/shutdown flush；
- `streamingCapabilityReady` 字段存在、bool、由 state capability 驱动；
- 不永久断言 False；
- offscreen QML smoke。

## 3. Gate 3.2

- PyAudio/PyAV files and pyproject dependencies；
- callback non-blocking；
- PCM capacity 8 drop-oldest；
- encoded capacity 16 fail-turn；
- one audio worker/uplink；
- one microphone lease；
- PTT start/stop/no speech/overflow/stale/double press/disable/shutdown/disconnect；
- Fake PTT；
- Real PTT independent manual entry。

依赖契约是 `python -m pip install -e ".[dev]"`；不要求旧安装脚本。

## 4. Gate 3.3 状态语义

有效 assistant text/TTS transcript 后检查：

- WAITING_FOR_NEXT_TURN；
- session active；
- audio idle；
- no capture/uplink/VAD/response timer/worker/lease；
- one listen/start；
- one listen/stop；
- no StartStreamingConversation effect；
- 等待后仍无自动第二轮；
- manual stop 后 session inactive。

Gate 3.3 测试明确验证 STREAMING_CONVERSATION 与 VAD capability active、ViewModel projection True；TTS playback/barge-in not_ready。

## 5. 确定性异常矩阵

至少覆盖：

| 场景 | 关键断言 |
|---|---|
| repeated start | one capture/start/uplink/VAD/lease |
| stop waiting speech | one abort, inactive, no leak |
| stop speaking | one abort, inactive, no leak |
| end then stop | at most one turn finalize; no duplicate protocol |
| stop then end | late VAD no-op |
| no speech | one abort, session ends |
| short speech | no listen/stop, one abort |
| overflow | visible error, resources released |
| disconnect listening | recovering, one reconnect timer |
| disconnect thinking | timer/capture cleared, recovering |
| reconnect | timer disappears, one resumed capture |
| streaming -> PTT | session stops before preference effect |
| disable | all runtime resources zero |
| shutdown | transport and assistant tasks also zero |
| timeout/stop/disconnect permutations | one finalization path |
| stale generation/session/turn | state/effects unchanged; no capture resume |

每个场景检查状态终点、finalize 次数、协议调用次数、自动续轮为零、无未处理 asyncio exception、无后台任务泄漏。

## 6. 资源终态

### A. session 正常结束、连接保留

```text
no streaming response timer
no audio uplink task
no VAD task
no capture stream
no audio worker
no microphone lease
transport sender/receiver may remain
```

### B. 自动恢复

```text
at most one reconnect timer per generation
timer may exist while waiting
no timer after successful reconnect
at most one resumed capture
```

### C. disable/shutdown

```text
no reconnect timer
no streaming timer
no audio uplink task
no VAD task
no capture stream
no audio worker
no microphone lease
no transport sender
no transport receiver
no pending assistant-* task
no second Python runtime process
```

不引入 psutil。静态检查应用/runtime 不导入 subprocess/multiprocessing；验收 runner 的短生命周期 Python 子命令不计为第二 Runtime。

## 7. 自动入口

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

顺序且 fail-fast：

1. PySide6/qasync/sqlalchemy/websockets/pyaudio/av import；
2. compileall；
3. Black --check；
4. Ruff check；
5. pytest -W error Gate 1.7、2.1～2.7、3.1～3.4；
6. Gate 2.7 Fake；
7. Gate 3.1 offscreen QML；
8. Gate 3.2 Fake PTT；
9. Gate 3.3 Fake streaming/VAD。

失败立即停止并传播非零 exit code。失败后不得打印 passed。

## 8. Real streaming

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_3_REAL_STREAMING.ps1
```

0=pass，1=implementation/acceptance failure，2=environment/device/network/activation blocked。输出必须脱敏。

Real Gate 一轮通过条件：真实 WebSocket、真实麦克风、VAD start/end、Opus uploaded>0、readable STT、readable assistant/TTS transcript、WAITING 不自动开麦、manual stop、无 audio/runtime task 残留。

单次 latency 只写 sample，不写 p95。识别文本可读不等于识别准确率达标。

## 9. Gate 4 边界

真实 PlaybackEnded 后自动 Listening 和真实两轮只在 Gate 4 验收。Gate 3 自动/Real runner 不得模拟或宣称该能力。

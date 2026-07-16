# ADR-007：当前 PC 音频栈与 Gate 3 连续对话边界

状态：Accepted  
日期：2026-07-16  
实施基线：`9f204735e338ff7e87010ca58e628406673e13ae`

## 背景

ADR-002 的 sounddevice/opuslib 候选与 Gate 3.2 已实施、已真实验证的 PyAudio/PyAV 管线不一致。同时 Gate 3.3 已接收 transcript 并停在 WAITING_FOR_NEXT_TURN，但尚无 TTS playback 或自动第二轮。

## 决策

1. 平台 capture 使用 PyAudio/PortAudio；Opus 编码使用 PyAV。
2. 依赖由 `pyproject.toml` 管理，正式安装命令为 `python -m pip install -e ".[dev]"`。
3. PTT 与 streaming 共用 AssistantAudioEngine、bounded PCM/Opus queues、one audio worker、one qasync uplink owner、one WebSocket sender 和 one microphone lease。
4. Gate 3 连续对话范围止于 local VAD、Opus uplink、readable STT/assistant transcript 和手动 session stop。
5. 有效 assistant text/TTS transcript 后进入 WAITING_FOR_NEXT_TURN，但不自动开麦。
6. TTS decode/playback、actual PlaybackEnded、auto next turn、real two-turn 和 barge-in 属于 Gate 4。
7. Gate 4 中 actual PlaybackEnded 是自动 next-turn 的唯一合法触发源。
8. stop/finalize/cancel/lease release 幂等；陈旧 generation/session/turn no-op。
9. 不引入第二 Python Runtime 进程。

## 后果

- ADR-002 superseded；
- 不恢复无实际逻辑的 INSTALL_GATE3_2_AUDIO_DEPS.ps1；
- Gate 3.1 历史 capability 测试改为字段/类型/状态驱动；
- Gate 3.3 测试明确 streaming capability active；
- Gate 3.4 验收覆盖异常排列和资源终态；
- Gate 4 不得复用 transcript 事件假装 PlaybackEnded。

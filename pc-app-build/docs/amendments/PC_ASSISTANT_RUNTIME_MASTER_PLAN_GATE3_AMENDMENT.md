# PC Assistant Runtime 总计划 Gate 3 修订

修订基线：`872d5be8b44f679a0531b081c61ac3d7b0921255`  
实施基线：`9f204735e338ff7e87010ca58e628406673e13ae`

状态：**已并入总纲 / 已实施**。

本文件作为历史决策记录保留。其有效规范已经并入 `docs/PC_ASSISTANT_RUNTIME_MASTER_PLAN.md`；发生冲突时以总纲、当前 Gate 冻结测试计划和当前代码不可变量为准。

## 1. 决策变更

旧顺序：

```text
Gate 3 PTT
Gate 4 TTS
Gate 5 MCP
Gate 6 连续对话
```

实施后的顺序：

```text
Gate 3  共用音频基础 + PTT + 连续对话上行/VAD + Gate 3.4 收口
Gate 4  TTS 播放 + PlaybackEnded 自动续轮 + 两轮连续对话 + 可选简单插话
Gate 5  MCP 便签闭环
Gate 6  语音体验和设备增强
Gate 6.5 KWS
Gate 7  延迟验证
```

连续对话上行/VAD 不再排在 MCP 后面，但真正的播放结束自动续轮仍不得前移到 Gate 3。

## 2. Gate 3 已实施范围

### Gate 3.1

全局悬浮 UI、Aurora scaffold、Preferences、Audio Ports/Fake。

### Gate 3.2

PyAudio/PyAV 共用上行管线、PTT、bounded queues、单 audio worker、单 uplink owner、单 microphone lease。

### Gate 3.3

Streaming session、local VAD、自动 listen/stop、真实一轮 Opus 上行、STT/assistant transcript、WAITING_FOR_NEXT_TURN。

### Gate 3.4

自动入口、历史测试契约、状态语义、异常生命周期、资源终态、ADR 和文档收口。

## 3. Gate 4 保留边界

```text
TTS binary downlink
Opus decode
PyAudio playback
actual PlaybackEnded
PlaybackEnded -> exactly one next-turn capture
real two-turn continuous conversation
optional simple barge-in
```

AssistantTextReceived 或 TtsStateReceived 自身不得启动下一轮录音。Gate 3.4 的 WAITING_FOR_NEXT_TURN 只表示 session 仍活跃但 capture 已停止。

## 4. 核心不变量

```text
single process
qasync single loop
single Controller state writer
single event pump
single WebSocket sender
single microphone lease
shared PTT/streaming AudioEngine
bounded queues
generation/session/turn stale-event rejection
NoteCommandService single note write boundary
LocalAppData runtime data
```

## 5. 历史保留说明

保留本文件而不删除，是为了说明为何旧总纲、旧 target gate、旧报告和当前实施顺序不同。后续不得再次把连续上行/VAD 移回 Gate 6，也不得把 TTS 播放或自动第二轮误写成 Gate 3 已完成能力。

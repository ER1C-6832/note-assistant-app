# PC Assistant Runtime 总计划 Gate 3 修订

修订基线：`872d5be8b44f679a0531b081c61ac3d7b0921255`

状态：本修订在合并后覆盖现有总纲中与 Gate 3、Gate 4、Gate 5、Gate 6 顺序冲突的描述。后续应在一次文档整理提交中把内容并回 `PC_ASSISTANT_RUNTIME_MASTER_PLAN.md`，在此之前以本修订为准。

## 1. 决策变更

旧顺序：

```text
Gate 3 PTT
Gate 4 TTS
Gate 5 MCP
Gate 6 连续对话
```

新顺序：

```text
Gate 3  共用音频基础 + PTT + 连续对话上行/VAD
Gate 4  TTS 播放 + 两轮连续对话闭环 + 简单插话
Gate 5  MCP 便签闭环
Gate 6  语音体验增强（可选高级 VAD/AEC/设备恢复；不再是连续对话首次实现）
Gate 6.5 KWS
Gate 7  延迟验证
```

连续对话不再排在 MCP 后面。

## 2. Gate 3 修订目标

```text
Global Floating Assistant Shell
Assistant Preferences
Shared Audio Pipeline
Push-to-Talk
Streaming Conversation Uplink
Local VAD
Automatic Turn Submission
Recovery / Cancellation / Shutdown
```

### Gate 3.1

全局悬浮 UI + Aurora scaffold + Preferences + Audio Ports/Fake。

固定 AssistantPanel 必须从便签主 RowLayout 移除，现有面板内容保留在悬浮展开层。

### Gate 3.2

真实 PyAudio/Opus 共用上行管线和 PTT。

### Gate 3.3

连续对话 session、VAD、自动 stop/listen、真实一轮上行。

### Gate 3.4

Gate 3 总验收、异常恢复和关闭。

## 3. Gate 4 修订目标

```text
TTS binary downlink
Opus decode
PyAudio playback
PlaybackEnded
Streaming auto-resume
Two-turn real continuous conversation
Optional simple barge-in
```

连续对话的“完整通过”必须等待真实 PlaybackEnded 后恢复并完成第二轮。

## 4. Gate 5

MCP 范围保持不变，但实施时点移动到完整语音交互之后：

```text
notes.create
notes.search
notes.delete + confirmation
```

仍共用 NoteCommandService。

## 5. Gate 6

Gate 6 不再首次实现连续对话。可用于：

- VAD 阈值和噪声适配；
- AEC/NS/AGC 调研或增强；
- 蓝牙/热插拔恢复；
- 持续待命策略；
- 更复杂 barge-in；
- 系统音频 interruption；
- 多设备选择。

任何增强仍不得引入第二 Runtime 或第二状态机。

## 6. UI 修订

最终产品入口：

```text
ApplicationWindow global overlay
-> Aurora floating button
-> expandable assistant panel
```

- 不占便签主布局宽度；
- 全页面单实例；
- 可拖动；
- 默认折叠；
- 展开后保留文本、连接和 Developer 诊断；
- 模式设置允许 PTT/连续切换；
- Aurora 颜色和运动由 AssistantState 投影。

## 7. 核心不变量

本修订不改变：

```text
single process
qasync single loop
single Event Pump
AssistantController single state writer
bounded queues
single WebSocket sender
NoteCommandService single note write boundary
LocalAppData runtime data
```

## 8. 更新后的最终产品功能顺序

```text
手动便签
文本 Runtime
全局悬浮 Assistant 入口
共用音频基础
PTT
连续对话上行/VAD
TTS 播放
两轮连续对话/简单插话
MCP 便签
可选 KWS
延迟与设备增强
```

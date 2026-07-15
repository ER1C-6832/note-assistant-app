# Gate 3 语音交互与全局悬浮入口 Spec 索引

基线提交：`872d5be8b44f679a0531b081c61ac3d7b0921255`

状态：**冻结候选，进入 Gate 3.1 前必须先合并文档决策。**

## 1. 本包目的

Gate 2 已完成真实文本、恢复、QML 接入和总验收。Gate 3 不再把“连续对话”推迟到 MCP 之后，而是把它与 PTT 共用的音频基础一起纳入主线。

同时修正 Gate 2.6 UI 的产品布局问题：当前 `AssistantPanel` 是 `Main.qml` 主 `RowLayout` 的固定第三列，长期占用约 330～410 px，压缩便签列表和详情。Gate 3.1 将其迁移为应用内全局悬浮入口，不再参与便签主布局计算。

## 2. 权威顺序

发生冲突时按以下顺序解释：

1. `PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE3_AMENDMENT.md`
2. 本目录中的 Gate 3 专项 Spec
3. Gate 2 已冻结的 State / Controller / Event Pump 契约
4. 旧总纲中被本修订明确替换的 Gate 3、Gate 4、Gate 6 描述

本包不允许推翻以下已验收不变量：

```text
单 Python 进程
Qt 主线程 + qasync 单 asyncio loop
AssistantController 唯一 AssistantState writer
Transport / Audio / QML 只产生事件
单 Event Pump
单 WebSocket sender
无 sidecar / localhost HTTP / 控制轮询
Manual UI 与未来 MCP 共用 NoteCommandService
```

## 3. 文件说明

- `UI_CURRENT_STATE_AUDIT.md`：当前固定侧栏问题与截图/代码审计。
- `GATE3_UI_SHELL_AND_AURORA_SPEC.md`：全局悬浮入口、拖拽、折叠、Aurora 状态视觉。
- `GATE3_ASSISTANT_PREFERENCES_SPEC.md`：语音模式和悬浮位置持久化边界。
- `GATE3_AUDIO_PIPELINE_SPEC.md`：PTT/连续对话共用的 PyAudio/Opus 管线。
- `GATE3_STREAMING_CONVERSATION_SPEC.md`：连续对话、VAD、回合和 TTS 依赖。
- `GATE3_STATE_EVENT_EFFECT_CONTRACT.md`：需要激活的 State/Event/Effect 契约。
- `GATE3_IMPLEMENTATION_PLAN.md`：Gate 3.1～3.4 和 Gate 4 衔接。
- `GATE3_TEST_AND_ACCEPTANCE_PLAN.md`：自动、Fake、Real、Windows UI/音频验收。
- `../../adr/ADR-0004-GLOBAL_FLOATING_ASSISTANT_AND_STREAMING_MAINLINE.md`：不可逆决策记录。
- `../../amendments/PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE3_AMENDMENT.md`：对现有总纲的正式修订。

## 4. Gate 3 主线

```text
Gate 3.1  全局悬浮 UI Shell + 偏好设置 + 音频接口/Fake
Gate 3.2  共用真实采集管线 + PTT Real
Gate 3.3  连续对话上行 + VAD + 自动提交
Gate 3.4  Gate 3 总验收与恢复/关闭闭环
Gate 4.1  TTS 解码与播放
Gate 4.2  两轮连续对话 + PlaybackEnded 后恢复监听 + 简单插话
```

连续对话不再等待 MCP；MCP 仍在音频交互链路稳定后实施。

## 5. 冻结结论

- `AssistantPanel` 的内容可以保留，但外壳必须从主 `RowLayout` 移除。
- 全局入口是应用窗口内部悬浮，不创建独立系统窗口，不使用第二进程。
- 收口形态是 Aurora 悬浮按钮；展开面板仍可保留现有连接、文本和 Developer 诊断。
- PTT 与连续对话不是两套 AudioEngine，而是同一音频管线上的两种会话策略。
- 设置中允许切换 `hold_to_talk` / `streaming_conversation`，切换只改变偏好和后续按钮语义，不允许直接从 QML 操作麦克风。
- 完整连续对话必须以真实两轮语音闭环验收，不能用“收到一次文本/TTS”代替。

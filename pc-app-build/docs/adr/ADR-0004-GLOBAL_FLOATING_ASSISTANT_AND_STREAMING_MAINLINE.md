# ADR-0004：全局悬浮 Assistant 入口与连续对话前移

状态：Accepted for Gate 3 Spec Freeze

基线：`872d5be8b44f679a0531b081c61ac3d7b0921255`

## Context

Gate 2.6 把 AssistantPanel 作为主 RowLayout 的固定右列接入，方便总验收，但会永久压缩便签列表和详情。产品最终目标是类似 Android 的全局 Aurora 助手入口。

旧总纲还把连续对话放在 MCP 之后的 Gate 6，而当前产品要求连续对话与语音按钮模式切换成为主线能力，不能继续拖后。

## Decision

1. Gate 3.1 把 AssistantPanel 从主布局移到应用内全局悬浮 Overlay。
2. 默认折叠为 Aurora 按钮；展开面板保留现有连接、文本和 Developer 诊断。
3. Overlay 可拖动并保存设备本地位置，但不创建独立系统窗口。
4. PTT 与连续对话共用一套 PyAudio/Opus 管线和一个麦克风 owner。
5. 连续对话上行/VAD 在 Gate 3 完成；TTS 播放后的两轮完整闭环在 Gate 4 完成。
6. MCP 移到完整语音交互稳定之后。
7. 设置允许切换 PTT/连续模式；偏好存入独立 AssistantPreferencesStore。
8. Aurora 只投影 AssistantState，不维护第二套业务状态。

## Consequences

### Positive

- 便签核心布局不再被助手永久挤占；
- UI 形态可直接演进到最终产品；
- 连续对话不会被 MCP 阶段阻塞；
- PTT/Streaming 共享设备、队列和取消模型；
- Android 的产品语义被保留，PC 仍保持 qasync/Event Pump 架构。

### Cost

- Gate 3.1 同时包含 UI shell、偏好和音频接口冻结；
- 主按钮需要处理展开、PTT 长按、Streaming 点击的手势冲突；
- Windows 无 AEC 场景下 barge-in 必须默认关闭并单独真实验收；
- 需要额外 UI position persistence 和 QML smoke。

## Rejected Alternatives

- 保留固定窄栏：仍影响便签布局。
- 独立顶层助手窗口：生命周期和焦点复杂。
- 每页放一个按钮：重复实例和状态。
- PTT/Streaming 各自 AudioEngine：资源竞争和重复 bug。
- 连续对话继续等到 Gate 6：不符合当前产品优先级。
- 直接复制 Android Controller：破坏 PC 纯 Reducer/Event Pump。

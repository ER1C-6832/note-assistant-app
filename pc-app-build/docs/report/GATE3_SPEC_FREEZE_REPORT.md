# Gate 3 Spec Freeze Report

基线提交：`872d5be8b44f679a0531b081c61ac3d7b0921255`

## 1. 输入

- Gate 2.7 Automated/Fake：通过；
- Gate 2.7 Real：通过；
- 当前 PC UI 截图；
- `Main.qml` 固定 AssistantPanel 布局；
- Gate 2 Full State/Event/Reducer；
- PC Runtime 总纲；
- Android Aurora、语音模式设置、PTT/Streaming 设计参考。

## 2. 发现

当前助手作为主 RowLayout 固定第三列，永久占用 330～410 px，压缩便签列表和详情。问题属于 UI Shell，不应倒回 Gate 2 修复，但必须在 Gate 3.1 首先处理。

旧总纲把连续对话放在 MCP 后，不符合新的产品优先级；State 和事件已预留 streaming/VAD/barge-in 字段，因此可以在保持单 State/Event Pump 的前提下前移激活。

## 3. 冻结决策

- Gate 3.1 把助手迁移成应用内全局悬浮 Overlay；
- 默认折叠为 Aurora 按钮；
- 可拖动并保存位置；
- 展开后保留现有面板与 Developer 诊断；
- Overlay 不改变便签布局宽度；
- 语音模式设置支持 PTT/连续切换；
- Preferences 与 RuntimeConfig 分离；
- PTT/Streaming 共用一套 PyAudio/Opus pipeline；
- Gate 3 完成连续上行/VAD；
- Gate 4 完成 TTS 播放和真实两轮闭环；
- MCP 顺延到语音主链稳定之后。

## 4. 未实现

本包只冻结 Spec，没有修改：

- QML；
- AssistantViewModel；
- Runtime State/Reducer；
- PyAudio；
- Opus/VAD；
- Real audio runner。

因此不能把本包视为 Gate 3.1 完成。

## 5. 下一交付

Gate 3.1 覆盖包应至少包含：

```text
AssistantOverlay.qml
AssistantFloatingPanel.qml
AuroraAssistantButton.qml
AssistantPanel content refactor
AssistantPreferencesStore
Preference/ViewModel bindings
Audio ports/models/fake
Gate 3.1 tests
VERIFY_GATE3_1.ps1
RUN_GATE3_1_UI_SMOKE.ps1
```

## 6. 验收判断

Spec 包通过的标准：

- 文件可直接覆盖到仓库；
- 文档间没有 fixed-panel/continuous-order 冲突；
- 不增加第二进程/loop/state；
- Gate 3.1～4.2 的功能完成定义和 Real Gate 区分明确。

# Gate 3.1 实施报告：全局悬浮 Shell、Preferences、Audio Ports/Fake

基线提交：`461bb50eb13ea6b63d35550f56ffb3ac9cbee34e`

## 1. 本 Gate 范围

Gate 3.1 只建立最终产品形态和真实音频实现之前的公共契约：

- 固定右侧 AssistantPanel 移出便签主 RowLayout；
- 应用内全局单实例 AssistantOverlay；
- 默认折叠、可拖动的 Aurora 流体按钮；
- 可展开悬浮面板，保留 Gate 2 文本、连接和 Developer 诊断；
- 独立 `assistant_preferences.json`；
- 按住说话/连续对话默认模式设置；
- 插话偏好默认关闭；
- 共享音频 models/ports/bounded queues/Fake adapters；
- 不打开真实麦克风，不声明 PTT 或连续对话已完成。

## 2. UI Shell

主布局现在只有：

```text
Sidebar + PageLoader
```

助手由 `ApplicationWindow` 直接子级 `AssistantOverlay` 承载，不参与 Layout 宽度计算。Overlay 空白区域没有 MouseArea，只有 launcher、浮动面板和明确控件接收指针事件。

新增：

```text
qml/components/AssistantOverlay.qml
qml/components/AssistantFloatingPanel.qml
qml/components/AuroraAssistantButton.qml
qml/components/AssistantVoiceModeSettings.qml
```

Aurora 颜色和运动目标全部来自 `AssistantViewModel` 对唯一 `AssistantState` 的只读投影。QML 不维护第二套 phase/connection/audio 状态。

## 3. Preferences

独立路径：

```text
%LOCALAPPDATA%\NoteAssistant\data\assistant_preferences.json
```

Schema v1 包含语音模式、连续对话超时、插话、文字功能和归一化 launcher 坐标。身份、token、endpoint 仍只在 `assistant_runtime.json`，两者不混用。

语音模式和插话设置走：

```text
QML -> AssistantViewModel -> AssistantController queue
-> ConversationStateMachine -> Set* Effect
-> AssistantPreferencesStore
```

launcher 坐标属于 UI shell，由 ViewModel 在拖动结束后 debounce 保存，shutdown 前有界 flush。

## 4. Audio Contracts/Fake

新增共享 `assistant/audio/`：

- PCM/Encoded/VAD 不可变模型；
- Capture/Encoder/VAD Protocol；
- PCM 容量 8 的 drop-oldest 语义；
- Encoded 容量 16 的 fail-on-overflow 语义；
- Scripted Fake capture、Fake Opus encoder、Scripted VAD；
- capture generation、double-start、stale frame 测试。

Gate 3.2 必须在这些接口上实现一个 PyAudio/Opus 管线，不能再建立 PTT 与 Streaming 两套 AudioEngine。

## 5. 验收

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_1.ps1
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_1_UI_SMOKE.ps1
```

通过条件：

- Gate 1/Gate 2 全量回归；
- preferences 与 audio fake 单测；
- QML offscreen 加载；
- 默认折叠；
- 展开面板前后 PageLoader 宽度不变；
- launcher 坐标持久化；
- shutdown 无 Runtime 残留。

## 6. 明确未完成

- 真实 PyAudio 输入；
- 真实 Opus 编码与 binary uplink；
- PTT 长按/松开；
- VAD 连续对话；
- TTS 播放；
- 两轮连续对话和插话。

Gate 3.2、3.3、4.1、4.2 的 Real Gate 应以真实口述命令、真实麦克风/扬声器结果和任务/设备清理为核心，不以 pytest 数量替代产品验收。

## 7. 交付构建验证

打包前完成：

```text
Black：通过
Ruff：通过
compileall：通过
Python 3.10 AST：22 files passed
Gate 2.1～2.7 + Gate 3.1：126 passed
Gate 2.7 Fake regression：fake_gate_complete
Gate 3.1 offscreen shell：gate3_1_ui_shell_verified
展开前后 PageLoader 宽度：1232.0 -> 1232.0
launcher 坐标持久化：通过
shutdown 后 Runtime task：0
```

Windows 仓库根目录的 `VERIFY_GATE3_1.ps1` 仍是最终自动验收入口；它会额外执行现有 Gate 1.7 回归。

## 验收修复与 UI 收口补充

本次后续修复不改变 Gate 3.1 Runtime 边界：

- Gate 2.7 历史测试不再要求根目录永久保留已经被当前 Gate runner 替换的脚本；
- `verify_gate2_7_real_acceptance.py` 继续作为历史 Real Gate 的持久化验收资产；
- 当前 `VERIFY_GATE3_1.ps1` 继续覆盖 Gate 2.7 自动/Fake 回归；
- 语音模式与插话偏好从助手主面板移入独立设置页，通过齿轮按钮进入；
- Aurora 按钮外圈向内收缩 5 px，保留 80 px 拖拽命中区；
- 拖拽与未来“按住说话”手势冲突仍保持未决，Gate 3.1 不绑定真实 PTT 手势。

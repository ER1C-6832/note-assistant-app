# Gate 3 Assistant Preferences Spec

## 1. 目标

为语音模式和悬浮 UI 建立设备本地、版本化、可迁移的偏好存储，同时保持连接凭据、身份和产品 UI 偏好分离。

## 2. 不复用 RuntimeConfigStore

当前 RuntimeConfigStore 负责：

- identity；
- OTA / authorization / WebSocket endpoint；
- token、activation 状态；
- Fake Runtime 连接配置。

这些属于 Runtime 身份和连接配置。以下产品偏好不得继续塞入同一结构：

- 默认语音交互模式；
- 连续对话 idle timeout；
- 是否允许插话；
- 是否显示文字对话/输入；
- 悬浮按钮位置。

## 3. 存储路径

```text
%LOCALAPPDATA%\NoteAssistant\data\assistant_preferences.json
```

测试通过 AppPaths 注入临时路径。

## 4. Schema v1

```json
{
  "schema_version": 1,
  "voice_interaction_mode": "hold_to_talk",
  "streaming_idle_timeout_ms": 8000,
  "streaming_barge_in_enabled": false,
  "conversation_text_enabled": true,
  "text_input_enabled": true,
  "launcher_x_ratio": 1.0,
  "launcher_y_ratio": 1.0
}
```

### 默认值

- `hold_to_talk`：升级后不自动启动持续麦克风行为；
- `streaming_barge_in_enabled=false`：在无 AEC 的 PC 环境中避免把 TTS 外放误判为插话；
- launcher 默认右下角；
- panel expanded 和 Developer expanded 不持久化，启动时收起。

## 5. 字段边界

### 进入 AssistantState 的偏好

```text
voice_interaction_mode
streaming_idle_timeout_ms
streaming_barge_in_enabled
conversation_text_enabled（若产品 transcript 由 State 决定显示语义）
```

这些字段会影响 Runtime 行为，应通过 Controller 事件激活并由 Reducer 产生新 State。

### 仅 UI ViewModel 持有的偏好

```text
launcher_x_ratio
launcher_y_ratio
text_input_enabled（若只控制输入框可见性）
```

悬浮位置不属于 AssistantState，不进入协议、诊断状态机或恢复策略。

## 6. 所有权

```text
QML Settings / Overlay
-> AssistantViewModel or AssistantSettingsViewModel
-> command / preference service
-> AssistantPreferencesStore
```

语音模式必须走：

```text
UI command
-> Controller queue
-> VoiceInteractionModeRequested
-> Reducer
-> PersistAssistantPreferences effect
```

Store 完成后可以投递 persisted/failed 事件，但不得直接写 AssistantState。

悬浮位置可以由 UI ViewModel 节流保存，不需要进入 Runtime Event Pump；它只属于 UI shell。保存必须在 UI 拖动结束后进行，不按每一帧写文件。

## 7. 模式切换语义

### 非活动状态

- 更新 preferred mode；
- 原子写入 preferences；
- 不自动开始录音或连接。

### 连续会话活动时切换为 PTT

```text
request mode change
-> stop streaming session
-> invalidate streaming generation
-> stop capture / abort or stop listen
-> release microphone
-> state becomes connected/idle
-> persist hold_to_talk
```

### PTT 录音活动时切换为连续

产品 UI 暂时禁用模式切换；Controller 仍必须对程序化请求 fail-safe：终止 PTT、释放麦克风后再切换，不允许两个 capture owner 并存。

### disable / shutdown

偏好保留，但所有活跃会话和设备资源必须停止。下次启动只恢复“默认模式”，不自动恢复上次正在进行的连续会话。

## 8. 设置 UI

Gate 3.1 至少提供一个可复用的 `AssistantVoiceModeSettings` 组件：

```text
按住说话
连续对话
允许插话（仅连续模式可配置）
```

当前 PC 尚无完整设置页时，可以先把该组件放在悬浮面板的产品设置区域；后续设置页复用同一组件和 ViewModel，不复制状态或命令。

模式控件必须明确：

- 切换默认交互模式；
- 不等于立即开始录音；
- 连续模式真正可用取决于 capability；
- capability 未激活时不得伪装成功，需显示“正在开发/尚未就绪”或暂不显示可执行主操作。

## 9. 文件写入

- UTF-8 JSON；
- 临时文件 + replace 原子更新；
- schema/version 校验；
- 非法值回退到默认并记录脱敏 warning；
- 不打印 token、identity 完整值；
- 多次快速拖动用 debounce，最终位置必须 flush；
- shutdown 有界等待最后一次偏好写入。

## 10. 测试

- 默认文件不存在；
- v1 round-trip；
- 非法 enum 回退；
- 超范围 timeout clamp；
- 坐标 ratio clamp 到 `[0, 1]`；
- 连续活动时模式切换先停止 session；
- PTT 活动时不会产生第二个 capture；
- 保存失败形成可见但非致命配置错误；
- RuntimeConfig 中不新增 UI position 字段。

# Gate 2.0 Runtime 方向决策

## 1. 决策背景

PC 总计划要求参考 Android 已验证的 Assistant Runtime 架构，在一个 Python 进程内完成 Qt、qasync、状态机、WebSocket、音频、MCP 和本地便签能力。

本次补充决策用于消除一个歧义：

> Gate 2 不接音频，不代表 PC Runtime 可以省略 Android 已经拥有的完整状态、控制器能力和未来功能边界。

## 2. 冻结决策

### D2-001：功能完整性对齐 Android

PC 最终产品必须覆盖 Android 已有的相关能力：

- 启用、禁用；
- Fake/Real Runtime 调试切换；
- Device Identity；
- OTA/Activation；
- WebSocket hello/session；
- 文本对话；
- PTT；
- TTS；
- MCP；
- 自动重连和可见错误；
- 流式连续对话；
- VAD；
- 简单打断；
- system audio interruption/recovery；
- 麦克风所有权；
- KWS 协调；
- generation/cancellation；
- Runtime 诊断和性能指标。

不得以“快速验证”“减少工作量”“PC 可以简单一点”为理由删除上述契约。

### D2-002：分 Gate 实现不是能力裁剪

Gate 2 只真正执行：

- enable/disable；
- identity/activation；
- connect/hello；
- send text/receive text；
- disconnect/reconnect；
- error/shutdown。

但 Gate 2.1 即创建完整目标状态结构，并冻结后续 Gate 需要的事件、子状态和能力名称。未激活能力必须处于明确的 `inactive`、`disabled` 或 `not_ready` 状态，不允许从模型中消失。

### D2-003：语义照搬，内部结构不机械照搬

Android 当前 `LocalAssistantController` 已同时承担连接、PTT、连续对话、KWS、VAD、barge-in、麦克风租约、多组 Job 和 generation。PC 不将其机械翻译成一个巨大 Python 类。

PC 保留：

- 相同公开能力；
- 相同状态语义；
- 相同协议语义；
- 相同安全边界；
- 相同生命周期结果。

PC 改进内部结构：

```text
AssistantController facade
-> single event pump
-> ConversationReducer
-> EffectRunner
-> Session / Audio / MCP / Recovery coordinators
```

所有 coordinator 只能执行 Effect 或产生 Event，不能直接写 `AssistantState`。

### D2-004：完整 Runtime Snapshot

PC 对外暴露一个完整、版本化的 Runtime Snapshot。为了可维护性，Android 的扁平字段可映射到嵌套子状态，但每个字段必须有明确等价项，不得静默丢弃。

### D2-005：双端同步不复制瞬时 Runtime State

Android/PC 双端数据同步的对象主要是便签业务数据和经过分类的用户设置，不是瞬时连接状态。

绝不跨设备同步：

- session_id；
- reconnect attempt；
- 当前 phase；
- microphone owner；
- websocket token；
- device/client identity；
- 当前音频 generation；
- 当前 VAD 状态；
- debug trace。

需要单独评估同步：

- 便签及标签；
- 用户偏好；
- 默认对话模式；
- UI 设置；
- KWS 开关和模型偏好。

### D2-006：MCP 之前解决跨设备标识

PC 和 Android 当前都依赖本地自增主键。它们不能成为 MCP 返回值或未来同步标识。

在 Gate 5 MCP 真正对外创建、搜索、删除便签之前，必须完成跨设备稳定 ID 迁移，至少引入 `sync_id` UUID，并禁止协议层暴露本地数据库整数 ID。

## 3. 为什么不直接复制 Android Controller

原因不是省时间，而是并发正确性和长期一致性：

- Kotlin `Main.immediate + StateFlow` 与 Python `qasync + asyncio` 的执行模型不同；
- Android Controller 已经历 Phase 3～5 的持续叠加，直接翻译会把历史耦合一起复制；
- PC 还要与 Qt 生命周期、Windows 音频回调和单线程数据库 Executor 组合；
- 单事件泵可以比多个 callback 直接改 State 更严格地保证单写者；
- 分离 Effect Runner 后，Fake/Real Adapter 可以共用同一套状态转换测试。

因此：

> 复制行为契约和状态语义，不复制已经膨胀的类结构。

## 4. 否决条件

出现以下任一情况，Gate 2 设计应被否决：

- 为减少文件数量删掉后续音频/MCP/KWS 状态；
- Fake Runtime 使用另一套 StateMachine；
- QML 直接调用 WebSocket；
- WebSocket callback 直接修改 Qt Property；
- Controller 外有第二个 AssistantState 写入者；
- 用本地整数 note id 设计未来 MCP 返回协议；
- 将设备身份或 token 放入跨设备同步；
- 用“后面再说”逃避协议字段与 Android 的映射审计。

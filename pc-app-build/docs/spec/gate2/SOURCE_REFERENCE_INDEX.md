# Android 参考索引

基线 commit：`974a477ce1803efa130cc8b51a493b39796e0ca7`

## Runtime

- `assistant-runtime/.../controller/AssistantController.kt`
- `assistant-runtime/.../controller/LocalAssistantController.kt`
- `assistant-runtime/.../state/AssistantState.kt`
- `assistant-runtime/.../state/VoiceConversationState.kt`
- `assistant-runtime/.../conversation/ConversationStateMachine.kt`

## Protocol / Network

- `assistant-runtime/.../network/XiaozhiWebSocketClient.kt`
- `assistant-runtime/.../network/FakeXiaozhiWebSocketClient.kt`
- `assistant-runtime/.../protocol/XiaozhiMessageBuilder.kt`
- `assistant-runtime/.../protocol/XiaozhiMessageRouter.kt`
- `assistant-runtime/.../protocol/ProtocolEvent.kt`
- `assistant-runtime/.../recovery/ReconnectPolicy.kt`

## Activation / Identity

- `assistant-runtime/.../activation/OtaActivationClient.kt`
- Android Phase3 activation and protocol audit reports

## Audio ownership / Future gates

- `core-common/.../audio/MicrophoneOwnershipCoordinator.kt`
- Phase5 wake-word and voice conversation implementation reports

## Notes schema

- `notes-data/.../entity/NoteEntity.kt`

## 重要审计结论

- Text 使用 `listen/detect`；
- hello 必须带完整 audio params；
- hello 返回有效 session_id 才连接成功；
- binary frame 是音频；
- note mutation 在 Runtime 文本阶段 fail-closed；
- Android 当前 Runtime 完整状态包含音频、MCP、连续对话、VAD、KWS 协调相关字段；
- Android 与 PC 当前都没有可直接用于双端同步的稳定 note UUID。

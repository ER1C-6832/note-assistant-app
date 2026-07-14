# Gate 2 验收清单

## 架构

- [ ] `assistant/` 不依赖 PySide6。
- [ ] `AssistantController` 是 UI 唯一 Runtime 入口。
- [ ] Event pump 是 AssistantState 唯一写入者。
- [ ] Reducer 无 I/O、无 await、无 Qt。
- [ ] Bootstrap 是唯一 Composition Root。
- [ ] Fake/Real 使用同一 StateMachine、Builder、Router。
- [ ] 无 Sidecar、localhost HTTP、外部 py-xiaozhi Runtime。
- [ ] 完整 Android 状态语义均有 PC 映射。
- [ ] 后续能力处于明确 inactive/not_ready，而非从契约删除。

## 协议

- [ ] WebSocket headers 对齐。
- [ ] open 后发送 hello。
- [ ] hello 包含完整 audio params。
- [ ] 非空 session_id 才 Connected。
- [ ] 文本使用 listen/detect。
- [ ] invalid JSON -> ProtocolError。
- [ ] unknown JSON 不断线。
- [ ] binary frame 在 Gate 2 被类型化但不播放。
- [ ] MCP 修改工具 fail-closed。

## 生命周期

- [ ] disable during connect 不会被旧 hello 恢复连接。
- [ ] disable during reconnect 取消 timer。
- [ ] manual reconnect 与 auto reconnect 不并行。
- [ ] normal close 1000 不重连。
- [ ] abnormal close 有界重连。
- [ ] ApplicationLifecycle 关闭所有 Runtime tasks。
- [ ] Windows 启动/退出无 traceback、无残留 python 进程。

## 安全

- [ ] token、hmac key、Authorization 不进入 QML。
- [ ] protocol trace 脱敏。
- [ ] Fake 配置不覆盖 Real 配置。
- [ ] Gate 2 不导入 NoteCommandService。
- [ ] Gate 2 测试前后 Notes 数据内容一致。

## 双端兼容

- [ ] Runtime 瞬时状态标记为 device-local/not-syncable。
- [ ] 设备身份和 secret 标记为永不跨设备同步。
- [ ] 便签 MCP 不设计本地整数 ID 为外部标识。
- [ ] Android/PC note schema gap 已进入兼容计划。
- [ ] `sync_id` 迁移被列为 Gate 5 前置条件。

## 质量

- [ ] Black/Ruff/compileall 通过。
- [ ] StateMachine unit tests 通过。
- [ ] Scripted Transport integration tests 通过。
- [ ] qasync/QML offscreen smoke 通过。
- [ ] Fake Gate 全通过。
- [ ] Real Gate 有真实证据，或明确标记 blocked。

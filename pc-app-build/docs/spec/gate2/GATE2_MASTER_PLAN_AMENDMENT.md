# 对 PC Runtime 总计划的 Gate 2 补充条款

建议将下列条款加入总计划 Gate 2 章节：

1. Gate 2.1 建立完整目标 AssistantState，不只建立文本字段。
2. Gate 3～6.5 逐项激活完整 State 的音频、MCP、连续对话、VAD、KWS 子状态。
3. PC 最终控制器能力与 Android 对齐；内部可拆分，但不删公开语义。
4. Fake 与 Real Runtime 不允许分叉为两套 StateMachine。
5. Gate 2 不执行便签 MCP，但完整 MCP Runtime State 和协议 envelope 在 Gate 2 冻结。
6. Gate 5 前增加 Cross-device Readiness 前置条件，完成 sync_id 和跨端 Note Contract。
7. Runtime 瞬时状态、设备身份和 secret 明确禁止跨设备同步。
8. 对 Android 的有意协议差异必须写入 compatibility matrix 并真实验证。

# Gate 2 Real Acceptance 强制策略

## 冻结结论

Gate 2 的完成标准是 Real Gate，不是 Fake Gate。

Fake Runtime 的用途只有：

- 验证架构边界；
- 验证 Reducer 和 Event Pump；
- 复现错误与取消；
- 在服务端不可用时进行确定性单测。

Fake Runtime 不证明：

- OTA endpoint 兼容；
- activation HMAC 兼容；
- WebSocket Header 兼容；
- hello/session 兼容；
- 文本协议兼容；
- 真实断线行为兼容。

## Gate 2.7 必须提供的真实证据

```text
real_activation_verified = true
real_handshake_verified = true
real_text_verified = true
real_close_error_verified = true
```

并记录：

- endpoint 类型和测试日期；
- PC board/app 标识是否被服务端接受；
- WebSocket URL（可公开部分）；
- session_id 仅记录脱敏形式；
- 真实发送/回复的协议事件序列；
- close code/reason；
- 未通过项和服务端阻塞项。

## 状态标记

凭据或服务端暂不可用时，只能标记：

```text
Fake Gate complete
Real Gate blocked
Gate 2 incomplete
```

禁止写成：

```text
Gate 2 complete
Real verification optional
Fake acceptance equivalent to product acceptance
```

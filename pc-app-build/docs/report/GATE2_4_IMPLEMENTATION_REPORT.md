# Gate 2.4 文本回合实施报告

基线：`note-assistant-app@612721fc7957ed8cf8e162fd0170e828fb38c5a3`

## 1. 目标

Gate 2.4 在 Gate 2.3 已通过真实 hello/session 的单进程 Runtime 上完成：

```text
send_text -> listen/detect -> Thinking -> typed text/TTS events -> Connected
```

Fake 只用于确定性回归。`RUN_GATE2_4_REAL_TEXT.ps1` 从真实服务端收到可读文本并返回 0，才算 Real Gate 通过。

## 2. 运行时边界

没有新增进程、事件循环、本地 HTTP 服务或外部 PC Xiaozhi Runtime。全部状态更新仍经过：

```text
Controller -> bounded queue -> single event pump -> reducer -> effect
-> RuntimeTransportRouter -> Real/Fake transport -> typed event -> event pump
```

Fake 和 Real 共用 `XiaozhiMessageBuilder` 与 `XiaozhiMessageRouter`。

## 3. 协议与并发

文本发送继续使用 Android 已验证的 `listen/detect`：

```json
{"session_id":"...","type":"listen","state":"detect","text":"用户输入"}
```

每轮分配单调递增的本地 `turn_token`。同一 session 只允许一个 active text turn；快速连续发送 fail-closed，错误码为 `text_turn_in_progress`。所有消息仍经过 Gate 2.3 的唯一 sender queue。

服务端协议不会回显 PC 本地 `turn_token`。因此本实现不声称服务端级强关联：Transport 将当时唯一的 active token 附加到 typed receive event，并结合单回合策略、发送完成屏障、session 校验和 completion 窗口拒绝迟到事件。后续若协议提供服务端 turn id，应改为显式关联。

## 4. Transcript 规则

| 消息 | 产品状态规则 |
|---|---|
| 用户提交文本 | 写入 `last_user_text` |
| `stt.text` | 写入 `last_stt_text`，不覆盖文本输入 |
| `llm.text` 可读正文 | 合并至助手回复 |
| `llm.text` 纯表情/情绪标记 | 仅记录 protocol event |
| `text.text` | 合并至助手回复 |
| `tts.text` | 合并至助手回复；Gate 4 前不播放 |
| invalid/unknown JSON | 仅进入脱敏 protocol diagnostics |
| 二进制音频 | 只记录 typed metadata；Gate 4 前不播放 |

产品 transcript 与协议 debug JSON 分离。文本合并会去除相同片段、前缀扩展和重叠后缀造成的重复。

## 5. 回合完成

回合可由终止 TTS、可读文本 settle、非文本 TTS fallback 或响应超时完成。完成后清除 active token 并保持 Connected。Gate 4 前不进入虚假的 Speaking/Playing。

## 6. 安全

- Token、Authorization、HMAC 和 challenge 不进入公开 State；
- URL 移除 query、fragment 和用户信息；
-真实脚本不打印完整 identity/session；
-自定义 prompt 不回显，只打印字符数；
-助手回复最多打印 500 字符；
-协议 trace 递归脱敏。

## 7. 验收

自动累计验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE2_4.ps1
```

真实文本验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE2_4_REAL_TEXT.ps1
```

可选 prompt：

```powershell
$env:NOTE_ASSISTANT_GATE2_4_TEXT = "请用一句话说明当前时间。"
```

退出码：

```text
0 = 真实 hello/session 有效，listen/detect 已发送，收到可读助手文本
2 = Gate 2.2/2.3 凭据、激活或 session 不可用
1 = 网络、协议、超时或文本验证失败
```

成功必须同时满足 `real_handshake_verified=true`、`real_text_verified=true`、`assistant_text` 非空且 `status=text_verified`。

## 8. 未提前实现

本 Gate 不实现音频播放、PTT、自动重连、MCP 便签执行、QML Assistant 面板、连续对话、VAD、barge-in 或 KWS。

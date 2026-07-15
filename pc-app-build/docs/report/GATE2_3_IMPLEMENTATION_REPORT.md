# Gate 2.3 实施报告：真实 WebSocket hello/session

## 结论

Gate 2.3 接通真实 WebSocket 握手、客户端 hello、服务端 hello/session、typed receive、单发送者、二进制路由以及关闭码/原因。自动化 Fake/脚本测试不能替代真实服务端验收。

Gate 2.3 只有在 `RUN_GATE2_3_REAL_WEBSOCKET_HELLO.ps1` 返回 0，并输出 `real_handshake_verified=true` 时，才能标记 Real hello/session 通过。

## 真实连接字段

握手 Headers：

- `Authorization: Bearer <persisted websocket token>`
- `Protocol-Version: 1`
- `Device-Id: <persisted identity>`
- `Client-Id: <persisted identity>`

客户端 hello：

```json
{"type":"hello","version":1,"features":{"mcp":true},"transport":"websocket","audio_params":{"format":"opus","sample_rate":16000,"channels":1,"frame_duration":20}}
```

Socket 打开不等于 Connected。只有 Router 收到 `type=hello` 且 `session_id` 非空后，Reducer 才进入 Connected，并设置 `gate_real_handshake_verified=true`。

## 并发模型

- 一个真实 socket generation；
- 一个 receiver loop；
- 一个容量 64 的发送队列；
- 一个 sender loop 是唯一 `connection.send()` owner；
- hello、文本以及未来协议消息都经同一队列；
- Controller 的 OpenTransport effect 是所有内部 socket task 的根任务；
- disable、切换模式、disconnect 和 shutdown 会取消根任务并关闭 socket；
- generation 拒绝迟到的 hello、关闭和协议事件。

## Router 行为

- `hello` -> ServerHello；
- `stt` / `llm` / `text` -> AssistantText；
- `tts` -> TtsState；
- `listen` -> ListenState；
- `mcp` -> McpEnvelope，Gate 5 前不执行便签修改；
- unknown JSON -> UnknownJson，保持连接；
- invalid JSON -> ProtocolError，保持连接；
- binary -> BinaryAudio，仅记录长度，Gate 4 前不播放。

所有诊断 JSON 对 token、authorization、HMAC、challenge、secret 等字段递归脱敏。

## 依赖选择

使用 `websockets>=16.0,<17`：

- Python 3.10 支持；
- asyncio 原生；
- 支持额外握手 Header；
- 支持 text/binary route；
- 支持 close code/reason；
- 接收取消语义明确；
- 不创建第二事件循环或第二进程。

TLS 使用系统默认验证，不复刻旧客户端关闭证书验证的做法。

## Gate 边界

本 Gate 不声明以下能力完成：

- 真实文本回合产品语义：Gate 2.4；
- 自动重连：Gate 2.5；
- QML AssistantPanel：Gate 2.6；
- 音频上传和播放：Gate 3/4；
- MCP notes 执行：Gate 5。

## 自动化验证记录

本地 Gate 2 基线验证：

- Gate 2.1～2.3：65 passed；
- Gate 1.7 外部 Runtime/第二进程禁用检查：2 passed；
- Black 24.10.0：50 Python 文件保持不变；
- Ruff 0.9.10：通过；
- compileall：通过；
- Python 3.10 AST：通过；
- `pyproject.toml` TOML 解析及 websockets 依赖范围：通过。

当前容器无法解析 `github.com`，且本地重建基线不包含 Gate 1.1～1.6 的完整源码与测试，
因此本地未声称完成 Gate 1.1～1.7 全量回归。仓库根目录的 `VERIFY_GATE2_3.ps1`
会在完整工作树中运行 Gate 1.1～1.7、Gate 2.1、Gate 2.2、Gate 2.3 的累计测试。

## Real Gate 状态

交付时状态为：

```text
Automated Gate complete
Real WebSocket hello/session pending user-machine verification
```

不得仅凭 scripted connector 测试把 Gate 2.3 标记为 Real complete。

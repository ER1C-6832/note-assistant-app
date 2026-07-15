# Gate 2.2 Identity / Config / Activation 实施报告

## 1. 基线与范围

实现基线：`note-assistant-app@5a11ff3`。

本阶段严格对应 `docs/spec/gate2/GATE2_IMPLEMENTATION_PLAN.md` 的 Gate 2.2：

- 稳定 Device Identity；
- 版本化 Runtime Config；
- Fake Activation；
- 真实 OTA / Activation Adapter；
- optional activation required；
- HMAC-SHA256 challenge；
- 脱敏诊断；
- Controller 单事件泵接线。

本阶段不实现真实 WebSocket、文本协议 Router、PTT 或 TTS。它们分别属于 Gate 2.3、2.4、3、4。

## 2. 已实现模块

```text
app/assistant/
├─ runtime_config.py
├─ identity/
│  ├─ models.py
│  ├─ store.py
│  └─ manager.py
└─ activation/
   ├─ models.py
   ├─ parser.py
   ├─ client.py
   └─ fake_client.py
```

### 2.1 RuntimeConfigStore

配置文件：

```text
%LOCALAPPDATA%\NoteAssistant\data\assistant_runtime.json
```

特性：

- `schema_version=1`；
- JSON 原子替换；
- 同进程线程锁；
- 最佳努力设置私有文件权限；
- 未知 schema fail-closed，不静默覆盖；
- Fake 与 Real 配置分区；
- identity reset 保留 OTA/授权 endpoint，但清除身份绑定 token、session 配置和激活状态。

### 2.2 Device Identity

持久化：

- `device_id`：随机本地管理 MAC 形式；
- `client_id`：UUID；
- `serial_number`：UUID hex；
- `hmac_key`：256-bit 随机值；
- `generation`：身份重置版本。

公开 State 只保存脱敏后的 device/client id，不保存 serial、HMAC 或 token。

### 2.3 Fake Activation

Fake Activation：

- 复用真实 identity manager；
- 只写 `config.fake`；
- 不覆盖 `config.real`；
- 返回脱敏诊断；
- 只有切换到 Fake Runtime 后才允许执行。

### 2.4 Real OTA / Activation

真实 Adapter 使用 stdlib `urllib`，通过 `asyncio.to_thread` 执行阻塞 HTTP，不阻塞 qasync/Qt 主循环。

OTA Header：

```text
Device-Id
Client-Id
Content-Type: application/json
User-Agent: windows/note-assistant-pc-0.1.0-gate2.2
Accept-Language: zh-CN
Activation-Version: 0.1.0-gate2.2  # activation_version=v2
```

PC 有意平台差异：

```text
board.type = windows
board.name = note-assistant-pc
```

真实流程：

```text
首次运行
-> POST OTA
-> 保存 websocket URL/token
-> 无 activation：Activated
-> 有 activation：Required，显示 code/authorization URL

用户完成授权后再次运行
-> POST /activate
-> HMAC-SHA256(challenge, identity.hmac_key)
-> HTTP 202：仍 Required
-> HTTP 200：重新 POST OTA 刷新 WebSocket 配置
-> Activated
```

不进行一分钟阻塞轮询。每次用户操作只完成一个有界真实检查。

### 2.5 Controller / Reducer

以下能力从 `not_ready` 激活为 `active`：

```text
identity
activation
```

Controller 仍遵守：

```text
command
-> Event Pump
-> pure reducer
-> Effect
-> adapter
-> result Event
-> Event Pump
```

身份和激活 Adapter 不直接写 `AssistantState`。

补充并发保护：

- disable/shutdown 取消激活任务；
- Runtime 模式切换取消正在执行的激活；
- 重复激活请求不启动并行任务；
- identity reset 取消旧 effect、关闭旧 transport generation、清除身份绑定凭据；
- Fake/Real Activation 模式不匹配时 fail-closed。

## 3. 安全边界

以下内容不会进入公开 State、普通日志或 QML：

- WebSocket token；
- HMAC key；
- activation challenge；
- Authorization Header；
- serial number 完整值。

OTA 调试 JSON 会递归脱敏：

```text
token
challenge
hmac
hmac_key
secret
key
authorization
```

真实 HTTP 错误若疑似包含上述字段，响应正文整体隐藏。

## 4. 测试

Gate 2.1 + Gate 2.2 本地结果：

```text
45 passed
Black 通过
Ruff 通过
compileall 通过
Python 3.10 AST 通过
warnings-as-errors 通过
```

覆盖：

- identity 重启稳定；
- reset generation；
- reset 清除身份绑定凭据；
- Runtime Config schema；
- OTA parser；
- token/challenge 脱敏；
- PC OTA headers/payload；
- activation required；
- HMAC 请求；
- activation 202/200；
- Fake 不污染 Real；
- Controller 单写者；
- disable/mode switch 取消激活；
- 重复激活不并行；
- disabled 状态下 identity/activation 不破坏不变量。

## 5. 真实验收入口

设置环境变量：

```powershell
$env:NOTE_ASSISTANT_OTA_URL = "https://..."
$env:NOTE_ASSISTANT_AUTHORIZATION_URL = "https://..."
$env:NOTE_ASSISTANT_ACTIVATION_VERSION = "v2"
```

可选测试数据目录：

```powershell
$env:NOTE_ASSISTANT_DATA_ROOT = "C:\temp\NoteAssistant-Gate22"
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE2_2_REAL_ACTIVATION.ps1
```

退出码：

```text
0 = 真实 endpoint 已返回 Activated
2 = 真实 endpoint 返回 activation_required，需要完成授权后再次运行
1 = 真实路径失败
```

控制台只输出脱敏 identity、公开 URL、激活码和授权 URL，不输出 token/HMAC/challenge。

## 6. Gate 2 完成状态

本报告只能声明：

```text
Gate 2.2 implementation complete
Gate 2 real acceptance not yet complete
```

Gate 2 最终完成必须在 Gate 2.7 同时满足：

- 真实 OTA/Activation；
- 真实 WebSocket Header；
- 真实 hello/session_id；
- 真实文本发送与回复；
- 真实关闭/错误恢复；
- 协议兼容矩阵更新。

Fake Gate 通过不能替代 Real Gate。

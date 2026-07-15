# Gate 2.7 Final Acceptance Report

基线提交：`2faaf859f3efd29508babb22c50623cf5939aef4`

验收修复基线：`1f0ea9ff38e0204f62bc2e418b1b9cd04236de12`

## 1. 范围

Gate 2.7 不新增第二套 Runtime，也不修改 Notes 写入路径。它把 Gate 2.1～2.6 已冻结的实现收束为两个独立、可审计的验收结果：

```text
Automated + Fake Gate
Real Gate
```

只有二者都通过，才允许声明 Gate 2 完成。

## 2. Automated / Fake Gate

入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE2_7.ps1
```

该脚本 fail-fast 执行：

- 依赖、compileall、Black、Ruff；
- Gate 1.7 与 Gate 2.1～2.7 全部自动化测试；
- 完整 State 默认值；
- Fake identity/activation，且不污染 Real 配置；
- Fake hello/session 与文本回合；
- invalid/unknown JSON 脱敏且不断线；
- MCP notes 工具调用 `blocked_not_ready`；
- 异常关闭、单 timer、有界自动重连与新 generation；
- disable/shutdown 后无 Runtime task；
- Assistant Runtime 全流程不改 `notes.db`；
- 离屏 QML 加载与有界生命周期关闭。

Gate 2.6 的历史 UI smoke 契约固定在：

```text
pc-app-build/tools/verify_gate2_6_ui_smoke.py
```

不要求根目录永久保留旧 Gate runner 文件名。

脚本返回 `0` 时，唯一允许的结论是：

```text
Fake Gate complete
```

## 3. Real Gate

入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE2_7_REAL_ACCEPTANCE.ps1
```

该脚本在同一个 Python 进程、同一个 asyncio/qasync 架构边界内验证：

- 稳定 identity；
- 真实 OTA / activation；
- Authorization、Protocol-Version、Device-Id、Client-Id headers；
- 真实 WebSocket hello/session；
- 真实文本回复；
- 真实 `1012` 异常关闭；
- 新 generation 的真实 hello/session 恢复；
- recovery 期间 activation 只执行一次；
- 输出仅包含脱敏 identity/session 和公开 URL。

服务端会截断超过十个字符的文本输入。Real acceptance 默认发送 `回复验收通过`，并在发送前把 `NOTE_ASSISTANT_GATE2_7_TEXT` 自定义文本限制为最多十个字符，避免验收因服务端截断而长时间等待。

返回码：

```text
0 = Real Gate complete
2 = Real Gate blocked
1 = Real Gate failed
```

凭据、激活或服务不可用时，只能标记：

```text
Fake Gate complete
Real Gate blocked
```

不得声称 Gate 2 全完成。

## 4. 架构不变量

- `AssistantController` 仍是唯一 AssistantState writer；
- Transport / timer / QML 只投递事件，不直接改 State；
- 单 Event Pump、单 sender、单 receiver、单 reconnect timer；
- 无 sidecar、localhost HTTP、subprocess 或第二 Python 业务进程；
- QML 不维护第二套 phase/connection；
- Gate 2 MCP 只解析并 fail-closed，不访问 Notes DB；
- PTT、播放、连续对话、VAD、Barge-in、KWS 保持 `not_ready`。

## 5. 交付文件

```text
VERIFY_GATE2_7.ps1
RUN_GATE2_7_REAL_ACCEPTANCE.ps1
pc-app-build/tools/verify_gate2_7_fake_acceptance.py
pc-app-build/tools/verify_gate2_7_real_acceptance.py
pc-app-build/tests/gate2_7/
pc-app-build/docs/report/GATE2_7_FINAL_ACCEPTANCE_REPORT.md
pc-app-build/docs/spec/gate2/GATE2_PROTOCOL_COMPATIBILITY.md
```

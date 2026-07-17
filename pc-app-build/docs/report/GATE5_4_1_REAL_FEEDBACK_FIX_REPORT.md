# Gate 5.4.1 Real Feedback Fix Report

状态：修复候选。
基线：`ddc287c656fd151fc7643d44c1be30e1b08a3fac` (`gate5 acceptance`)。

## 用户真实证据

- Windows 自动部分全部通过。
- 绝大多数真实语言工具和 UI 路径正常。
- 偶发连接异常后能够重连，并且没有自动重放工具调用。
- 发现纯数字标题 `119` 被 resolver 错误优先解释为 `note_id=119`。
- 桌面 UI 缺少独立待办导航工具。

## 修复

- 删除“纯数字 query 自动当 ID”的兼容分支。
- 新增数字标题与明确 ID 冲突回归测试。
- 新增 `ui.show_todos` descriptor、executor、typed command、Qt adapter 和 QML 导航。
- 所有 registry、protocol、acceptance catalog 和 freeze verifier 修订为 32 tools。
- 保持 reconnect 不 replay 的现有安全行为。

## 复测命令

```powershell
python -m pytest -W error tests
python tools/verify_gate5_0_protocol.py
python tools/verify_gate5_1_read_ui.py
python tools/verify_gate5_4_freeze.py
```

真实复测：

```text
帮我找到标题叫119的便签，给它加上 Gate54标签。
把桌面界面切到待办列表。
```

## 本地验证

```text
compileall: passed
Black: 18 modified Python files unchanged
Ruff: passed
Gate 5.4 architecture: 5 passed
isolated numeric-title/id routing: passed
isolated ui.show_todos typed dispatch + Qt adapter + QML contract: passed
acceptance catalog count: 32
serialized tools/list: 16633 bytes
```

当前容器不是完整 Windows 工作树，因此未代替用户运行完整 pytest、真实连接或真实 QML 音频会话。

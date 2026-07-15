# Gate 2.6 AssistantViewModel / QML 实施报告

基线提交：`87416e3f7e781accf07a5c24ebcb925bc07b7fd3`。

## 交付范围

- 新增 `ui/assistant_view_model.py`，把不可变 `AssistantState` 投影为 Qt Property；
- 新增 `qml/components/AssistantPanel.qml`；
- 在 `bootstrap.py` 中组装唯一 `AssistantController`、真实/Fake Transport、Identity、Activation 与 Recovery；
- 把 `assistantViewModel` 注入同一个 `QQmlApplicationEngine`；
- 把 Assistant ViewModel 与 Controller 纳入 `ApplicationLifecycle` 有界关闭；
- 新增 Gate 2.6 架构、ViewModel 和离屏 QML smoke 验收。

## 普通用户功能

- 启用/关闭助手；
- 连接、断开和错误重试；
- 显示 phase、连接状态和 Runtime 状态文本；
- 文本发送；
- 显示最近用户文本和助手回复；
- 显示结构化 Runtime 错误。

## Developer 折叠区

- Real / Scripted Fake Runtime 切换；
- 脱敏 device/client/session；
- Fake/Real Activation；
- 身份重置；
- 自动重连诊断；
- 脱敏协议事件与 JSON；
- 模拟异常断线和 Transport failure；
- 完整 capability registry。

## 并发与状态约束

- ViewModel 不创建第二套 phase、connection 或 recovery 状态；
- 所有命令只调用 `AssistantController` 公共 API；
- Runtime State 仍只有 event pump 一个写入路径；
- Qt、qasync、Notes DB 与 Assistant Runtime 运行在同一个 Python 进程；
- 不引入 Sidecar、localhost HTTP、FastAPI、subprocess 或第二事件循环；
- ViewModel 关闭先取消 UI command task 并解除订阅，随后 Controller 按 Gate 2.5 顺序关闭。

## 未提前暴露

Gate 3+ 的 PTT、麦克风、播放按钮以及 Gate 6.5 KWS 产品入口没有出现在普通 UI 或 Developer UI 中。

## 验收

自动验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE2_6.ps1
```

离屏 QML 与生命周期 smoke：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE2_6_UI_SMOKE.ps1
```

最终视觉布局仍需在 Windows 桌面实际启动应用确认；自动 smoke 只证明 QML 可加载、Assistant Runtime 已注入且退出有界。

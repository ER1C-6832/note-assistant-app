# Gate 1.7 全量回归修复

## 问题

Gate 1.6 架构测试仍要求旧写法 `notesViewModelRef: notesViewModel`，但 QML 关闭阶段空值修复后，`Main.qml` 已统一通过 `root.viewModel` 显式传递 ViewModel。

## 修复

- 不回退 `Main.qml`。
- 更新 Gate 1.6 测试，验证 `readonly property var viewModel: notesViewModel`。
- 要求四个子页面继续显式接收 `notesViewModelRef: root.viewModel`。

## 验证

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_7.ps1
```

预期 Gate 1.1～1.7 全量测试通过。

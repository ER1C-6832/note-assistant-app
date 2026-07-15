# Gate 2.4 verifier compatibility fix

修复 Gate 2.3 架构测试固定依赖 VERIFY_GATE2_3.ps1 的问题。

当前 Gate 验收脚本会持续演进，因此测试改为检查当前 VERIFY_GATE*.ps1 中覆盖 gate2_3 的脚本。

不修改 Runtime、WebSocket、Text Turn 实现。

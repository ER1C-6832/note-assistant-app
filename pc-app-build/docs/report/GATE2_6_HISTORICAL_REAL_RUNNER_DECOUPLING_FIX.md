# Gate 2.6 historical Real runner decoupling fix

基线提交：`92adde1a85b09a073db84033fc99d282af62e6c4`。

修复 Gate 2.3、2.4、2.5 架构测试仍要求根目录存在 `RUN_GATE2_*_REAL_*.ps1` 的问题。

历史 Real Gate 的长期验收资产是 `pc-app-build/tools/verify_gate2_*` Python 工具；根目录 PowerShell runner 属于当前交付入口，可随 Gate 演进替换。Gate 2.6 使用 UI smoke runner，不应为了历史测试保留已经退出当前交付面的 Real runner。

变更仅涉及历史架构测试和本报告：

- 保留当前 `VERIFY_GATE*.ps1` 对历史测试目录的覆盖与 fail-fast 检查；
- 保留 Gate 2.3、2.4、2.5 Python Real 验收工具存在性检查；
- 移除对任意根目录 Real runner 文件名或命名模式的依赖；
- 不修改 Runtime、Recovery、WebSocket、AssistantViewModel 或 QML。

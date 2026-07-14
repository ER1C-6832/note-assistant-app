# Gate 1.7 验收修复报告

基线提交：`211fc45dbe74348e52f4410761e99e3f9f4804f9`。

## 修复内容

- 格式化 Gate 1.7 的两个测试文件，Black 检查不再失败。
- 架构扫描不再把 SQLite `-wal` / `-shm` companion file 的局部变量误判为旧 Sidecar 进程架构；仍检查明确的 Sidecar 客户端、进程和 URL 模式。
- 修正 CRUD 回归断言：编辑后原搜索词不再匹配时，当前搜索结果应清空；数据更新改由 QueryService 验证。
- `Main.qml` 对 ViewModel 销毁阶段增加完整空值保护，关闭窗口时不再读取空对象的 `selectedIndex` 等属性。
- `VERIFY_GATE1_7.ps1` 对每个 Python 命令检查退出码，任一步失败立即以退出码 1 结束，不再误报通过。

## 验证

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE1_7.ps1
```

只有依赖、compileall、Black、Ruff 和 Gate 1.1～1.7 pytest 全部成功后，脚本才会输出 `Gate 1 automated acceptance passed.`。

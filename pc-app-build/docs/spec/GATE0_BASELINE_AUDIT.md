# Gate 0 基线审计

状态：通过，可开始 Gate 0  
审计日期：2026-07-14  
分支：`rewrite/single-process-runtime`

## 已确认

重写分支相对 `master` 已完成结构性删除：

- `services/`
- `integrations/`
- `scripts/`
- `pc-app-build/docs/` 旧文档
- Sidecar 客户端
- Notes API 客户端
- py-xiaozhi 集成和补丁
- 登录预热、进程扫描和多进程启动逻辑
- 旧 Assistant 页面、面板和设置页

应用入口当前是有意保留的空白 bootstrap，占位状态不会误启动旧 Runtime。

## 当前非阻塞残留

远端检查时仍能看到以下轻量残留：

1. `VoiceButton.qml` 是未接线的中性占位组件；
2. `TopBar.qml` 仍保留未使用的 `notesControllerRef/apiBusy`；
3. `Sidebar.qml` 仍保留未使用的 `currentPage/pageRequested`；
4. 两份 `requirements.txt` 与 `pyproject.toml` 存在重复依赖声明。

这些不包含 Sidecar、py-xiaozhi、Notes API 或多进程语义，不阻塞 Gate 0。Gate 1 恢复手动便签时应顺手删除。

## Gate 0 禁止重新引入

- Sidecar
- 外部 py-xiaozhi Runtime
- localhost REST 业务热路径
- 控制轮询
- Runtime 进程管理器
- QML 直接操作 WebSocket、音频或数据库
- Assistant Core 依赖 PySide6

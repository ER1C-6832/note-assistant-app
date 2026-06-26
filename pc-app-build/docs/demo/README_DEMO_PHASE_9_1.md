# Phase 9.1 Demo 数据与 Mock 模式

## 种子数据

```bat
scripts\seed_demo_notes.bat
```

会创建带有 `demo-seed` 标签的演示便签。

清理演示数据：

```bat
scripts\reset_demo_data.bat
```

只删除带 `demo-seed` 标签的便签。

## Mock 语音桥接

```bat
scripts\start_sidecar_mock.bat
```

Mock 监听：

```text
ws://127.0.0.1:17890/assistant
http://127.0.0.1:17891/api/health
```

## 一键 Mock 演示

```bat
scripts\start_demo_mock_mode.bat
```

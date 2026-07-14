# ADR-001：单进程与 qasync

状态：Accepted for Gate 0

## 决策

PC 验证版采用单 Python 进程，并在 Qt 主线程中使用 qasync 驱动 asyncio。

## 原因

消除 Sidecar、IPC、轮询和多进程启动；WebSocket 是异步 IO；PortAudio 和 libopus 在原生层工作；QML 状态更新属于 Qt 主线程。

## 后果

callback 和数据库必须有严格所有权；event loop 不执行阻塞 IO；需要 bounded queue 和 generation token；若性能不足，必须用 Gate 7 数据证明后再考虑拆进程。

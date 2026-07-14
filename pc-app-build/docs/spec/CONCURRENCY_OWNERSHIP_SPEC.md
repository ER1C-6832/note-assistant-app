# Concurrency and Ownership Spec

状态：Gate 0 冻结候选

## 1. 事件循环选择

采用 `Qt 主线程 + qasync asyncio event loop`，不在后台线程再创建第二个长期 asyncio loop。

## 2. 执行域

| 执行域 | 所有者 | 允许工作 | 禁止工作 |
|---|---|---|---|
| Qt/qasync 主线程 | Bootstrap、Controller | 状态机、WebSocket 协调、MCP 路由、UI 信号 | 阻塞 DB、阻塞音频、CPU 密集编码 |
| PortAudio callback | sounddevice | 复制固定长度 PCM、投递线程安全事件 | JSON、网络、DB、QML、日志格式化 |
| Audio worker | AudioEngine | Opus 编解码、帧统计 | 修改 AssistantState、操作 QML |
| Playback callback | sounddevice | 从播放缓冲读取 PCM | 网络、状态转换、DB |
| DB executor 单线程 | Repository | SQLAlchemy/SQLite | QML、WebSocket、音频 |

## 3. 队列

Capture ingress：20ms PCM16，容量 8 帧；满时丢弃最旧帧并计数，callback 不等待。

Encoded uplink：容量 16 包；满时结束当前采集并进入可见错误，不允许无限堆积。

Playback：目标 80～200ms，硬上限 1 秒；超过上限记录 overflow，清空旧 generation 并停止本次播放。

Runtime event queue：容量 256，只放小型不可变事件，不放 PCM。

## 4. WebSocket 所有权

只有 qasync loop 中的 `WebSocketClient` 可以创建连接、发送文本/二进制和关闭连接。音频线程不得直接调用 socket。所有 send 由单一发送 Task 或 async Lock 串行化。

## 5. State 所有权

只有 Controller 调用 StateMachine。StateMachine 不读文件、不访问网络、不操作音频、不调用 Qt、不写数据库。

## 6. 数据库所有权

SQLAlchemy Session 不跨线程共享。每个 DB executor 调用使用自己的 Session，所有写操作串行化。UI 和 MCP 都调用同一个 `NoteCommandService`。

## 7. Generation Token

录音和播放各自递增 generation。stop/cancel/abort 使旧 callback 自动失效，解决残留 callback、旧 TTS 包、旧 socket 事件和快速连续点击。

## 8. 取消与关闭

Controller 跟踪 reconnect、receive、uplink、capture、playback、metrics flush 等长期任务。`shutdown()` 设置 closing，取消并有界等待，再关闭设备、socket 和 executor。禁止 fire-and-forget 长期任务。

## 9. GIL 结论

PortAudio、libopus、async 网络和 SQLite executor 不依赖 Python 多线程执行大量 Python CPU 代码。GIL 不是引入多进程的默认理由；性能不足必须由 Gate 7 数据证明。

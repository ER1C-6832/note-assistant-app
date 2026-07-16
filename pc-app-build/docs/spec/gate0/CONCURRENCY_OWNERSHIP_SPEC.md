# Concurrency and Ownership Spec

状态：Gate 0 历史冻结基线；Gate 3.4 增补当前实现注记。

> 历史说明：Gate 0 冻结时音频 adapter 候选为 sounddevice。该历史验收事实不被改写。当前实现已经由 ADR-007 选择 PyAudio/PyAV；下表以“当前实现”标识现状。

## 1. 事件循环

采用 Qt 主线程 + qasync asyncio event loop。不在后台线程创建第二个长期 asyncio loop。

## 2. 执行域

| 执行域 | 所有者 | 允许工作 | 禁止工作 |
|---|---|---|---|
| Qt/qasync 主线程 | Bootstrap、AssistantController | 单事件泵、Reducer、WebSocket 协调、UI signal | 阻塞 DB、阻塞设备、CPU 密集编码 |
| PortAudio callback（当前 PyAudio） | PyAudio adapter | 复制 20ms PCM、非阻塞投递 | JSON、网络、DB、QML、状态写入 |
| Audio worker | AssistantAudioEngine | PyAV Opus 编码、VAD、统计 | 修改 AssistantState、QML、socket send |
| qasync uplink task | EffectRunner | 从 bounded packet queue 读取并调用单 sender | 编码、设备 callback、第二 socket owner |
| Playback callback（Gate 4） | future PyAudio output adapter | 读取 playback buffer | 在 Gate 3 提前实现播放/续轮 |
| DB executor 单线程 | Repository | SQLAlchemy/SQLite | QML、WebSocket、音频 |

## 3. 队列

- Capture ingress：20ms PCM16，容量 8，满时 drop-oldest 并计数；callback 不等待。
- Encoded uplink：容量 16，满时失败当前 turn；不得无限堆积。
- Runtime event queue：容量 256，只放小型不可变事件，不放 PCM。
- Playback queue：属于 Gate 4；Gate 3 不创建 output stream。

## 4. 所有权

- 只有 AssistantController 调用 StateMachine 并发布新 AssistantState；
- WebSocket sender 只有一个；
- PTT 与 streaming 共用一个 AudioEngine；
- 一个进程最多一个逻辑 microphone lease；
- DB Session 不跨线程共享；
- UI/MCP 共用 NoteCommandService。

## 5. Generation / session / turn

connection、streaming、capture、playback（Gate 4）generation 各自递增。服务端 session_id、本地 streaming UUID 和 turn token 都必须匹配当前 owner。stop/cancel/disable/shutdown 使旧 callback 无效。

## 6. 幂等与关闭

stop、finalize、timer cancellation、task cancellation、capture close 和 lease release 必须幂等。单事件泵决定 response timeout、stop、disconnect 的顺序；迟到事件不得恢复 capture。

正常 session stop 可保留 connected transport。disable/shutdown 必须取消 reconnect/streaming timer、uplink、VAD、capture、worker、lease、sender/receiver 和 pending assistant task。

## 7. 单进程结论

应用/runtime 不导入或启动 subprocess/multiprocessing Python 助手进程。PortAudio native callback、one audio worker 和 DB executor 是同一进程内执行域。验收脚本顺序启动短生命周期 Python 命令不属于第二 Runtime。

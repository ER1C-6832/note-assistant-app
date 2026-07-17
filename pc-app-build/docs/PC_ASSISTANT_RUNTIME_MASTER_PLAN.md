# PC 小智语音助手单进程重写总计划

> 文档定位：本文件是 PC 端单进程 Runtime 重写的长期权威计划。  
> 当前代码基线：`2bd25c3677cf2aecd2784d089e8f971c40bb377e`。  
> Gate 5 的 32-tool Windows Automated/Fake/Real 结果由用户于 2026-07-17 完成验收；Gate 6 规划在该事实基础上制定。  
> Gate 3/4 修正案继续作为历史记录；Gate 6 修正案的有效决策已并入本文件。

规范优先级（发生冲突时从高到低）：

1. 当前代码已经实现、且由冻结测试证明的架构不可变量；
2. 本总纲中已经并入的当前决策；
3. 当前 Gate 的冻结 Spec 与测试/验收计划；
4. 已接受且未被 superseded 的 ADR；
5. 实施计划；
6. Delivery Report；
7. 历史基线、旧报告和旧 runner 名称。

历史测试与当前能力冲突时，应修正历史测试契约，不得回退已经正确激活的 runtime 能力。

---

## 1. 项目背景

现有 PC 端曾采用多进程、Sidecar、本地 HTTP、外部 py-xiaozhi Runtime 等组合架构，带来了多进程生命周期复杂、本地控制链路延迟、状态分散、异常恢复困难和历史兼容层不断增长等问题。

本次重写目标不是继续修补旧架构，而是：

> 参考 Android 已验证成功的 Assistant Runtime 架构，在 PC 上重新实现一套单进程、低延迟、可测试、可观测的桌面语音助手。

---

## 2. 总体目标

最终 PC 应用在一个 Python 进程内完成：

- PySide6 / QML 桌面 UI；
- qasync 事件循环；
- Assistant 状态机；
- WebSocket；
- 麦克风采集；
- Opus 编解码；
- TTS 播放；
- MCP 工具调用；
- 本地便签数据库；
- 连续对话；
- 可选 KWS；
- 延迟指标记录。

最终链路：

```text
QML
-> Qt ViewModel
-> AssistantController
-> StateMachine / WebSocket / Audio / MCP
-> NoteCommandService
-> NoteRepository
-> SQLite
```

必须消除：

```text
Sidecar
localhost HTTP
控制轮询
外部 py-xiaozhi Runtime
第二套业务状态
第二套便签写入口
QML 直接操作网络、音频或数据库
```

---

## 3. 已冻结的核心技术决策

### 3.1 单进程

产品默认只运行一个 Python 进程。

允许：

- Qt 主线程；
- qasync 驱动的 asyncio；
- PortAudio/PyAudio 原生音频回调线程；
- 音频编解码工作线程；
- 单线程数据库 Executor。

不允许：

- Sidecar；
- 外部 py-xiaozhi Runtime；
- 以多进程作为默认性能方案；
- 通过 localhost HTTP 连接本地业务模块。

### 3.2 事件循环

采用：

```text
Qt 主线程 + qasync + asyncio
```

即：

```text
QGuiApplication
+ qasync.QEventLoop
+ asyncio Task
```

理由：

- Qt Property 和 Signal 天然在 Qt 主线程；
- AssistantState 保持单写者；
- 网络 I/O 使用 async，不阻塞 UI；
- 不创建第二个长期 asyncio loop；
- 避免跨线程 Future、锁和 loop 生命周期问题；
- 更接近 Android 中单一协程调度中心的思路。

禁止：

- 在后台线程再创建长期 asyncio loop；
- QML 回调直接执行阻塞 SQL；
- 音频 callback 直接修改 UI；
- WebSocket callback 直接操作 QML。

### 3.3 音频入口

当前 PC 音频入口为：

```text
PyAudio / PortAudio
```

当前编码实现为：

```text
PyAV / FFmpeg libopus
```

正式 runtime dependencies 由 `pc-app-build/pyproject.toml` 管理：

```text
PyAudio >= 0.2.14, < 0.3
PyAV >= 13, < 17
```

唯一安装契约为：

```powershell
python -m pip install -e ".[dev]"
```

不再优先采用 Gate 0 候选中的 `sounddevice + opuslib`，也不再强制要求历史 `INSTALL_GATE3_2_AUDIO_DEPS.ps1`。该替代决策由 ADR-007 固定，ADR-002 已被 superseded。

当前 Gate 3 上行结构：

```text
PyAudio Input Stream
-> bounded PCM16 ingress queue
-> one Audio Encoder Worker
-> PyAV Opus Encoder
-> bounded Opus Packet Queue
-> qasync uplink owner
-> existing single WebSocket sender
```

Gate 4 才实现下行：

```text
WebSocket Binary
-> Opus Decoder
-> PCM Playback Buffer
-> PyAudio Output Stream
-> actual PlaybackEnded
```

PyAudio 只负责平台音频设备和 PCM 流，不负责 AssistantState、WebSocket、VAD 状态、MCP、QML 或数据库。

冻结上行参数：

```text
采样率：16,000 Hz
声道：mono
格式：PCM16 little-endian
帧长：20ms
每帧采样数：320
每帧 PCM：640 bytes
Opus application：VOIP
上行码率：24 kbps
```

下行播放采样率属于 Gate 4 平台适配，Decoder 与 Playback Adapter 必须分层。

### 3.4 数据库路径

生产和开发默认统一使用：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\
│  ├─ notes.db
│  ├─ custom_tags.json
│  ├─ assistant_runtime.json
│  └─ assistant_preferences.json
├─ logs\
├─ metrics\
└─ backups\
```

`assistant_runtime.json` 保存 endpoint、激活和身份相关配置；`assistant_preferences.json` 保存语音模式、交互偏好与 launcher 位置。报告、测试输出和交付包不得包含 token、完整设备身份或密钥。

不再以仓库目录作为默认运行时数据库路径。

原因：

- 打包后无需再次迁移；
- Worktree 与真实数据隔离；
- 防止数据库误提交；
- 开发、打包和升级路径一致；
- 安装包无需重新设计用户数据目录。

测试允许通过 `AppPaths` 注入临时目录。

### 3.5 便签统一业务边界

手动 UI 和未来 MCP 工具必须共用：

```text
NoteCommandService
NoteQueryService
NoteRepository
```

禁止：

```text
QML -> SQLAlchemy
MCP -> SQLAlchemy
QML -> HTTP -> Notes API
Assistant -> 独立便签写逻辑
```

统一链路：

```text
Manual UI
-> NotesViewModel
-> NoteCommandService
-> NoteRepository
-> SQLite
```

```text
Voice MCP
-> McpProtocolClient
-> ToolExecutor
-> NoteCommandService
-> NoteRepository
-> SQLite
```

### 3.6 状态所有权

AssistantState 只有一个写入者：

```text
AssistantController
```

其他模块只产生事件：

```text
WebSocket Event
Audio Event
UI Command
MCP Event
Reconnect Timer
System Audio Event
```

统一进入：

```text
AssistantController
-> ConversationStateMachine
-> new AssistantState
```

禁止 AudioEngine 直接写状态、WebSocketClient 直接写 QML、QML 维护第二套 phase、Repository 修改 AssistantState。

---

## 4. 模块边界

推荐最终目录：

```text
pc-app-build/apps/notes-pyside/
├─ main.py
└─ app/
   ├─ __init__.py
   ├─ bootstrap.py
   ├─ app_paths.py
   ├─ lifecycle.py
   ├─ assistant/
   │  ├─ controller.py
   │  ├─ state.py
   │  ├─ state_machine.py
   │  ├─ events.py
   │  ├─ metrics.py
   │  ├─ activation/
   │  ├─ identity/
   │  ├─ protocol/
   │  ├─ network/
   │  ├─ audio/
   │  └─ mcp/
   ├─ notes/
   │  ├─ domain.py
   │  ├─ commands.py
   │  ├─ repository.py
   │  ├─ sqlalchemy_models.py
   │  ├─ sqlalchemy_repository.py
   │  ├─ database_executor.py
   │  ├─ command_service.py
   │  ├─ query_service.py
   │  ├─ migration.py
   │  └─ tag_catalog.py
   ├─ ui/
   │  ├─ note_list_model.py
   │  ├─ notes_view_model.py
   │  └─ assistant_view_model.py
   └─ qml/
```

依赖方向：

```text
QML
-> UI ViewModel
-> Application Service / AssistantController
-> Domain Interface
-> Platform Adapter
```

强制约束：

- `assistant/` 不依赖 PySide6；
- `notes/` 不依赖 PySide6；
- 只有 `ui/` 和 `bootstrap.py` 可以依赖 PySide6；
- Repository 不返回 ORM Row；
- ViewModel 不持有 SQLAlchemy Session；
- QML 不直接访问 WebSocket、Audio、Repository；
- Bootstrap 是唯一 Composition Root。

---

# 5. 分阶段实施总计划

## Gate 0：冻结架构 Spec

### 目标

先冻结系统边界，再编码，避免边写边改架构。

### 输出

```text
PC_RUNTIME_REWRITE_SPEC.md
ASSISTANT_STATE_CONTRACT.md
CONCURRENCY_OWNERSHIP_SPEC.md
LATENCY_MEASUREMENT_SPEC.md
MCP_NOTE_TOOL_SCOPE.md
GATE0_ACCEPTANCE_CHECKLIST.md
```

### 冻结内容

- 模块依赖方向；
- AssistantState 最小字段；
- Controller 接口；
- StateMachine 纯状态约束；
- Qt、asyncio、音频、数据库的线程所有权；
- 队列容量与溢出策略；
- generation token；
- WebSocket hello；
- 音频协议参数；
- MCP MVP 工具；
- 延迟事件名称；
- 关闭顺序；
- 错误策略。

### 验收

- Spec 之间不冲突；
- 单进程/qasync 决策明确；
- 不存在 Sidecar、本地 HTTP、多 Runtime 兼容路线；
- 所有后续 Gate 都有明确输入输出。

### 预计

```text
0.5～1 个有效工作日
```

### 当前状态

```text
已完成
```

---

## Gate 1：恢复单进程手动便签

### 目标

恢复一个可用的本地便签 App，并建立未来 MCP 共用的进程内业务边界。

### 总链路

```text
AppPaths
-> SQLAlchemy Repository
-> Note Domain
-> NoteCommandService
-> NoteQueryService
-> NotesViewModel
-> QML
```

### 验收

- 单一 Python 进程；
- 无 HTTP；
- 数据位于 `%LOCALAPPDATA%\NoteAssistant\`；
- 手动创建、搜索、更新、置顶、删除、恢复、彻底删除；
- 旧数据库可安全读取或迁移；
- UI 不阻塞；
- ViewModel 不直接写 SQLAlchemy；
- MCP 后续直接复用 NoteCommandService。

### Gate 1.1：Bootstrap 与 AppPaths

完成：

- qasync Bootstrap；
- QGuiApplication；
- AppPaths；
- ApplicationLifecycle；
- 空 NotesViewModel；
- QML Smoke；
- Basic Qt Quick Controls Style。

状态：已完成。

### Gate 1.2：Domain 与 Persistence

完成：

- Note Domain；
- Commands；
- Repository Protocol；
- SQLAlchemy ORM；
- SqlAlchemyNoteRepository；
- DatabaseExecutor；
- 批量事务；
- 精确标签查询；
- UTC 兼容。

状态：已完成。

### Gate 1.3：数据迁移与 TagCatalog

完成：

- legacy DB 候选发现；
- SQLite quick_check；
- SQLite Backup API；
- LocalAppData 目标路径；
- 备份；
- 迁移报告；
- custom_tags.json；
- TagCatalog；
- 标签引用保护；
- 默认标签；
- 受保护标签；
- 数据迁移测试。

状态：完成修复后待最终确认。

最终验收：

```text
Black 通过
Ruff 通过
Gate 1.1 + 1.2 + 1.3 全量测试通过
```

### Gate 1.4：Application Service 与 Bootstrap Composition

完成：

- `NoteCommandService`；
- `NoteQueryService`；
- 异步 Service 接口；
- DatabaseExecutor 调度；
- Repository 错误到应用错误的映射；
- Bootstrap 中组合 AppPaths、Migration、Engine、SessionFactory、DatabaseExecutor、Repository、TagCatalog、CommandService、QueryService；
- Lifecycle 注册 DB Executor 和 Engine 关闭器。

约束：

- UI 可暂时继续使用空 ViewModel；
- Service 不依赖 PySide6；
- 每个写命令只进入一次 DB Executor；
- 批量操作仍是一次事务；
- Bootstrap 不直接写业务 SQL。

预计：

```text
0.5～1 日
```

### Gate 1.5：Qt Model 与 NotesViewModel

完成：

- NoteListModel；
- DeletedNoteListModel；
- NotesViewModel；
- Qt Property；
- async Slot；
- query generation；
- mutation serialization；
- selection by note_id；
- busy 状态；
- success/failure Signal；
- TagCatalog 映射。

预计：

```text
0.5～1 日
```

### Gate 1.6：QML 正式接线

完成：

- 空 ViewModel 替换为正式 NotesViewModel；
- 所有页面读写真实数据；
- 创建、编辑、搜索、分类、置顶、标签；
- 软删除、恢复、彻底删除、批量操作；
- async Signal 驱动导航；
- 错误时保留用户输入。

预计：

```text
0.5～1 日
```

### Gate 1.7：Gate 1 总验收

完成：

- Unit；
- Integration；
- QML Smoke；
- Windows 手工测试；
- legacy 数据迁移；
- 重启持久化；
- 退出无残留线程/进程；
- Gate 1 Implementation Report。

预计：

```text
0.5 日
```

### Gate 1 总预计

原始估算：

```text
1～2 日
```

按当前实际拆分和 Windows 迁移验证，修订为：

```text
3～5 个有效工作日
```

---

## Gate 2：Runtime Core 与文本链路

### 目标

在不涉及音频的情况下完成真实 Assistant Runtime 核心。

### 模块

```text
AssistantState
ConversationStateMachine
AssistantController
AssistantEvent
MessageBuilder
MessageRouter
WebSocketClient
ReconnectPolicy
ActivationClient
DeviceIdentity
AssistantViewModel
MetricsRecorder
```

### 第一版能力

```text
enable
disable
connect
hello
send_text
receive_text
disconnect
automatic reconnect
manual reconnect
error state
```

### 建议最小 phase

```text
Disabled
Idle
Activating
Connecting
Connected
Listening
UploadingAudio
Thinking
Speaking
Reconnecting
Error
```

### 验收

- QML 只观察 AssistantViewModel；
- WebSocket 不依赖 QML；
- StateMachine 不依赖网络；
- Controller 不依赖 PySide6；
- Fake WebSocket 可测试所有状态转换；
- hello 收到非空 session_id 后才算 Connected；
- 自动重连有上限、退避和取消；
- disable 可释放连接和任务；
- 所有状态变更在 qasync loop 串行发生。

### 预计

```text
1～2 个有效工作日
```

---

## Gate 3：全局悬浮入口、共用音频、PTT 与 Streaming 上行/VAD

### 当前状态

```text
Gate 3.1  完成
Gate 3.2  完成
Gate 3.3  真实一轮链路通过
Gate 3.4  收口交付；最终关闭以累计自动 verifier 全部返回 0 为准
```

Gate 3 不实现 TTS 播放、自动第二轮、barge-in、MCP 或 KWS。

### Gate 3.1：全局悬浮 Shell、Preferences、Audio Ports/Fake

- `ApplicationWindow` 内全局单实例 AssistantOverlay；
- 默认折叠、可拖动 Aurora launcher；
- Assistant Preferences 与 RuntimeConfig 分离；
- PTT/streaming 模式选择；
- Audio models/ports/bounded queues/Fake；
- Offscreen QML smoke；
- 不打开真实麦克风。

Gate 3.1 只冻结 `streamingCapabilityReady` 字段存在、类型为 bool 且由 `AssistantState.capabilities` 驱动。Gate 3.3 激活后该投影为 True，历史 Gate 3.1 测试不得永久断言 False。

### Gate 3.2：共用真实采集管线与 PTT

```text
QML PTT
-> AssistantViewModel
-> AssistantController event pump
-> one PyAudio input stream
-> bounded PCM queue
-> one Audio worker / PyAV Opus encoder
-> bounded Opus queue
-> qasync uplink task
-> existing single WebSocket sender
```

约束：

- PTT 与 streaming 共用一个 `AssistantAudioEngine`；
- 单一逻辑 microphone lease；
- PCM ingress 容量 8，满时 drop-oldest 并计数；
- encoded uplink 容量 16，满时失败当前 turn；
- callback 不写日志、不写状态、不发网络；
- capture generation 使旧 callback/packet/stop 失效；
- stop/cancel/release 幂等。

### Gate 3.3：Streaming Conversation Uplink + Local VAD

真实一轮链路：

```text
manual streaming start
-> microphone lease
-> shared capture
-> local VAD
-> shared Opus uplink
-> end of speech
-> exactly one listen/stop
-> readable STT
-> readable assistant/TTS transcript
-> WAITING_FOR_NEXT_TURN
-> manual session stop
```

当前能力：

- streaming session generation/UUID；
- VAD warmup / speech start / end of speech / no-speech timeout；
- 自动提交当前 turn；
- response watchdog；
- 断线 recovery；
- mode switch / disable / shutdown cleanup；
- `STREAMING_CONVERSATION` 与 `VAD` capability active。

边界：

- transcript 接收不等于 TTS 播放；
- AssistantTextReceived/TtsStateReceived 不自动启动下一轮；
- `TTS_PLAYBACK` 与 `BARGE_IN` 仍为 not_ready；
- 单次 latency sample 不得描述为 p95；
- 可读 STT 不等于识别准确率验收。

### Gate 3.4：总验收、异常生命周期与文档收口

收口内容：

- 累计自动入口 `VERIFY_GATE3_3.ps1`；
- 独立真实入口 `RUN_GATE3_3_REAL_STREAMING.ps1`；
- Gate 3.1/3.2 历史测试契约修正；
- WAITING_FOR_NEXT_TURN 状态语义；
- turn/session protocol finalization 幂等；
- response timeout / stop / disconnect / stale token 的确定性排列测试；
- resource terminal matrix；
- 总纲、修正案、ADR、Spec 与报告收口。

同一 streaming generation + capture generation + turn token：

- `listen/stop` 或 `abort` 最多发送一次；
- turn submission/completion 最多一次；
- session stop 最多一次；
- timer/task cancellation、capture stop 和 lease release 可重复调用但结果相同；
- 旧 connection/session/turn 事件为无害 no-op；
- 陈旧 callback 不得恢复 capture。

有效 assistant text/TTS transcript 后固定：

```text
streaming_state = WAITING_FOR_NEXT_TURN
streaming_session_active = true
audio.status = idle
capture/uplink/VAD/response timer/worker/lease = stopped
next-turn capture = not started
```

### Gate 3 资源终态

正常 session stop、transport 仍 connected 时必须无：streaming response timer、audio uplink、VAD task、capture stream、audio worker、microphone lease。Transport sender/receiver 可以继续存在。

自动恢复期间允许同一 generation 暂时存在一个 reconnect timer；恢复成功后 timer 消失，capture 最多恢复一次。

Disable/shutdown 完成后必须无：reconnect timer、streaming timer、uplink、VAD、capture、worker、lease、transport sender/receiver、pending `assistant-*` task 和第二 Python runtime。

---

## Gate 4：TTS 播放与真实两轮连续对话

### 状态

未开始。

### Gate 4.1：TTS Playback

```text
WebSocket binary downlink
-> Opus decode
-> playback buffer
-> PyAudio output
-> PlaybackStarted / actual PlaybackEnded
```

要求：playback generation、旧包丢弃、abort 清空、设备错误可见、播放资源有界关闭。

### Gate 4.2：Auto Next Turn 与可选简单插话

只有当前 playback generation 的真实 `PlaybackEnded` 才能触发下一轮 capture：

```text
turn_1 speech
-> real TTS playback
-> PlaybackEnded
-> exactly one listening turn_2
```

AssistantTextReceived、TtsStateReceived 或 `tts/stop` 本身均不是自动开麦触发源。真实两轮未完成前不得声明完整连续对话通过。简单 barge-in 默认关闭，并继续共用同一 microphone ownership。

---

## Gate 5：MCP 便签闭环

### 状态

已完成并接受。Windows 累计自动验收和 32 个真实工具验收均由用户报告通过。

### 冻结工具面

```text
Tool count: 32
Name-set SHA-256: 543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9
Unsupported Android-only tools advertised: 0
Runtime: single process
```

MCP 共用 `NoteCommandService` / `NoteQueryService`，未注册工具 fail-closed，request id 去重，高风险写操作显式确认，删除默认软删除。真实反馈修订已加入 `ui.show_todos`，并将纯数字标题与明确数据库 ID 分开解析。不得建立第二套便签写入口或第二 Runtime。

---

## Gate 6：语音体验与设备增强

Gate 6 将原独立 Gate 6.5 KWS 合并进同一个语音增强总 Gate，固定为五个子阶段：

```text
6.0  Cross-platform probe and contract freeze
6.1  Device registry, route handling and duplex audio foundation
6.2  Offline KWS and microphone-owner handoff
6.3  AEC/NS processing; AGC probe only and default-off
6.4  Acoustic barge-in, settings completion and cumulative closeout
```

冻结顺序为：设备/双工底座先于 KWS；AEC 先于声学 barge-in。KWS 与 barge-in 是两个独立检测器，KWS 不得用于播放期插话。

Gate 6 首版产品策略：

```text
AEC                automatic / required for speaker-route acoustic barge-in
NS                 automatic / conservative
AGC                off by default; not a Gate 6 completion dependency
KWS                off until user enables it
Acoustic barge-in  off until user enables it and the processed path is ready
```

Gate 6.0 比较 WebRTC APM、Windows endpoint/system AEC 和 macOS voice processing；在真实 probe 前不冻结 concrete backend。Core、StateMachine 和 Ports 不导入平台 API。

Gate 6 引入小型“语音与设备”面板，而不是完整设置中心。普通用户只选择 input/output、KWS、唤醒词和是否允许插话；AEC/NS/AGC、delay、drift、ERLE 等只进入 Developer Diagnostics。

Windows 全量证据通过后可标记 `Accepted-Windows`。只有真实 macOS capture/playback/KWS/AEC/barge-in/terminal 证据通过后，才能标记 `Accepted-CrossPlatform`。

任何增强仍不得引入第二 Runtime、第二状态机、第二 sender、第二 Python 进程或无所有权的麦克风流。

---

## Gate 7：A/B 延迟验证

### 目标

对 Android、旧 PC、新 PC 使用同一组指标。

### 时间源

```python
time.perf_counter_ns()
```

禁止使用墙钟计算性能。

### 核心事件

App：

```text
app_process_start
bootstrap_start
qt_created
qml_load_start
qml_ready
first_frame
runtime_ready
```

Connection：

```text
connect_requested
socket_opened
hello_sent
hello_received
connected
```

PTT：

```text
ptt_down
capture_requested
capture_started
first_pcm
first_opus
first_audio_sent
ptt_up
stop_listen_sent
```

Downlink：

```text
stt_partial
stt_final
tts_start
first_downlink_packet
first_decoded_pcm
playback_started
playback_ended
```

MCP：

```text
mcp_request_received
tool_execution_started
db_transaction_started
db_committed
tool_execution_finished
mcp_response_sent
```

Continuous/KWS：

```text
vad_speech_started
vad_speech_ended
continuous_stop_sent
tts_resume_listening
kws_audio_started
wake_detected
wake_to_listening
false_wake
```

### 对比对象

```text
Android
旧 PC
新单进程 PC
```

### 指标目标

| 指标 | 新 PC 目标 |
|---|---:|
| UI 冷启动 | < 1.5 秒 |
| 已连接时按键到命令接收 | p95 < 50ms |
| 按键到首帧 PCM | p95 < 150ms |
| 按键到首个 Opus 上行 | p95 < 220ms |
| PTT 松开到 stop listen 发出 | p95 < 80ms |
| TTS 包到实际播放 | p95 < 120ms |
| MCP 请求到 DB commit | p95 < 150ms |
| KWS 唤醒到 Listening | p95 < 300ms |
| 本地 HTTP | 0 |
| 轮询控制 | 0 |
| 外部 Runtime 进程 | 0 |

### 测试方法

```text
3 次预热
30 次正式样本
输出 p50 / p95 / max
相同设备
相同网络
相同服务端
冷启动和热启动分开
```

### 预计

```text
1 个有效工作日
```

---

# 6. 连续对话与 KWS 的范围决策

Gate 3 修正案已实施，当前顺序为：

```text
Gate 3  共用音频基础 + PTT + streaming 上行/VAD
Gate 4  TTS 播放 + PlaybackEnded 自动续轮 + 真实两轮 + 可选简单插话
Gate 5  32-tool MCP 便签闭环（已完成）
Gate 6  设备/双工 + KWS + AEC/NS + 声学 barge-in
Gate 7  延迟验证
```

连续对话上行/VAD 不再等待 MCP；完整连续语音闭环仍以 Gate 4 的真实播放与 actual PlaybackEnded 为基线。Gate 6 不得破坏 PlaybackEnded 唯一自然续轮规则。

## 增量估算（历史规划，非当前完成声明）

| 能力 | 增量时间 |
|---|---:|
| TTS playback + PlaybackEnded | 1～2 日 |
| 真实两轮与自动续轮 | 0.5～1 日 |
| 简单打断 | 0.5～1 日 |
| 基础 KWS | 1～2 日 |
| KWS 设备兼容与误唤醒调优 | 1～2 日 |
| Windows 蓝牙/热插拔增强 | 1～2 日 |
| AEC/NS/AGC 深度优化 | 2～5 日 |

---

# 7. 总工期

## 原始估算

```text
最终微清理             0.5 日
Spec 与状态契约        0.5～1 日
单进程便签恢复         1～2 日
文本 Runtime           1～2 日
PTT + TTS              3～5 日
MCP 便签闭环           1～2 日
性能对照               1 日
```

原始可验证版本：

```text
约 7～12 个有效工作日
```

## 根据实际 Gate 1 拆分后的修订估算

```text
Gate 0                  已完成
Gate 1                  3～5 日
Gate 2                  1～2 日
Gate 3                  2～3 日
Gate 4                  1～2 日
Gate 5                  已完成
Gate 6                  以 6.0 真实探测后估算为准
Gate 7                  1 日
```

历史 Gate 6/6.5 工期估算失效。Windows/macOS backend、设备路由和打包探测前不得给出伪精确总工期。

---

# 8. 主要风险

## 8.1 Windows 音频设备行为

包括默认设备变化、蓝牙设备切换、设备占用、采样率差异、热插拔、PyAudio callback 行为和关闭时流阻塞。

应对：

- Audio Adapter 与 Core 分离；
- Device ID 可配置；
- bounded queue；
- generation token；
- 有界关闭；
- 真实设备测试；
- 不在 Gate 3 同时做 KWS 和蓝牙增强。

## 8.2 服务端激活与协议边界

包括 activation、device identity、hello 字段、session_id、binary packet、TTS 采样率、listen/abort 时序和 MCP 路由。

应对：

- 逐条对照 Android；
- MessageBuilder 独立；
- MessageRouter 独立；
- Fake WebSocket；
- 协议 trace；
- 不把服务端字段硬编码进 QML。

## 8.3 SQLite 与 Windows 文件句柄

包括 backup API、WAL/SHM、文件替换、测试临时目录、connection close 和 Engine dispose。

应对：

- 所有 sqlite3 connection 显式 close；
- SQLAlchemy Engine 显式 dispose；
- Windows 本地测试；
- 不把 Linux 测试通过等同于 Windows 通过；
- 迁移逻辑必须有独立 Windows 验收。

## 8.4 上下文与文档漂移

本文件用于避免对话上下文达到上限后丢失总路线。

规则：

- 新决策先改本文件；
- Gate Spec 只描述当前 Gate；
- ADR 记录不可逆决策；
- Delivery Report 记录实际完成情况；
- 不在多个文档重复维护不同版本的总计划。

---

# 9. 每个 Gate 的统一交付要求

每个 Gate 必须包含：

```text
完整代码文件
中文交付报告
测试命令
明确验收标准
已知限制
提交建议
```

禁止：

- 只给片段却声称完整；
- 未实际验证却声称通过；
- 只在 Linux 验证 Windows 特有逻辑；
- 将格式检查失败视为通过；
- 将 UI 可启动等同于业务完成；
- 用兼容层保留已废弃架构；
- 未经 Spec 直接扩大范围。

---

# 10. 当前进度

| 阶段 | 状态 |
|---|---|
| 最终架构清理 | 已完成 |
| Gate 0 | 已完成（历史冻结基线保留） |
| Gate 1.1～1.7 | 已完成 |
| Gate 2.1～2.7 | 已完成，Automated/Fake/Real 证据已归档 |
| Gate 3.1 | 已完成 |
| Gate 3.2 | 已完成 |
| Gate 3.3 | 真实一轮链路通过；累计自动验收由 Gate 3.4 收口 |
| Gate 3.4 | 已完成 |
| Gate 4 | 已完成（4.0～4.4，真实协议、真实播放、真实两轮与停止优先级） |
| Gate 5 | 已完成（32-tool Windows Automated/Fake/Real 验收通过） |
| Gate 6 | Spec 已冻结，等待 6.0 探测实施 |
| Gate 7 | 未开始 |

Gate 3.3 只声明 VAD + Opus 上行 + readable transcript；不声明 TTS 播放、自动第二轮或 barge-in。

---

## 10.1 Gate 4 已冻结结果

Gate 4 在单进程 Runtime 内完成：

```text
真实 WebSocket Opus binary downlink
-> bounded encoded ingress
-> PyAV decode/resample
-> bounded PCM buffer
-> PyAudio callback output
-> actual physical PlaybackEnded
-> exactly-once auto next turn
-> 真实两轮连续对话
```

当前真实 endpoint 已验证为 Opus / 24 kHz / mono / 20 ms；实际 decoder/output 层使用显式格式规划，不能把 wire format 当成 PCM output format。

冻结所有权：

- 原始 Opus 和 PCM 不进入 Runtime event queue 或 AssistantState；
- WebSocket receiver 不等待 decode、output 或 physical drain；
- playback worker 是 decode/resample/queue 协调的唯一所有者；
- PortAudio callback 只消费 PCM、补静音并报告真实 sample consumption；
- 只有 terminal + encoded empty + decoder flush + PCM empty + 最后真实 sample consumed + output inactive 才能产生 natural `PlaybackEnded`；
- 只有当前 generation/token 的 natural `PlaybackEnded` 可以分配下一轮 capture；
- stop、mode switch、disconnect、disable、shutdown、失败、取消和陈旧 callback 均不续轮；
- 默认不允许 capture 与 playback 重叠。

Gate 4 不包含 MCP、KWS、AEC、声学全双工 barge-in 或完整设备热插拔恢复。这些能力继续属于后续 Gate。

验收资产：

- `tools/verify_gate4_0_real_downlink_probe.py`；
- `tools/verify_gate4_2_real_playback.py`；
- `tools/verify_gate4_3_real_two_turn.py`；
- `tools/verify_gate4_4_real_stop_during_playback.py`；
- `tools/verify_gate4_4_cumulative.py`。

---

## 10.2 Gate 5 已冻结结果

Gate 5 在同一 WebSocket、同一 sender、同一 Controller 和同一便签服务边界内完成 32 个真实 MCP 工具。工具目录、确认、去重、重连不重放、UI typed bus 和资源终态均以 `docs/spec/gate5/` 与 `docs/report/GATE5_FINAL_ACCEPTANCE_REPORT.md` 为准。

Gate 5 的真实反馈修订包括：

- 新增 `ui.show_todos`；
- 纯数字 query 按标题/关键词解析；
- 只有“编号/ID/第 N 号便签”等明确表达按数据库 ID；
- reconnect 不重放历史工具调用。

---

# 11. 历史 Gate 1.4 开始前检查（保留）

> 以下内容是 Gate 1 当时的历史 checkpoint，不代表当前进度，也不覆盖当前累计 Gate 3 verifier。

必须满足：

```text
python -m black --check apps\notes-pyside\app\notes tests\gate1_3
python -m ruff check apps\notes-pyside\app\notes tests\gate1_3
python -m pytest tests\gate1_1 tests\gate1_2 tests\gate1_3 -q
```

期望：

```text
Black 通过
Ruff 通过
52 passed
```

通过后进入：

```text
Gate 1.4
NoteCommandService
NoteQueryService
Bootstrap Composition
Migration Integration
DatabaseExecutor Lifecycle
```

---

# 12. 最终产品验收

## 架构

- 单 Python 进程；
- qasync 单事件循环；
- 无 Sidecar；
- 无 localhost HTTP；
- 无控制轮询；
- 无外部 py-xiaozhi Runtime；
- Core 不依赖 PySide6；
- UI 不直接访问平台资源。

## 功能

- 手动便签；
- 文本对话；
- PTT；
- TTS；
- MCP 32-tool 便签闭环；
- 高风险确认/拒绝与软删除恢复；
- 连续对话；
- 可选离线 KWS；
- AEC/NS processed path；
- 可选声学 barge-in；
- input/output 设备选择与安全恢复；
- 自动重连；
- 错误可见；
- 数据持久化。

## 性能

- UI 冷启动 < 1.5 秒；
- PTT 到首帧 PCM p95 < 150ms；
- PTT 到首个 Opus 上行 p95 < 220ms；
- TTS 包到播放 p95 < 120ms；
- 本地 HTTP = 0；
- 控制轮询 = 0；
- 外部 Runtime 进程 = 0。

## 工程质量

- StateMachine 可纯单测；
- Fake WebSocket 可覆盖连接状态；
- Fake Audio 可覆盖 Controller；
- Migration 有 Windows 测试；
- 所有队列有界；
- 所有长期任务可取消；
- 所有 shutdown 有界；
- 不保留旧架构兼容层。

---

## 结论

本项目主线不是“把 PC 旧代码修好”，而是：

> 以 Android 已验证架构为参考，在 PC 上构建一个单进程、qasync 驱动、PyAudio 音频入口、LocalAppData 数据路径、统一 NoteCommandService、可测试且可量化延迟的完整语音助手 Runtime。

当前执行顺序：

```text
架构
-> 本地便签业务边界
-> 文本 Runtime
-> 全局悬浮入口
-> 共用音频 / PTT
-> streaming 上行 / VAD
-> TTS playback / PlaybackEnded / 真实两轮
-> MCP
-> 语音与设备增强
-> KWS
-> 延迟验证
```

不要跳过基础层，也不要因为追求快速 Demo 重新引入 Sidecar、本地 HTTP、第二 Runtime 或第二套业务状态。

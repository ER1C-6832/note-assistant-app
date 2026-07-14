# PC 小智语音助手单进程重写总计划

> 文档定位：本文件是 PC 端单进程 Runtime 重写的长期权威计划。  
> 后续 Gate、Spec、ADR、代码实现和验收均以本文件为总纲；若局部文档与本文件冲突，先更新本文件并记录决策变更。

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

PC 音频入口改为：

```text
PyAudio / PortAudio
```

不再优先采用 sounddevice。

目标结构：

```text
PyAudio Input Stream
-> PCM16 Ring Buffer
-> Audio Encoder Worker
-> Opus Packet Queue
-> WebSocket Binary Upload
```

下行：

```text
WebSocket Binary
-> Opus Decoder
-> PCM Playback Buffer
-> PyAudio Output Stream
```

PyAudio 只负责平台音频设备和 PCM 流，不负责 AssistantState、WebSocket、VAD 状态、MCP、QML 或数据库。

初始音频参数：

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

下行播放采样率由服务端协议和设备适配决定，Decoder 与 Playback Adapter 必须分层。

### 3.4 数据库路径

生产和开发默认统一使用：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\
│  ├─ notes.db
│  └─ custom_tags.json
├─ logs\
├─ metrics\
└─ backups\
```

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

## Gate 3：PTT 音频上行

### 目标

完成真实按住说话链路。

### 链路

```text
QML PTT Button
-> AssistantViewModel
-> AssistantController
-> AudioCapture
-> PCM16 Frame
-> Opus Encoder
-> WebSocket Binary Upload
-> stop listen
```

### PyAudio 结构

```text
PyAudio Input Stream
-> callback / read loop
-> bounded PCM queue
-> Opus encoder worker
-> bounded packet queue
-> WebSocket send task
```

### 第一版只做

```text
按住说话
松开发送 stop listen
```

不立即做：

```text
continuous conversation
KWS
AEC
复杂打断
Bluetooth recovery
```

### 必须打点

```text
ptt_down
ptt_command_received
capture_requested
capture_started
first_pcm
first_opus
first_packet_queued
first_audio_sent
ptt_up
capture_stopped
stop_listen_sent
```

### 队列建议

PCM ingress：

```text
容量：8 帧
约 160ms
满时丢弃最旧帧
```

Opus packet queue：

```text
容量：16
满时终止本轮并进入可见错误
```

### 验收

- UI 不阻塞；
- 音频 callback 不写日志、不写状态、不写网络；
- PTT 不会启动两个麦克风实例；
- stop 后旧 callback 通过 generation token 失效；
- WebSocket 只有一个发送所有者；
- 按键到首帧 PCM p95 < 150ms；
- 按键到首个 Opus 上行 p95 < 220ms。

### 预计

```text
2～3 个有效工作日
```

---

## Gate 4：TTS 下行播放

### 目标

完成 Assistant 语音回复。

### 链路

```text
WebSocket Binary
-> Audio Router
-> Opus Decoder
-> Playback Buffer
-> PyAudio Output Stream
```

### 完成

- binary 下行；
- Opus decode；
- PCM playback；
- TTS start；
- Speaking State；
- TTS stop；
- playback ended；
- abort；
- playback generation；
- 旧队列丢弃。

### 验收

- UI 不阻塞；
- 新回合不播放旧音频；
- abort 立刻清空旧 generation；
- Speaking 状态开始/结束准确；
- 首个 TTS 包到播放开始 p95 < 120ms；
- 播放设备失败进入可见 Error；
- 不在 WebSocket Router 中硬编码 PyAudio。

### 预计

```text
1～2 个有效工作日
```

---

## Gate 5：MCP 便签闭环

### 目标

让服务端通过 MCP 调用本地便签能力。

### 第一批工具

```text
notes.create
notes.search
notes.delete
```

### 删除确认

```text
tools/call notes.delete
-> NoteCommandService 检查风险
-> 创建 PendingConfirmation
-> 返回 requires_confirmation
-> 用户显式确认
-> 执行软删除
```

### 完整链路

```text
WebSocket MCP
-> MessageRouter
-> McpProtocolClient
-> McpToolExecutor
-> NoteCommandService
-> NoteRepository
-> SQLite
-> ToolResult
-> WebSocket MCP Response
```

### 协议支持

```text
initialize
notifications/initialized
tools/list
tools/call
```

### 约束

- 未注册工具 fail-closed；
- request_id 去重；
- 不直接调用 Repository；
- 工具执行记录审计；
- UI 与 MCP 共用 CommandService；
- 删除默认只软删除；
- 永久删除不进入第一版语音工具。

### 验收

- MCP create 后 UI 可刷新看到；
- MCP search 与手动搜索语义一致；
- delete 未确认时数据库不变；
- 重复 request_id 不重复写；
- ToolResult 结构固定；
- 工具执行错误不导致 WebSocket 断开。

### 预计

```text
1～2 个有效工作日
```

---

## Gate 6：连续对话

### 目标

在 PTT、TTS、MCP 稳定后加入免按键对话。

### 完成

- VAD；
- 无语音超时；
- 自动开始监听；
- 语音结束自动 stop listen；
- Thinking；
- TTS；
- TTS 结束后继续监听；
- 简单打断；
- system audio interruption；
- generation/cancellation。

### 状态链路

```text
Connected
-> Listening
-> UploadingAudio
-> Thinking
-> Speaking
-> Listening
```

### 验收

- VAD 不直接修改 AssistantState；
- 自动 stop 不会重复；
- TTS 后只恢复一个采集任务；
- 用户关闭连续模式后旧任务全部失效；
- 简单打断可停止播放并重新监听；
- 无语音超时可返回 Connected；
- 不影响 PTT 模式。

### 预计

```text
1～2 个有效工作日
```

---

## Gate 6.5：KWS 唤醒词

KWS 不再永久排除，改为可选增强 Gate。

### 目标

支持低功耗持续监听唤醒词后进入连续对话。

### 可能链路

```text
PyAudio KWS Stream
-> KWS Engine
-> wake event
-> AssistantController
-> connect/reuse connection
-> start streaming conversation
```

### 推荐策略

第一版不自行训练模型，优先复用成熟本地 KWS 引擎或现有服务端支持。

### 需要新增

- KWS Audio Owner；
- microphone ownership；
- KWS 与 PTT/Continuous 互斥；
- 唤醒后切换采样通道；
- false positive 指标；
- cooldown；
- system audio interruption；
- KWS enable/disable；
- 设置持久化；
- 模型文件管理。

### 增量工作量

基础唤醒：

```text
1～2 日
```

加入设备兼容、误唤醒调优、模型打包：

```text
2～4 日
```

### 验收

- KWS 不与 PTT 抢麦克风；
- 唤醒后 300ms 内进入 Listening；
- TTS 播放时默认抑制 KWS；
- false positive 可记录；
- 模型不存在时可降级；
- KWS 关闭后不保留音频流；
- 不引入第二进程。

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

原始快速验证只要求文本、PTT、TTS、MCP 和基础连续对话。

当前决策调整为：

- 连续对话纳入主线 Gate 6；
- KWS 纳入可选 Gate 6.5；
- 不因快速验证永久排除完整能力；
- 每增加能力必须明确额外工作量和风险；
- 不允许把 KWS 提前插入 PTT/TTS 尚未稳定的阶段。

## 增量估算

| 能力 | 增量时间 |
|---|---:|
| 基础 VAD 连续对话 | 1～2 日 |
| 简单打断 | 0.5～1 日 |
| TTS 后自动恢复监听 | 0.5 日 |
| 基础 KWS | 1～2 日 |
| KWS 设备兼容与误唤醒调优 | 1～2 日 |
| KWS 模型打包与设置页 | 0.5～1 日 |
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
Gate 5                  1～2 日
Gate 6                  1～2 日
Gate 6.5 KWS            1～4 日
Gate 7                  1 日
```

不含 KWS 的稳定验证版：

```text
约 9～15 个有效工作日
```

包含基础 KWS：

```text
约 10～17 个有效工作日
```

包含 KWS 调优和设备增强：

```text
约 12～20 个有效工作日
```

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
| Gate 0 | 已完成 |
| Gate 1.1 | 已完成 |
| Gate 1.2 | 已完成 |
| Gate 1.3 | 修复后待最终全量确认 |
| Gate 1.4 | 下一步 |
| Gate 1.5 | 未开始 |
| Gate 1.6 | 未开始 |
| Gate 1.7 | 未开始 |
| Gate 2 | 未开始 |
| Gate 3 | 未开始 |
| Gate 4 | 未开始 |
| Gate 5 | 未开始 |
| Gate 6 | 未开始 |
| Gate 6.5 | 未开始 |
| Gate 7 | 未开始 |

---

# 11. Gate 1.4 开始前检查

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
- MCP create/search/delete；
- 删除确认；
- 连续对话；
- 简单打断；
- 可选 KWS；
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

执行顺序保持：

```text
架构
-> 本地便签业务边界
-> 文本 Runtime
-> PTT
-> TTS
-> MCP
-> 连续对话
-> KWS
-> 延迟验证
```

不要跳过基础层，也不要因为追求快速 Demo 重新引入 Sidecar、本地 HTTP、第二 Runtime 或第二套业务状态。

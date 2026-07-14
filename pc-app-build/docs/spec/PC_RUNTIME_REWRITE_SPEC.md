# PC Assistant Runtime Rewrite Spec

状态：Gate 0 冻结候选  
版本：1.0  
Android 参考：`note-assistant-android@974a477ce1803efa130cc8b51a493b39796e0ca7`

## 1. 目标

在现有 PySide6/QML 便签 App 内实现一个单进程、低延迟、可测试的 PC Assistant Runtime。

当前目标只验证：

- 远端激活和 WebSocket；
- 文本对话；
- PTT 上行；
- TTS 下行；
- MCP 便签工具；
- 基础自动重连；
- 完整延迟打点。

不包含：双端同步、设备管理、跨设备命令、KWS、最终商用桌面 UI、云数据库、Sidecar、外部 py-xiaozhi 进程。

## 2. Android 参考原则

PC 复制 Android 的职责边界和行为，不复制平台 API。主要参考：

- `AssistantController.kt`
- `LocalAssistantController.kt`
- `AssistantState.kt`
- `ConversationStateMachine.kt`
- `XiaozhiWebSocketClient.kt`
- `XiaozhiMessageBuilder.kt`
- `RealAudioEngine.kt`
- `McpProtocolClient.kt`
- `NoteCommandService.kt`

## 3. 强制架构

```text
main.py
└─ app/bootstrap.py
   ├─ Qt Application
   ├─ qasync event loop
   ├─ AppPaths
   ├─ NoteRepository
   ├─ NoteCommandService
   ├─ AssistantController
   ├─ NotesViewModel
   ├─ AssistantViewModel
   └─ QML context registration

app/
├─ assistant/      # 不依赖 PySide6
├─ notes/          # 不依赖 PySide6
├─ ui/             # 允许依赖 PySide6
├─ qml/
└─ data/
```

依赖方向：

```text
QML
  -> UI ViewModel
      -> AssistantController / NoteCommandService
          -> Protocol / Audio / MCP / Repository
              -> OS、WebSocket、SQLite
```

禁止 `assistant -> ui`、`notes -> ui`、`audio callback -> QML`、`repository -> QML`。

## 4. 单进程定义

产品只运行一个 Python 进程，但允许多个线程和异步任务：

- Qt 主线程；
- 同一主线程上的 qasync/asyncio loop；
- PortAudio callback 线程；
- 音频编码/播放工作任务；
- 单线程数据库 Executor。

单进程不是单线程，也不要求所有工作串行。

## 5. Composition Root

只有 `app/bootstrap.py` 可以创建具体实现、读取配置、创建数据库和音频设备、注册 QML Context Property，并管理启动和关闭顺序。

领域模块不得自行创建全局单例或读取 UI 对象。

## 6. Runtime Controller 接口

```python
class AssistantController(Protocol):
    @property
    def state(self) -> AssistantState: ...

    def subscribe(self, listener: StateListener) -> Callable[[], None]: ...

    async def enable(self) -> None: ...
    async def disable(self) -> None: ...
    async def connect(self) -> None: ...
    async def reconnect(self) -> None: ...
    async def disconnect(self, reason: str = "user_close") -> None: ...
    async def send_text(self, text: str) -> None: ...
    async def start_push_to_talk(self) -> None: ...
    async def stop_push_to_talk(self) -> None: ...
    async def abort(self, reason: str = "user_interruption") -> None: ...
    async def shutdown(self) -> None: ...
```

Gate 6 才增加连续对话接口。

## 7. 启动顺序

```text
1. 创建 AppPaths
2. 初始化日志和 Metrics
3. 初始化 SQLite
4. 创建 NoteRepository / NoteCommandService
5. 创建 StateMachine
6. 创建 WebSocketClient
7. 创建 AudioEngine，但不启动采集
8. 创建 McpProtocolClient
9. 创建 AssistantController
10. 创建 QML ViewModel
11. 加载 QML
12. UI 首帧后异步恢复连接
```

加载 QML 前禁止枚举全部音频设备、连接远端、全量扫描数据库、导入旧 py-xiaozhi 或启动外部进程。

## 8. 关闭顺序

```text
1. 禁止新命令
2. 取消重连任务
3. 停止录音
4. 清空播放 generation
5. 关闭 WebSocket
6. 刷新 Metrics
7. 关闭 DB Executor
8. 退出 Qt
```

关闭总等待上限 2 秒。超时后记录错误并退出，不扫描系统进程。

## 9. WebSocket 协议

请求头：

```text
Authorization: Bearer <token>
Protocol-Version: 1
Device-Id: <device_id>
Client-Id: <client_id>
```

Hello 与 Android 保持一致：

```json
{"type":"hello","version":1,"features":{"mcp":true},"transport":"websocket","audio_params":{"format":"opus","sample_rate":16000,"channels":1,"frame_duration":20}}
```

只有收到包含非空 `session_id` 的服务端 hello，连接才进入 `Connected`。

热路径必须是 `AudioEngine -> binary WebSocket frame`，禁止经过 localhost HTTP、Sidecar、日志文件、轮询或第二进程。

## 10. 音频参数

上行：PCM16 little-endian、16kHz、单声道、20ms/帧、320 samples/帧、640 bytes PCM/帧、Opus VOIP、24kbps。

下行：Opus Decoder 与 Playback Adapter 分离。Python MVP 默认解码到 24kHz 单声道 PCM16；播放采样率属于平台适配参数，不写入协议 Router。真实验证要求 48kHz 时，只修改音频适配层。

## 11. 技术栈冻结

Gate 1/2 允许加入：`qasync`、`websockets`、`sounddevice`、`numpy`、`opuslib`。

保留：`PySide6`、`SQLAlchemy`、`Pydantic`、`pytest`、`pytest-asyncio`。

不使用：FastAPI、Uvicorn、HTTPX 作为本地业务桥、`multiprocessing` 作为默认架构。

## 12. 数据路径

开发和打包均使用：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\notes.db
├─ config\settings.json
├─ logs\
└─ metrics\
```

仓库内不得存放运行时数据库作为默认生产路径。Gate 1 首次启动允许从旧路径执行一次显式迁移或复制，必须先备份。

## 13. 错误策略

- 状态机非法转换：拒绝并记录；
- WebSocket 失败：进入 Error 或 Reconnecting；
- 音频队列溢出：记录指标并优先保持实时性；
- MCP 未注册工具：fail-closed；
- 数据库失败：返回统一 StorageError；
- UI 不得吞掉 Runtime Error；
- 所有异常带 `operation_id` 或 `turn_id`。

## 14. 测试边界

必须可替换：Fake WebSocket、Fake Audio Engine、In-memory Repository、Fake Clock、Fake Metrics Sink。

Controller 和 StateMachine 测试不启动 Qt。

## 15. Gate 0 结束条件

- 本 Spec 被接受；
- 状态契约、并发所有权、延迟事件命名、MCP MVP 工具和 ADR 被接受；
- 没有 Runtime 源码提前绕开这些边界。

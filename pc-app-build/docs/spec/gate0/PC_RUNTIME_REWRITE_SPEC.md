# PC Assistant Runtime Rewrite Spec

状态：Gate 0 历史冻结基线；Gate 3.4 增补当前实现。  
版本：1.1  
Android 参考：`note-assistant-android@974a477ce1803efa130cc8b51a493b39796e0ca7`

## 1. 历史基线

Gate 0 冻结目标是：在现有 PySide6/QML 便签 App 内实现单进程、低延迟、可测试的 Assistant Runtime，禁止 Sidecar、本地 HTTP 和外部 py-xiaozhi Runtime。

当时的候选音频栈和 Gate 顺序属于历史设计输入，不表示 Gate 0 当时已经拥有当前 PyAudio/PyAV、PTT 或 streaming 能力。当前实现由总纲、Gate 3 修正案和 ADR-007 更新。

## 2. 强制架构

```text
main.py
└─ app/bootstrap.py
   ├─ QGuiApplication + qasync
   ├─ AppPaths
   ├─ NoteRepository / NoteCommandService
   ├─ AssistantController
   ├─ NotesViewModel / AssistantViewModel
   └─ QML context registration

app/
├─ assistant/  # no PySide6
├─ notes/      # no PySide6
├─ ui/         # PySide6 allowed
└─ qml/
```

依赖方向：QML -> ViewModel -> Controller/Application Service -> protocol/audio/repository adapters -> OS/WebSocket/SQLite。

## 3. 单进程定义

产品只运行一个 Python 应用/runtime 进程，允许：Qt 主线程、同一 qasync loop、PortAudio native callback、one audio worker、one DB executor。不得使用 multiprocessing、subprocess Sidecar 或 localhost HTTP 作为 Runtime 架构。

## 4. Composition Root

只有 bootstrap 创建具体实现、读取配置、创建数据库/transport/audio adapter、注册 QML 并管理关闭。领域模块不得创建第二全局 runtime 或读取 QML 对象。

## 5. 当前 Runtime 能力边界

Gate 3 结束时：

- identity、activation、text WebSocket、recovery；
- global floating assistant shell；
- PyAudio capture + PyAV Opus uplink；
- PTT；
- streaming session + local VAD + one-turn transcript；
- WAITING_FOR_NEXT_TURN 手动等待。

未实现：TTS decode/playback、actual PlaybackEnded、auto next turn、two-turn continuous、barge-in、MCP、KWS。

## 6. 当前配置与数据路径

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\notes.db
├─ data\custom_tags.json
├─ data\assistant_runtime.json
├─ data\assistant_preferences.json
├─ logs\
├─ metrics\
└─ backups\
```

测试通过 AppPaths 注入临时目录。仓库目录不是生产数据路径。

## 7. 当前音频协议与依赖

上行：PCM16 little-endian、16 kHz、mono、20 ms、320 samples、640 bytes/frame、Opus VOIP 24 kbps。

依赖：PyAudio + PyAV，由 pyproject 管理。安装命令：`python -m pip install -e ".[dev]"`。

热路径：AudioEngine -> binary WebSocket frame；不得经过日志文件、轮询、本地 HTTP 或第二进程。

## 8. 启动与关闭

启动时创建 AudioEngine 但不打开 capture；用户明确 PTT/streaming start 后才申请 lease 和设备。

关闭顺序：禁止新命令、取消 timers、停止 capture/VAD/uplink、释放 lease、关闭 transport、flush preferences/metrics、关闭 DB executor、退出 Qt。所有操作有界且幂等。

## 9. Gate 3 / Gate 4 分界

Gate 3 的 assistant text/TTS transcript 只更新 transcript 并进入 WAITING_FOR_NEXT_TURN，不播放、不自动开麦。

Gate 4 才激活 binary downlink、decoder、output stream 和 actual PlaybackEnded；PlaybackEnded 是自动 next-turn 的唯一合法触发源。

## 10. 测试边界

必须可替换 Fake transport、Fake capture/encoder/VAD、Fake clock、temporary repository。Controller/Reducer 测试不启动 Qt；QML 通过独立 offscreen smoke；真实 microphone/WebSocket 通过独立人工 runner。

# Assistant State Contract

状态：Gate 0 冻结候选  
原则：单一事实源、单写者、不可变快照。

## 1. 枚举

```python
class AssistantPhase(StrEnum):
    DISABLED = "disabled"
    IDLE = "idle"
    ACTIVATING = "activating"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    UPLOADING_AUDIO = "uploading_audio"
    THINKING = "thinking"
    SPEAKING = "speaking"
    RECONNECTING = "reconnecting"
    ERROR = "error"

class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"

class ActivationStatus(StrEnum):
    UNKNOWN = "unknown"
    REQUIRED = "required"
    ACTIVATING = "activating"
    ACTIVATED = "activated"
    FAILED = "failed"

class AudioStatus(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    PLAYING = "playing"
    ERROR = "error"

class VoiceInteractionMode(StrEnum):
    HOLD_TO_TALK = "hold_to_talk"
    STREAMING = "streaming"
```

## 2. 最小状态

```python
@dataclass(frozen=True, slots=True)
class AssistantState:
    phase: AssistantPhase
    connection: ConnectionStatus
    activation: ActivationStatus
    audio: AudioStatus
    assistant_enabled: bool
    status_text: str
    error_message: str | None
    session_id: str | None
    device_id: str | None
    client_id: str | None
    websocket_url: str | None
    last_user_text: str | None
    last_assistant_text: str | None
    last_event_monotonic_ns: int | None
    reconnect_attempt: int
    last_close_code: int | None
    last_close_reason: str | None
    runtime_error_count: int
    audio_captured_frames: int
    audio_encoded_frames: int
    audio_uploaded_frames: int
    audio_dropped_frames: int
    preferred_voice_mode: VoiceInteractionMode
    active_turn_id: str | None
    active_capture_generation: int
    active_playback_generation: int
```

详细延迟时间线由 `MetricsRecorder` 保存，状态只保留 UI 需要的摘要。

## 3. 单写者

只有 `AssistantController` 所在 asyncio loop 可以替换当前状态。音频 callback、WebSocket 底层回调、QML 和 Repository 都不能直接修改状态。

## 4. 核心不变量

1. `connection == CONNECTED` 时 `session_id` 必须非空。
2. `audio == RECORDING` 时 phase 必须是 Listening 或 UploadingAudio。
3. `audio == PLAYING` 时 phase 必须是 Speaking。
4. `assistant_enabled == False` 时不得处于 Connected/Listening/Speaking。
5. Disabled 时连接断开、音频 Idle。
6. 新录音会话递增 capture generation。
7. 新播放会话或 abort 递增 playback generation。
8. 旧 generation callback 必须忽略。
9. `runtime_error_count` 只能递增。
10. 延迟使用单调时钟。

## 5. 基础转换

```text
Disabled --enable--> Idle
Idle --activate--> Activating
Activating --success--> Idle
Idle --connect--> Connecting
Connecting --hello(session_id)--> Connected
Connecting --failure--> Error/Reconnecting
Connected --ptt_down--> Listening
Listening --ptt_up--> Thinking
Thinking --tts_start--> Speaking
Speaking --tts_end--> Connected
Connected --disconnect--> Idle
Any Enabled --transport failure--> Reconnecting
Any --disable--> Disabled
Any --fatal error--> Error
```

## 6. 非法操作

- 未启用时 connect：不发网络请求；
- 未连接时 PTT：不启动麦克风；
- 未录音时 stop PTT：保持状态并记录 ignored；
- 重复 connect/start PTT：幂等；
- Speaking 时 PTT：Gate 3 默认先 abort 播放，再开始采集。

## 7. UI 映射

`AssistantViewModel` 只映射 State 到 Qt Property/Signal，不连接 WebSocket、不创建 Audio Stream、不执行工具、不写数据库、不保存第二套状态。

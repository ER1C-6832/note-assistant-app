# Gate 3 测试与验收计划

## 1. 分层

```text
Static architecture
Unit
Reducer/Event/Effect
Fake Audio/Transport integration
Offscreen QML
Windows manual UI
Real microphone/WebSocket
Performance
Shutdown/leak
```

## 2. Gate 3.1 UI 验收

### 自动架构

- `Main.qml` 主 `RowLayout` 不包含 `AssistantPanel`；
- `AssistantOverlay` 是 ApplicationWindow 全局单实例；
- Overlay 不创建 Controller；
- QML 不引用 Transport/Audio/Repository；
- Developer 诊断仍绑定同一 `assistantViewModel`；
- `pageLoader` 不因 panel expanded 改变宽度；
- launcher position 不进入 AssistantState；
- 无 `Window {}`/第二顶层助手窗口。

### Offscreen smoke

输出至少：

```json
{
  "qml_root_count": 1,
  "assistant_overlay_count": 1,
  "assistant_panel_in_layout": false,
  "notes_loader_width_stable": true,
  "assistant_event_pump_running": true,
  "status": "gate3_1_ui_smoke_verified"
}
```

### 手工 Windows UI

在 1280x760、1520x960、不同 DPI：

- 默认只有按钮；
- 点击可展开；
- 面板可拖动；
- 拖到四边后仍可关闭/拖回；
- resize 后仍在窗口内；
- 主页、搜索、创建、编辑、已删除页面都只有一个入口；
- Overlay 空白区域可点击下面便签；
- 展开面板不改变列表和详情宽度；
- Developer 诊断可展开；
- Esc 只收起 panel。

## 3. Preferences

- missing file defaults；
- schema round-trip；
- corrupt JSON recovery；
- enum validation；
- timeout clamp；
- position clamp；
- debounce only writes on drag end/settle；
- shutdown flush；
- voice mode change uses Controller event；
- RuntimeConfig 未被 UI position 污染。

## 4. Audio Unit/Fake

- callback try_put non-blocking；
- PCM capacity 8 / drop oldest；
- packet capacity 16 / fail turn；
- frame format validation；
- encoder failure；
- VAD sequence；
- stale capture generation dropped；
- stop timeout；
- device open failure；
- microphone lease rejected；
- no duplicate worker/uplink task。

## 5. Reducer

覆盖：

```text
voice mode change idle
voice mode change during PTT
voice mode change during streaming
PTT start/stop/no speech
streaming start/stop
speech detected/end
no speech timeout
response timeout
abnormal close/recovery
reconnect exhausted
disable/shutdown
stale generation/token
```

纯 Reducer 不打开设备、不 sleep、不访问文件。

## 6. Gate 3.2 Real PTT

Runner 不打印原始 PCM、token 或完整 identity/session。

结果字段建议：

```text
status
input_device_public
sample_rate
pcm_frames
opus_frames
uploaded_frames
speech_seen
first_pcm_latency_ms
first_opus_upload_latency_ms
stop_listen_latency_ms
real_audio_upload_verified
real_text_or_tts_state_verified
no_pending_audio_tasks
```

通过条件：

- uploaded_frames > 0；
- real server 接受当前 session 的音频；
- stop/abort 正确；
- capture/playback 均已关闭；
- 无异常 traceback。

## 7. Gate 3.3 Real Streaming Uplink

结果字段建议：

```text
voice_mode=streaming_conversation
streaming_session_id_masked
streaming_generation
turn_index=1
vad_speech_started
vad_speech_ended
auto_stop_sent
uploaded_frames
server_response_observed
session_stopped
no_pending_audio_tasks
```

通过条件：一轮真实语音由 VAD 自动提交，不能要求用户松开按钮。

## 8. Gate 4.2 Real Continuous

必须两轮：

```text
turn_1_speech -> playback_1_ended
-> auto_listening_2
-> turn_2_speech -> playback_2_ended
```

输出：

```text
turn_count >= 2
playback_ended_count >= 2
auto_resume_count >= 1
single_capture_owner=true
stale_event_count=0 or explicitly archived
```

## 9. UI/Aurora

- State 到 AuroraTarget 的 mapping unit；
- 颜色字符串合法；
- error 不快速闪烁；
- minimized/hidden 时动画暂停或降频；
- QML 帧动画不调用 Python Slot；
- click/drag threshold；
- PTT press/release 各只发一个 command；
- streaming click start/stop 各只发一个 command。

## 10. Shutdown 与泄漏

关闭窗口后：

```text
no reconnect timer
no streaming timer
no next-turn timer
no audio uplink task
no capture stream
no audio worker
no microphone lease
no transport sender/receiver
no second python process
```

Windows runner 需要等待并检查 `asyncio.all_tasks()` 的 Runtime 任务名称。

## 11. 回归

每个 Gate 3 verifier 必须继续执行 Gate 1.7、Gate 2.1～2.7 全量测试和 Gate 2 Real 不变量静态检查。历史 Real 脚本不要求每次自动执行，但不能被删除或失去可追溯工具。

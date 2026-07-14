# Latency Measurement Spec

状态：Gate 0 冻结候选

## 1. 时钟

所有延迟事件使用 `time.perf_counter_ns()`。墙钟只用于文件名和可读报告。

## 2. 关联 ID

每个事件包含 `process_run_id`、`connection_id`、`session_id`、`turn_id`、`capture_generation`、`playback_generation` 中适用的字段。

JSON Lines 示例：

```json
{"event":"audio.first_pcm","ts_ns":123456789,"turn_id":"uuid","generation":3}
```

## 3. 冷启动事件

```text
app.process_start
app.bootstrap_start
app.qt_created
app.qml_load_start
app.qml_ready
app.first_frame
runtime_restore_scheduled
runtime_connect_requested
runtime_hello_received
runtime_ready
```

## 4. PTT 事件

```text
ptt.pointer_down
ptt.command_received
audio.capture_requested
audio.capture_started
audio.first_pcm
audio.first_opus
audio.first_packet_queued
ws.first_audio_sent
ptt.pointer_up
ptt.stop_command_received
audio.capture_stopped
ws.stop_listen_sent
```

## 5. 下行事件

```text
server.stt_partial
server.stt_final
server.tts_start
audio.first_downlink_packet
audio.first_decoded_pcm
audio.playback_started
audio.playback_ended
server.tts_stop
```

## 6. 工具事件

```text
mcp.request_received
mcp.request_parsed
tool.execution_started
db.transaction_started
db.transaction_committed
tool.execution_finished
mcp.response_sent
```

## 7. MVP 目标

| 指标 | 目标 |
|---|---:|
| 进程启动到 QML ready | < 1500ms |
| 已连接时 PTT down 到命令接收 | p95 < 50ms |
| PTT down 到第一帧 PCM | p95 < 150ms |
| PTT down 到首个 Opus 上行 | p95 < 220ms |
| PTT up 到 stop listen 发出 | p95 < 80ms |
| 首个 TTS 包到播放开始 | p95 < 120ms |
| MCP 请求到 DB commit | p95 < 150ms |
| 本地控制轮询 | 0 |
| 本地 HTTP 热路径 | 0 |
| 外部 Runtime 进程 | 0 |

## 8. 测试方法

每个场景 3 次预热、30 次正式样本，输出 p50、p95、max。保持同一麦克风、网络和服务端，分别测试冷启动和热启动，并对比 Android、Legacy PC、新 PC。

## 9. 日志性能

Metrics Recorder 先写内存 ring buffer，由异步任务批量落盘。音频 callback 中不得输出 console、格式化 JSON、写文件或调用 logging。

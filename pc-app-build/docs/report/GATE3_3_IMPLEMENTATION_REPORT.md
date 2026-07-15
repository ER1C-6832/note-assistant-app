# Gate 3.3 Streaming Conversation Uplink Implementation Report

基线提交：`018949c14d1c3ac7e429205c9390f3970d40a5ba`

## 1. 范围

Gate 3.3 激活连续对话的上行与自动提交部分：

```text
start streaming session
-> microphone lease
-> shared PyAudio capture
-> local VAD
-> shared Opus encoder/uplink
-> VAD end of speech
-> listen/stop
-> STT / assistant transcript
-> waiting for manual session stop
```

本 Gate 不实现 TTS 解码与扬声器播放，也不在回复结束后自动开启第二轮。完整语音闭环与自动续轮属于 Gate 4.1/4.2。

## 2. 架构边界

- PTT 与连续对话共用 `AssistantAudioEngine`、PyAudio adapter、Opus encoder 和唯一 WebSocket sender。
- 音频线程只产生 PCM/VAD 数据，不直接修改 `AssistantState`。
- 所有 VAD、session、turn 和 timeout 事件进入现有 Controller event queue。
- `AssistantController` 仍是唯一状态写入者。
- 本地 `streaming_session_id` 使用 UUID，不写入服务端协议。
- connection、streaming、capture 与 turn token 四层 generation/token 共同丢弃陈旧回调。

## 3. VAD

新增自适应能量 VAD：

- 300 ms warmup；
- 自适应 RMS/peak 阈值；
- 240 ms 最短有效语音；
- 700 ms 尾部静音自动提交；
- 默认 8 秒无语音超时；
- 状态：warmup、waiting、speech detected、speech active、end of speech、no speech timeout。

VAD 运行在共享音频 worker 中，只把状态变化放入有界队列。

## 4. 生命周期

- 用户手动开始/停止连续 session；
- VAD 只自动结束当前语音回合；
- 无语音超时结束整个 session；
- 模式切换先停止活跃 streaming session，资源释放完成后再持久化新模式；
- disable、disconnect、异常恢复和 shutdown 取消 VAD、uplink、response timer 并释放麦克风；
- 异常断线时保留本地 session UUID，连接恢复后只启动一次新 capture generation。

## 5. UI

- 设置页仍负责选择按住说话/连续对话；
- 展开面板在连续模式显示“开始/停止连续对话”和 VAD 状态；
- 悬浮 Aurora 左键在连续模式下启动/停止 session；
- 右键仍可展开面板；
- launcher 拖拽与未来 PTT 长按手势没有在本 Gate 强行合并。

## 6. 验收

自动入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

真实入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_3_REAL_STREAMING.ps1
```

Real Gate 必须证明：真实麦克风、真实 Opus 上行、本地 VAD 自动 stop、可读 STT、可读助手文本/TTS transcript、手动结束 session、无残留音频或 asyncio task。

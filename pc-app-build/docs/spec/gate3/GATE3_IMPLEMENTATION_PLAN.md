# Gate 3 实施计划

基线：Gate 2.7 Automated/Fake/Real 均通过。

## Gate 3.0：Spec Freeze

本包即 Gate 3.0 产物。通过条件：

- 总纲修订明确连续对话前移；
- 固定 AssistantPanel 的布局问题有明确迁移方案；
- 音频线程、队列、generation 和 sender ownership 无冲突；
- 设置持久化与 RuntimeConfig 分离；
- Gate 3/4 Real 验收边界清晰。

不写 Runtime 代码。

## Gate 3.1：全局悬浮 Shell、Preferences、Audio Ports/Fake

### UI

- 从 `Main.qml` 主 RowLayout 移除固定 `AssistantPanel`；
- 恢复便签主区域完整宽度；
- 新增 `AssistantOverlay.qml`；
- 新增 `AssistantFloatingPanel.qml`；
- 新增 `AuroraAssistantButton.qml`；
- 现有面板内容迁移/复用；
- 可拖动、clamp、默认折叠；
- Developer 诊断继续可用；
- 所有页面共享单实例。

### Preferences

- `AssistantPreferencesStore`；
- schema v1；
- voice mode selector；
- barge-in preference 默认关闭；
- launcher position debounce persistence；
- bootstrap composition 和 shutdown flush。

### Audio 契约

- ports/models/queues；
- Fake Audio Capture / Encoder / VAD；
- Audio events/effects 契约；
- no real PyAudio device yet。

### 验收

- 自动 UI 架构测试证明 panel 不在 Layout；
- offscreen QML smoke；
- drag/clamp/persistence unit；
- Fake capture generation/overflow；
- Gate 2 全量回归。

## Gate 3.2：共用真实采集管线 + PTT

### 实现

- PyAudio adapter；
- Opus encoder adapter；
- bounded PCM/packet queue；
- audio worker；
- qasync uplink owner；
- microphone lease；
- listen/start / listen/stop / abort effects；
- Aurora Listening/Thinking 状态激活；
- PTT 长按/松开手势。

### Fake Gate

- start/stop；
- no speech；
- queue overflow；
- stale callback；
- double press；
- disable/shutdown；
- network close during capture。

### Real Gate

- 真实麦克风；
- 真实 Opus binary upload；
- 服务端 STT/TTS state 或可读回复；
- stop latency；
- 无残留设备/task。

## Gate 3.3：连续对话上行 + VAD

### 实现

- streaming session generation/UUID；
- VAD warmup/speech/end/no-speech；
- 自动 listen/stop；
- response watchdog；
- network recovering；
- mode switch safely stops session；
- Aurora user-speaking/thinking/recovering；
- 浮动按钮 click start/stop。

### Real Gate

- 切到连续模式；
- 点击开始；
- 真实讲话；
- VAD 自动提交；
- 服务端返回可读文本/TTS state；
- 手动停止；
- session/generation/任务清理正确。

此 Gate 只声明“连续对话上行与自动提交通过”，不声明完整 TTS 后下一轮闭环。

## Gate 3.4：Gate 3 总验收

- Automated/Fake 全量；
- UI non-blocking；
- Real PTT；
- Real streaming uplink；
- abnormal close during idle/listening/thinking；
- disable/mode switch/shutdown；
- performance samples；
- 文档和协议兼容矩阵更新。

## Gate 4.1：TTS Playback

- binary route；
- Opus decode；
- playback buffer；
- PyAudio output；
- playback generation；
- actual `PlaybackEnded`；
- Aurora Speaking。

## Gate 4.2：完整连续对话 + 简单插话

- PlaybackEnded 后唯一 next-turn；
- 真实两轮连续对话；
- barge-in 默认关闭，可设置开启；
- 停止播放 + abort + 新 listen/start；
- 不受旧 playback/turn event 影响。

## Gate 5：MCP

MCP 保持在 PTT、TTS 和完整连续对话稳定后。它不再是连续对话开始前的阻塞项。

## 交付约定

每个子 Gate 都提供：

```text
完整覆盖包
SHA-256
中文报告
VERIFY_GATE3_X.ps1
Fake/Automated 结果
独立 Real runner
已知限制
```

真实音频 Gate 未在 Windows 设备上返回 0，不得声称完成。

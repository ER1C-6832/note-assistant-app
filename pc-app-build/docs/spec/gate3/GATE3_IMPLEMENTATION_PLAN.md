# Gate 3 实施计划

状态：Gate 3.4 收口版  
基线：Gate 2.7 Automated/Fake/Real 已通过。

## Gate 3.0：Spec Freeze

已完成。Gate 3 修正案、UI、音频所有权、设置持久化和 Gate 3/4 Real 边界已冻结。

## Gate 3.1：完成

- 全局悬浮 Shell；
- Assistant Preferences；
- Audio ports/models/queues/Fake；
- offscreen QML smoke；
- Gate 2 全量回归。

历史 `streamingCapabilityReady=False` 只代表 Gate 3.1 当时能力状态，不是永久产品契约。Gate 3.1 测试只验证字段存在、bool 类型和状态驱动。

## Gate 3.2：完成

- PyAudio adapter；
- PyAV Opus encoder；
- bounded PCM/packet queue；
- one audio worker；
- qasync uplink owner；
- microphone lease；
- PTT start/stop/abort；
- Fake 与 Real PTT assets。

正式安装命令：

```powershell
python -m pip install -e ".[dev]"
```

`pyproject.toml` 是唯一依赖契约，不要求历史 `INSTALL_GATE3_2_AUDIO_DEPS.ps1`。

## Gate 3.3：真实链路通过

- streaming session generation/UUID；
- local VAD；
- automatic listen/stop；
- response watchdog；
- network recovery；
- mode switch；
- real one-turn uplink；
- WAITING_FOR_NEXT_TURN；
- manual session stop。

不实现播放或自动第二轮。

## Gate 3.4：收口

### 范围

- 根目录 fail-fast automatic verifier；
- 独立 Real streaming runner；
- 修复 Gate 3.1/3.2 历史测试契约；
- 冻结 WAITING_FOR_NEXT_TURN；
- 确定性终止排列与 stale token tests；
- 正常/恢复/disable-shutdown 资源矩阵；
- 总纲、修正案、Gate 0 注记、ADR 和报告收口。

### 异常矩阵

```text
repeated start
stop while waiting for speech
stop while user speaking
end_of_speech then stop
stop then end_of_speech
no speech timeout
short speech
uplink overflow
disconnect listening
disconnect thinking
single reconnect/single capture resume
streaming -> PTT
disable
shutdown
response timeout / stop / disconnect permutations
stale generation/session/turn callback
```

### 非目标

不拆 Controller，不新增 Runtime，不实现 TTS playback、auto second turn、barge-in、MCP 或 KWS。

## Gate 4.1：未开始

Binary downlink、Opus decode、PyAudio playback、playback generation、实际 PlaybackEnded、Aurora Speaking。

## Gate 4.2：未开始

PlaybackEnded 唯一续轮、真实两轮、默认关闭的可选简单插话、stale playback no-op。

## Gate 5：未开始

MCP 继续位于完整语音交互之后，共用 NoteCommandService。

## 交付约定

自动入口：`VERIFY_GATE3_3.ps1`。真实入口：`RUN_GATE3_3_REAL_STREAMING.ps1`。真实设备未在目标 Windows 环境返回 0 时，只能引用已有证据并标注待复测。

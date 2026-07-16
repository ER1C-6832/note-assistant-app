# Gate 4 Final Acceptance Report

状态：Implementation Complete；等待当前目标工作树 4.4 cumulative + real-stop 返回 0 后签署 Accepted  
最终收口基线：`9f37041cc5a955d0f943e552a465a8e9b02046a0`

## 1. 完成结论

Gate 4 已完成从真实 TTS binary 到真实两轮连续对话的单进程闭环：

```text
real TTS Opus binary
-> bounded private ingress
-> PyAV decode/resample
-> PyAudio physical output
-> actual PlaybackEnded
-> exactly-once next capture
-> second real voice turn and playback
```

## 2. 自动与 Fake 证据

已实现并归档：

- hello/audio_params validation；
- bounded probe/encoded/PCM queues；
- no payload in Runtime event queue；
- Fake decode/output/last-sample drain；
- corrupt/overflow/underflow/zero-audio/watchdog；
- duplicate/stale generation；
- playback cancel/failure；
- cancelled playback 后迟到 physical-end 不得重新 auto-next；
- exactly-once auto-next ledger；
- next capture failure recovery；
- stop/mode/disconnect/disable/shutdown precedence；
- Fake two-turn no-overlap scenario。

Gate 4.2 用户侧证据：330 tests passed，Gate 4 定向 58 passed。Gate 4.3 增加 12 tests；发现的 disabled late-end 和 Fake runner token 问题已修复，用户确认修复后无问题。

## 3. Windows Real 证据

### 3.1 Protocol Probe

`real_gate_complete`：

- wire：Opus / 24 kHz / mono / 20 ms；
- 130 packets；
- PyAV decode 成功；
- no output device；
- no payload persistence；
- no pending assistant task。

### 3.2 One-turn Playback

`real_gate_complete`：

- 628 packets，43,024 encoded bytes；
- 602,880 decoded/played sample frames；
- natural physical drain；
- encoded/PCM overflow=0；
- 人工听感通过；
- output/worker/buffer/task 归零。

单次 latency sample：first packet→decode 5.66 ms，first packet→playback start 49.97 ms，terminal→physical drain 228.782 ms。该单次结果不代表 p95。

### 3.3 Real Two-turn

`real_gate_complete`：

- turn 1：130 packets，124,800 decoded/played frames；
- turn 2：249 packets，239,040 decoded/played frames；
- auto-next request/start=2；
- capture generation `1 -> 2`；
- turn token `1 -> 2`；
- capture/playback overlap=0；
- 人工听感通过；
- 最终 pending assistant tasks=[]。

### 3.4 Stop during Playback

当前交付新增 `verify_gate4_4_real_stop_during_playback.py`。最终签署要求：

- 回复已实际开始播放；
- runner 发出 user stop；
- audible interruption 人工确认；
- natural playback summary 不创建；
- auto-next request count 不增加；
- session inactive；
- output/worker/PCM/capture/uplink/VAD/task 全部归零。

## 4. 资源终态矩阵

| 场景 | 结束语义 | 自动续轮 | 资源结果 |
|---|---|---:|---|
| natural physical drain | PlaybackEnded | streaming 时 exactly 1 | playback 归零后 capture 启动 |
| user stop | PlaybackCancelled | 0 | playback/session/capture 归零 |
| mode switch | PlaybackCancelled | 0 | playback 先关闭，再切模式 |
| disconnect | cancelled/stale | 0 | generation 失效，不重放 |
| disable | cancelled/stale | 0 | phase disabled，所有资源归零 |
| shutdown | cancelled | 0 | bounded close，task=[] |
| decoder/output/watchdog failure | PlaybackFailed | 0 | error 可见，资源关闭 |
| duplicate/stale end | no-op | 0 | state/effect 不变 |

## 5. 隐私与架构

- 单 Python Runtime、单 qasync loop、单 Controller state writer；
- 无 Sidecar、localhost HTTP、外部 ffmpeg 或第二 Runtime；
- Opus/PCM 默认不落盘；
- Runtime state、日志和报告不包含原始 payload、token 或完整 identity；
- callback 不 decode、不写状态；receiver 不等待 playback。

## 6. 非目标

Gate 4 不声明 MCP、KWS、AEC、NS/AGC、声学全双工 barge-in 或完整设备热插拔恢复。README 和 Master Plan 已同步当前真实边界。

## 7. 最终命令

```powershell
python tools/verify_gate4_4_cumulative.py
python tools/verify_gate4_4_real_stop_during_playback.py
```

两者返回 0 后，Gate 4 可从 `Implementation Complete` 标记为 `Accepted`，下一阶段进入 Gate 5。

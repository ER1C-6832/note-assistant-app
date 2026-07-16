# ADR-008：真实 TTS Playback、Physical Drain 与自动续轮

状态：Accepted  
日期：2026-07-16

## Context

Gate 3 已具备真实麦克风、Opus 上行和连续对话提交，但回复完成仍以 transcript/TTS terminal 临时判断，无法证明扬声器已经消费最后一个样本，也不能安全自动打开下一轮麦克风。

## Decision

1. 原始 downlink Opus 只进入专用有界 ingress，不进入 Runtime event queue 或 AssistantState。
2. 独立 `AssistantPlaybackEngine` worker 负责 decode、resample、PCM buffer 和 output 协调；capture worker 与 playback worker 生命周期分离。
3. 使用 PyAV 解码/重采样，使用 PyAudio callback 消费 PCM；callback 不 decode、不修改状态、不阻塞等待 producer。
4. natural `PlaybackEnded` 只在 input terminal、decode flush、所有队列清空、最后真实 sample 已消费且 output inactive 后产生。
5. 自动续轮只由当前 generation/token 的 natural `PlaybackEnded` 触发；Controller 使用有界 ledger 提供 exactly-once 防线。
6. stop、mode switch、disconnect、disable、shutdown、失败、取消和 stale callback 均禁止续轮。
7. 默认禁止 capture/playback overlap；Gate 4 不实现 acoustic/full-duplex barge-in 或 AEC。

## Consequences

- transcript 和 `tts/stop` 可以先到，但不能让 UI 或状态机声称播放完成；
- receiver、Qt 主线程和 Runtime event queue 不承担音频热路径负载；
- Windows output device 选择和 PyAV decoder output 格式必须显式规划；
- 用户 stop 可有界释放 output/worker/buffer，并且不会产生假 natural end；
- 第二轮启动具备确定性事件顺序和 generation/token correlation；
- 后续 Gate 6 若实现插话，必须在本 ADR 的 ownership 和 no-overlap 默认规则上显式扩展，而不能旁路 playback cancel。

## Evidence

Gate 4.0、4.2、4.3 Windows runner 已分别证明真实协议、真实一轮播放和真实两轮闭环。Gate 4.4 cumulative 与 real-stop runner 是发布前最终证据入口。

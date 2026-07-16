# PC Assistant Runtime Master Plan — Gate 4 Amendment

状态：Accepted  
适用基线：`9f37041cc5a955d0f943e552a465a8e9b02046a0`

## 修改结论

Master Plan 的 Gate 4 状态更新为已完成。当前单进程 Runtime 已拥有：

- 真实 Opus TTS binary downlink；
- PyAV decode/resample；
- PyAudio output callback；
- physical drain 驱动的 actual PlaybackEnded；
- actual PlaybackEnded 唯一自动续轮；
- 真实两轮连续对话；
- stop/disconnect/disable/shutdown 的有界播放取消；
- generation/token/stale rejection；
- 资源和任务终态检查。

## 不改变的后续范围

Gate 4 不提前实现：

- Gate 5 MCP；
- Gate 6 AEC、设备增强和声学 barge-in；
- Gate 6.5 KWS；
- Gate 7 延迟分位数与长期指标。

单次 Real runner 的 latency 只作为 sample，不得宣称 p95。

## 权威引用

- `docs/spec/gate4/GATE4_FINAL_FREEZE.md`；
- `docs/adr/ADR-008-gate4-playback-and-auto-next-turn.md`；
- `docs/report/GATE4_FINAL_ACCEPTANCE_REPORT.md`。

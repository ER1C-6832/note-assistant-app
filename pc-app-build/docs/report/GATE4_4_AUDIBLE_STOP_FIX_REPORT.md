# Gate 4.4 可听中断验收修复报告

基线：`6cc494ad9cb2046e99839da82a51631e7dbfffe0`。

## 日志结论

真实 stop 链路已经正确完成：播放被标记为 `playback_cancelled`，没有 natural summary，没有自动续轮，且输出、buffer、capture、uplink、VAD 与 assistant task 均归零。人工确认失败的原因是 runner 在 `PLAYING` 后仅等待约 0.35 秒，设备 callback 已启动但人耳未必已经听到足够内容。

## 修复

- playback watchdog 在物理输出启动后每 100 ms 发出轻量 `PlaybackProgressUpdated`；不携带 PCM/Opus payload。
- Real stop runner 不再用盲目 sleep；默认等待 `played_frames` 达到 1.5 秒对应的真实 sample frames 后再 stop。
- 可通过 `GATE4_4_AUDIBLE_BEFORE_STOP_SECONDS` 调整为 0.75～5 秒。
- 回复短于阈值时返回 `real_gate_blocked`，提示换更长回复重试，而不是判定产品失败。
- SSL/URL open EOF 激活错误归类为环境阻塞。
- 按要求暂时移除 README 相关 Gate 4.4 测试，不修改 README。

## 覆盖后验证

```powershell
python tools/verify_gate4_4_cumulative.py
python tools/verify_gate4_4_real_stop_during_playback.py
```

真实 runner 应在实际播放约 1.5 秒后中止。人工听到明显截断且没有重新开麦时输入 `y`。

## 本地验证

```text
compileall: passed
Black check: passed
Ruff check: passed
Gate 4.4 source/docs contracts: 5 passed
Playback harness including live progress: 17 passed
```

当前容器没有完整 Gate 1～4 仓库树和 Windows 音频设备，因此未声称执行完整累计 pytest 或真实扬声器验收。

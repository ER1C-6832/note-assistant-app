# Gate 4.0 增量实施报告

状态：通过；真实协议事实已冻结为 Gate 4.1 输入

验收 HEAD：`rewrite/single-process-runtime@648cfb8801fefafc5a5d450eb1d98f841b0b0556`

## 本次完成

- `ServerHello` 增加经过校验的 `DownlinkAudioFormat`；缺失、非法和暂不支持的参数显式 fail-closed；
- 新增 metadata-only、bounded downlink probe，只在内存中短暂持有待解码 packet，不写 Opus/PCM/WAV；
- 新增 `ProbingRealWebSocketTransport`，binary payload 非阻塞进入专用 probe queue，Runtime event queue 仍只收到 `size_bytes`；
- 新增 PyAV Opus 可解码性探测、TTS state 顺序、packet size/arrival interval、terminal 相对顺序和资源终态统计；
- 新增 Windows Real runner；不打开 output device，不激活 `TTS_PLAYBACK`；
- 新增 Gate 4.0 protocol/probe/transport/architecture tests。

## 文件

修改：

- `apps/notes-pyside/app/assistant/protocol/events.py`
- `apps/notes-pyside/app/assistant/protocol/message_router.py`

新增：

- `apps/notes-pyside/app/assistant/network/downlink_probe.py`
- `apps/notes-pyside/app/assistant/network/probing_websocket_transport.py`
- `tools/verify_gate4_0_real_downlink_probe.py`
- `tests/gate4_0/*`
- 本报告

## 刻意未做

- 未实现 decoder/resampler/playback engine；
- 未打开 PyAudio output；
- 未生成 `PlaybackStarted`/`PlaybackEnded`；
- 未自动进入下一轮；
- 未冻结 Gate 4 Draft 中的真实格式和容量参数。

## 已执行验证

- `python -m compileall`：通过；
- Black：通过；
- Ruff：通过；
- 最小依赖隔离回归：`17 passed`，覆盖新 protocol/probe/transport 以及既有 Gate 2.3 router 契约；
- 完整累计 pytest：当前执行环境没有完整仓库与 Windows 音频环境，未执行。

## Windows 真实验收结果

用户执行 `python tools/verify_gate4_0_real_downlink_probe.py`，返回 `status=real_gate_complete`：

- hello：Opus / 24,000 Hz / mono / 20 ms；
- binary packets：130；size 48～107 bytes，median 68 bytes；
- TTS：`start -> sentence_start -> sentence_end -> sentence_start -> stop`；
- first/last binary 均在 terminal 前；
- PyAV decode 成功，decoded 48,000 Hz / 2 channels / 960 sample frames；
- overflow/unarmed/stale 均为 0；
- 未落盘、未打开 output，最终 probe task 与 assistant task 均为空。

注意：wire format 与 decoded PCM format 不同，已作为 Gate 4.1 format planner 的冻结输入。

## 验收命令

覆盖后在 `pc-app-build` 执行：

```powershell
python -m pip install -e ".[dev]"
python tools/verify_gate4_0_real_downlink_probe.py
```

返回码：

- `0`：真实 hello format、TTS/binary 顺序和至少一个 PyAV decode 均通过；
- `1`：实现/协议验收失败；
- `2`：激活、网络、设备或依赖环境阻塞。

真实 runner 已返回 0；实际协议参数已写回 Gate 4 Spec。此前完整 pytest 的 collection error 是 `DownlinkAudioFormat` 未从 `protocol.__init__` 导出，随 Gate 4.1 增量修复。

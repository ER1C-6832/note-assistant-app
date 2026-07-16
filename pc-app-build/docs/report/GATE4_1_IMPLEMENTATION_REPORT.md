# Gate 4.1 增量实施报告

状态：Fake Playback Foundation 候选，等待目标工作树累计回归

输入 HEAD：`rewrite/single-process-runtime@648cfb8801fefafc5a5d450eb1d98f841b0b0556`

## 4.0 冻结输入

真实 probe 已返回 `real_gate_complete`：

- wire：Opus / 24,000 Hz / mono / 20 ms；
- 130 个 binary packet，48～107 bytes，median 68 bytes；
- TTS：`start -> sentence_start -> sentence_end -> sentence_start -> stop`；
- binary 全部早于 terminal；
- PyAV decoded frame：48,000 Hz / 2 channels / 960 sample frames；
- overflow、unarmed binary、stale event 均为 0；
- 未落盘、未打开 output，最终任务归零。

因此 4.1 显式区分 wire format 与 decoded PCM format。

## 本次完成

- 修复 `DownlinkAudioFormat` 未从 `app.assistant.protocol` 导出导致的全量 pytest collection error；
- 新增独立 `assistant/playback` foundation，不复用 capture/VAD worker 生命周期；
- 新增 immutable stream/packet/PCM/signal/summary models；
- 新增 2,000 ms encoded budget 与 terminal 保留槽；20 ms wire 下容量为 100 packet；
- 新增线程安全有界 PCM buffer；Gate 4.1 Fake 48 kHz/stereo/PCM16 下容量为 384,000 bytes；
- 新增 non-blocking callback consumption、partial chunk、underflow、terminal+full drain；
- 新增唯一 playback worker、early packet staging、generation/sequence stale rejection；
- `PlaybackStartedSignal` 只在 Fake output 消费首批真实 PCM 后产生；
- `PlaybackEndedSignal` 只在 input terminal、decode flush、PCM empty、last sample consumed 后产生；
- cancel/failure/zero-audio 不伪造自然 PlaybackEnded；
- 新增 PyAV decoder boundary、format planner、PyAudio fail-closed scaffold；
- `TTS_PLAYBACK` capability 保持 not-ready，真实设备接入属于 Gate 4.2；
- 更新 4.0 报告和 Gate 4 Frozen Spec。

## 增量文件

修改：

- `apps/notes-pyside/app/assistant/protocol/__init__.py`
- `docs/report/GATE4_0_IMPLEMENTATION_REPORT.md`
- `docs/spec/gate4/GATE4_SPEC_INDEX.md`
- `docs/spec/gate4/GATE4_TTS_PLAYBACK_AND_TWO_TURN_SPEC.md`

新增：

- `apps/notes-pyside/app/assistant/playback/*.py`
- `tests/gate4_1/*`
- `tools/verify_gate4_1_fake_playback.py`
- 本报告

## 本地实际验证

隔离环境执行：

```text
python -m pytest -W error -q tests/gate4_1
25 passed

python tools/verify_gate4_1_fake_playback.py
status=fake_gate_complete
encoded_packets_received=3
decoded_sample_frames=2880
played_sample_frames=2880
playback_started_count=1
playback_ended_count=1
final worker/output=false
```

另执行 Gate 4.0 protocol import 回归与 Gate 4.1 合并隔离测试：`35 passed`；compileall、Black check、Ruff check 均通过。完整仓库不在当前执行环境，因此未冒充执行 Gate 1.7～4.1 累计回归。

## 覆盖后的验收命令

在 `pc-app-build` 下先执行完整累计测试：

```powershell
python -m compileall -q apps tools tests
python -m black --check apps tools tests
python -m ruff check apps tools tests
python -m pytest -W error tests
```

再执行当前 Gate 定向验收：

```powershell
python -m pytest -W error tests/gate4_0 tests/gate4_1 -q
python tools/verify_gate4_0_real_downlink_probe.py
python tools/verify_gate4_1_fake_playback.py
```

预期：

- 全量 pytest 不再发生 `DownlinkAudioFormat` import collection error；
- Gate 4.0 real runner 继续返回 0；
- Gate 4.1 fake runner 返回 0；
- Fake runner 不打开扬声器、不保存 Opus/PCM；
- `TTS_PLAYBACK` 仍为 not-ready。

## 未做

- 未把 playback engine 接入 RealWebSocketTransport 产品 composition root；
- 未打开真实 PyAudio output；
- 未把 playback signals 投递到 Controller event pump；
- 未激活 QML buffering/speaking；
- 未自动进入第二轮。

以上属于 Gate 4.2/4.3，避免 4.1 foundation 越界。

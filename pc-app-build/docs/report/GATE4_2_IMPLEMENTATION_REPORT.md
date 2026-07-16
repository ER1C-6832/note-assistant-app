# Gate 4.2 精简实施报告

状态：Implementation candidate，等待 Windows real playback 与人工听感验收  
输入基线：`bd6d688268b3ef4ec2ea1926ffc29df95b82b256` (`rewrite/single-process-runtime`)

## 完成范围

- 接入真实 WebSocket TTS binary downlink，payload 绕过 Runtime event queue；
- 接入 PyAV Opus decode 和显式 PCM resample；
- 接入 PyAudio callback output、underflow padding 和真实 sample consumption；
- actual `PlaybackStarted` 只在首个真实 PCM 被 output 消费后产生；
- actual `PlaybackEnded` 只在 terminal、decode flush、PCM 清空、最后真实 sample 消费且 PortAudio stream inactive 后产生；
- 增加 stream-start、decoder-progress、physical-drain 和 output-close 有界 watchdog；
- stop、mode switch、disconnect、disable、shutdown 取消播放，不产生自然结束；
- 激活一轮 buffering/speaking/error 投影和 TTS playback capability；
- Gate 4.3 自动第二轮保持关闭。

## 关键参数

- wire：Opus / 24,000 Hz / mono / 20 ms；
- output 候选优先级：48 kHz stereo、48 kHz mono、24 kHz mono、44.1 kHz stereo、44.1 kHz mono；
- encoded buffer：2,000 ms；PCM buffer：2,000 ms；startup prebuffer：2 chunks；
- start watchdog：6 s；decoder watchdog：6 s；drain watchdog：8 s；close budget：2 s。

## 本次验证

已执行：

```text
compileall: passed
Black check: passed
Ruff check: passed
Gate 4.1 + Gate 4.2 isolated: 38 passed
Gate 4.2 fake runner: fake_gate_complete
playback_started_count=1
playback_ended_count=1
auto_next_turn_count=0
played_sample_frames=decoded_sample_frames=2880
```

当前执行环境无法解析 `github.com`，因此没有重新拉取完整工作树执行累计 317+ 测试；Windows 真实扬声器也未在本环境执行。覆盖后必须由目标机完成下列验收。

## 完整验收命令

在 `pc-app-build` 目录执行：

```powershell
python -m compileall -q apps tools tests
python -m black --check apps tools tests
python -m ruff check apps tools tests
python -m pytest -W error tests
python tools/verify_gate4_2_fake_playback.py
python tools/verify_gate4_2_real_playback.py
```

真实 runner 要求说一句命令并人工确认完整、非静音、速度和音调正常。返回码：0=通过，1=实现/验收失败，2=环境、设备、网络、激活或人工确认阻塞。

## 非目标与限制

- 不自动开启第二轮；
- 不实现 full-duplex barge-in、AEC、KWS 或 MCP；
- 不保存 Opus/PCM；
- 不启动外部 ffmpeg 或第二 Runtime/event loop。

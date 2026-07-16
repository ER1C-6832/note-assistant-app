# Gate 3.2 Real PTT 与共享音频管线实施报告

原实施基线：`2d23f6dd08e7b32d2061f0ec4ed3df4bb8f58a25`  
Gate 3.4 契约收口基线：`9f204735e338ff7e87010ca58e628406673e13ae`

## 1. 范围

Gate 3.2 激活 PTT 主链路，不实现 TTS 播放、自动第二轮、插话或 KWS：

```text
AssistantPanel PTT
-> AssistantViewModel
-> single Controller event pump
-> Reducer effects
-> one PyAudio input stream
-> bounded PCM queue
-> one AudioEngine worker + PyAV Opus encoder
-> bounded Opus queue
-> qasync uplink owner
-> existing single WebSocket sender
```

## 2. 当前依赖安装契约

PyAudio 和 PyAV 已是 `pc-app-build/pyproject.toml` 的正式 runtime dependencies：

```toml
"PyAudio>=0.2.14,<0.3"
"av>=13,<17"
```

唯一正式安装命令：

```powershell
python -m pip install -e ".[dev]"
```

历史 `INSTALL_GATE3_2_AUDIO_DEPS.ps1` 不再是验收资产。Git 历史没有需要继续保留、且 pyproject 无法表达的 Windows 特殊安装逻辑，因此 Gate 3.4 更新 architecture test，不创建空壳脚本。

## 3. 平台音频

- 16 kHz、mono、PCM16 little-endian；
- 20 ms / 320 samples / 640 bytes；
- Opus VOIP 24 kbps；
- PyAudio callback 只复制 PCM 并投递有界队列；
- PCM ingress 8，满时 drop-oldest；
- encoded uplink 16，满时失败当前 turn；
- one `assistant-audio-worker-*`；
- binary send 经过 existing single sender。

## 4. 生命周期

connection_generation、capture_generation 与 voice_turn_token 拒绝陈旧事件。disable、disconnect、recovery、mode change 和 shutdown 取消 uplink、关闭 capture、释放 lease。stop/cancel/release 幂等。

## 5. 协议时序

```text
PTT press
-> listen/start mode=manual
-> capture
-> Opus binary upload

PTT release
-> bounded stop/drain
-> useful audio: listen/stop
-> no useful audio: abort
-> STT / assistant/TTS transcript
-> VoiceTurnCompleted
```

Gate 4 前只接收 transcript/state，不播放下行音频。

## 6. 验收入口

自动验收已经并入当前累计入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

独立真实 PTT Python verifier 继续保留：

```powershell
python pc-app-build/tools/verify_gate3_2_real_ptt.py
```

历史 Real runner 可以继续作为人工包装，但当前 Gate 3.4 不要求恢复已被累计 runner 取代的旧根目录安装脚本。

## 7. 已知边界

- 不播放 TTS；
- 不自动恢复下一轮；
- launcher 拖拽/PTT 长按组合不在本 Gate；
- 蓝牙、热插拔、AEC/NS/AGC 不在本 Gate。

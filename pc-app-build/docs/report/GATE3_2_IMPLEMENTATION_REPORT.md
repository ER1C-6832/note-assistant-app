# Gate 3.2 Real PTT 与共享音频管线实施报告

基线提交：`2d23f6dd08e7b32d2061f0ec4ed3df4bb8f58a25`

## 1. 范围

Gate 3.2 激活按住说话主链路，但不实现 TTS 播放、连续对话、插话或 KWS：

```text
AssistantPanel 独立 PTT 按钮
-> AssistantViewModel
-> AssistantController event pump
-> Reducer
-> StartPushToTalk / StopPushToTalk effects
-> one PyAudio input stream
-> bounded PCM queue
-> one audio worker + one Opus encoder
-> bounded Opus queue
-> qasync uplink task
-> existing WebSocket sender
```

悬浮 Aurora launcher 继续只负责展开、收起和拖动。拖动与未来 launcher 长按手势的最终裁决保持未决，本 Gate 不把 PTT 绑定到可拖动 launcher。

## 2. 平台音频

- 16,000 Hz、mono、PCM16 little-endian；
- 20 ms / 320 samples / 640 bytes；
- Opus VOIP，24 kbps；PyAV wheel 内含 FFmpeg/libopus 运行库，不依赖 PATH 上的外部 DLL；
- PyAudio callback 只复制 PCM 帧并投递有界队列；
- PCM ingress 容量 8，满时丢最旧；
- encoded uplink 容量 16，满时失败当前语音回合；
- 编码在唯一 `assistant-audio-worker-*` 工作线程执行；
- WebSocket 二进制发送仍经过现有单 sender。

## 3. 生命周期与 generation

- `connection_generation` 丢弃旧 WebSocket 事件；
- `capture_generation` 拒绝旧 callback、旧编码包和旧 stop；
- `voice_turn_token` 归属 STT、助手文本和 TTS 状态；
- 一个进程只有一个逻辑麦克风租约；
- disable、disconnect、transport recovery 和 shutdown 均取消 uplink、关闭 capture、释放租约；
- shutdown 有界等待，不保留 `assistant-audio-*` task 或 worker。

## 4. 协议时序

```text
PTT press
-> listen/start mode=manual
-> capture start
-> Opus binary upload

PTT release
-> bounded capture stop
-> drain encoded packets
-> listen/stop（检测到有效语音）
   或 abort（无有效语音）
-> STT / assistant text / TTS state
-> VoiceTurnCompleted
```

Gate 4 前只验证下行文本/TTS 状态，不播放二进制 TTS 音频。

## 5. Gate 3.1 顺带修复

- `AssistantPanel.qml` 和语音设置组件使用非空 fallback projection，避免 QML teardown 期间访问已销毁 ViewModel；
- Gate 2.7 Fake sentinel SQLite connection 在 `finally` 中显式关闭，修复 Windows 临时目录清理时的 `WinError 32`；
- 历史 Gate 2.7 测试继续检查持久化 Python 验收资产，而不固定旧根目录 runner；
- 历史 Gate 3.1 Fake PCM 使用冻结的 640-byte 帧契约。

## 6. 验收

依赖安装：

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_GATE3_2_AUDIO_DEPS.ps1
```

自动验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_2.ps1
```

真实语音验收：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_2_REAL_PTT.ps1
```

真实脚本要求用户说一句真实命令，并验证：

- 默认麦克风成功打开；
- captured / encoded / uploaded 均大于 0；
- 无 uplink overflow；
- stop 后无 capture、worker、uplink task 或麦克风租约；
- 服务端返回可读 STT；
- 服务端返回可读助手文本或 TTS transcript；
- 输出不包含 token、完整 identity 或完整 session id。

只有自动脚本与 Real PTT 脚本均返回 `0`，才允许声明 Gate 3.2 完成。

## 7. 已知边界

- 当前不播放 TTS 音频；
- 当前不自动恢复下一轮监听；
- 当前 PTT 产品入口位于展开面板，launcher 的拖动/长按手势决策留到后续 UI 收口；
- Windows 蓝牙、热插拔、AEC/NS/AGC 不在本 Gate。

## 8. 本地确定性验证

```text
Gate 3.2：14 passed
受影响历史契约 + Gate 3.2：45 passed，1 skipped（本容器未安装 PySide6）
Gate 2.7 Fake：fake_gate_complete
Gate 3.2 Fake PTT：gate3_2_fake_ptt_verified
PyAV/libopus 单帧编码：通过
Python 3.10 AST：50 files passed
Black / Ruff / compileall：通过
```

真实 Windows 麦克风、PortAudio 设备打开以及真实服务端 STT/回复必须由 `RUN_GATE3_2_REAL_PTT.ps1` 完成，未运行前不声明 Real Gate 通过。

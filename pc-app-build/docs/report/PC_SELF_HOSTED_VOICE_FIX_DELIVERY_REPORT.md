# PC 自建小智语音链路修复交付报告

日期：2026-07-21
分支：`rewrite/single-process-runtime`

## 1. 交付结论

本次修复解决了 PC 客户端连接自建 `xiaozhi-esp32-server` 后发现的两个独立问题：

1. 按住说话时，设备轮询线程与录音启动线程并发操作 PyAudio/PortAudio，触发 Windows 原生访问冲突 `0xC0000005`。
2. 客户端在服务端刚发出早期 `tts start` 时就启动六秒音频首包看门狗，把 LLM 与 TTS 生成耗时误算为播放卡死，导致语音生成完成前主动断开连接。

修复后，设备轮询会在录音或播放占用原生音频资源期间暂停，并在两者都空闲后恢复；播放首包看门狗从真实媒体边界 `tts sentence_start` 开始计时。

## 2. 根因与修改

### 2.1 PyAudio 原生崩溃

故障栈显示：

- 路由观察线程位于 `PyAudio.terminate()`；
- 录音启动线程同时位于 `PyAudio.__init__()`；
- 两者分别由设备快照轮询和 `SupervisorCaptureAdapter` 触发。

修改内容：

- `PollingAudioRouteObserver` 增加 `pause()` / `resume()`；
- `pause()` 会先标记暂停，再等待已经进入的设备枚举退出，关闭检查与枚举之间的竞态窗口；
- `AudioSessionSupervisor` 在 capture/playback 非空闲时暂停轮询，仅在两者均空闲时恢复；
- 输出设备能力探测通过同一个 registry native-operation 锁串行化。

### 2.2 TTS 首包误超时

自建服务端的真实时序为：

1. ASR 完成后发送 `tts start`；
2. 执行 LLM 推理和 TTS 生成；
3. 准备发送音频时发送 `tts sentence_start`；
4. 紧接着发送 Opus 二进制包。

原客户端从步骤 1 开始六秒倒计时。本次会话的 TTS 恰好在第六秒完成，客户端先关闭了连接。

修改后只在第一条 `tts sentence_start` 建立本轮播放流并启动无二进制首包看门狗；后续同轮 `sentence_start` 不会重建或取消正在播放的流。早期 `tts start` 仍正常进入会话状态机，用于表达“正在思考”。

## 3. 验证结果

- Gate 4 + Gate 6 回归：`160 passed`；
- 完整 PC 自动化测试：`512 passed`；
- 最终定向回归：`30 passed`；
- Black：全部修改文件通过；
- Ruff：全部修改文件通过；
- Windows 真实路由/麦克风：`gate6_1_real_route_complete`；
- Realtek 麦克风 3 秒采集：47,680 samples、0 callback errors；
- 验证结束：route observer 已关闭，microphone lease 已释放，无 pending route task 或开放 duplex stream。

## 4. 用户验收步骤

在 `pc-app-build` 目录执行：

```powershell
.\venv\Scripts\python.exe tools\verify_gate3_2_real_ptt.py
```

在提示后的五秒内说一句完整中文。预期：

- `status` 为 `real_gate_complete`；
- `stt_text` 有正确中文；
- `assistant_text` 非空；
- 不再出现 `playback_stream_start_timeout`；
- 能听到自建服务端返回的音色。

随后用故障捕获方式启动 GUI：

```powershell
New-Item -ItemType Directory -Force .\logs | Out-Null
.\venv\Scripts\python.exe -X faulthandler main.py 2>&1 |
    Tee-Object -FilePath .\logs\pc-runtime.log
```

依次验收：

1. 连续执行十次“按住说话—说一句—松开”，应用不闪退；
2. 每轮都能显示 STT 和助手回复，并正常播放语音；
3. 开启连续对话，说完保持安静，至少完成两轮；
4. 返回普通界面后再次按住说话，仍可正常开始录音；
5. 日志中没有 `access violation`、`playback_stream_start_timeout` 或残留音频任务错误。

## 5. 边界

本次只修改 PC v2 客户端。服务端、Android 客户端、模型和 TTS 配置均未修改。LLM/TTS 本身的响应速度仍由自建服务端所选模型与外部服务决定，但不再被错误的六秒播放首包看门狗截断。

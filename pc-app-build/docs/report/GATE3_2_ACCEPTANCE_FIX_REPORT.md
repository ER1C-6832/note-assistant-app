# Gate 3.2 acceptance fix report

修复基线：`cb2aebe8ad7c4889b77bc170dd395bd90456c926`

## 1. 修复原因

Gate 3.2 已替换根目录当前 Gate runner，历史 Gate 3.1 架构测试仍固定要求：

```text
VERIFY_GATE3_1.ps1
RUN_GATE3_1_UI_SMOKE.ps1
```

当交付目录只保留当前 `VERIFY_GATE3_2.ps1` 与 `RUN_GATE3_2_REAL_PTT.ps1` 时，Runtime、UI smoke 和 Real PTT 均正常，但全量 pytest 会因历史文件名不存在而失败。

## 2. 修复方式

Gate 3.1 历史契约改为检查长期持久化资产：

```text
pc-app-build/tools/verify_gate3_1_ui_shell.py
pc-app-build/docs/report/GATE3_1_IMPLEMENTATION_REPORT.md
```

同时动态查找当前仍覆盖 `tests/gate3_1` 的 `VERIFY_GATE*.ps1`，并验证：

- 当前 verifier 保留 Gate 3.1 回归；
- 当前 verifier 继续执行 `verify_gate3_1_ui_shell.py`；
- PowerShell 保留 `$LASTEXITCODE -ne 0` 与 `exit 1` fail-fast。

不再要求根目录永久保留旧 Gate runner 文件名。该模式允许 Gate 3.3、Gate 4 等后续 verifier 继续演进。

## 3. Real PTT 验收状态

用户在 Windows 真实环境完成 Gate 3.2 Real PTT：

```text
status: real_gate_complete
captured_frames: 250
encoded_frames: 250
uploaded_frames: 250
dropped_pcm_frames: 0
uplink_overflow_count: 0
capture_stop_latency_ms: 47
stop_listen_latency_ms: 48
first_opus_upload_latency_ms: 204
pending_runtime_tasks: []
```

真实服务端返回了可读 STT 与助手 TTS transcript，音频采集、worker、uplink 和麦克风租约均已释放。

Gate 3.2 只要求音频上行、STT 和可读回复文本。二进制 TTS 解码与扬声器播放仍属于 Gate 4.1，当前 `main.py` 能显示回复但尚无声音符合冻结边界。

## 4. 验收

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_2.ps1
```

本修复不修改 Runtime、音频管线、WebSocket、QML 或真实 PTT runner。

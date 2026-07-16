# Gate 4.4 验收日志修复报告

基线：`2db7186b9223fe78eb620b1adc715036fa082fe6` (`final runner`)

## 1. 累计测试中的 README 失败

失败不是 Gate 4 Runtime 逻辑问题。Gate 4.4 覆盖包中的 `README.md` 是仓库根文件，但若在 `pc-app-build` 目录内直接解压，它会错误落到 `pc-app-build/README.md`；测试读取的是仓库根 `README.md`。

本修复包继续保留正确的仓库根相对路径。必须从 `note-assistant-app` 仓库根目录覆盖，不能从 `pc-app-build` 目录覆盖。根 README 已明确写入：

```text
当前已实现范围不包含 MCP、KWS 或全双工声学插话
```

## 2. Real stop runner 的 watchdog 不一致

原 runner 自己最多等待 75 秒，但 Runtime 内部 `streaming_response_timeout_ms` 仍是默认 20 秒。因此服务端生成较慢时，状态机会先产生 `streaming_response_timeout`，runner 随后报告失败。

修复后：

- runner 使用验收专用初始状态，把内部 response watchdog 默认设为 90 秒；
- 可通过 `GATE4_4_RESPONSE_TIMEOUT_SECONDS` 调整，范围限制为 30～180 秒；
- runner 外部等待预算为内部 watchdog 再加 30 秒；
- 明确的 `streaming_response_timeout` 返回 `real_gate_blocked`（退出码 2），并给出重试提示，不再错误归类为产品逻辑失败；
- 提示词给出能稳定产生较长 TTS 的示例命令。

该改动只影响 Real 验收工具，不修改产品默认 20 秒 response timeout，也不改变 transport、playback、auto-next 或状态机产品行为。

## 3. 本地检查

```text
compileall: passed
Black check: passed
Ruff check: passed
log-fix contract tests: 2 passed
```

当前环境没有完整仓库和 Windows 音频设备，未执行 361 项累计测试和真实 stop。覆盖后在 `pc-app-build` 执行：

```powershell
python tools/verify_gate4_4_cumulative.py
python tools/verify_gate4_4_real_stop_during_playback.py
```

第一个命令应返回 `status=passed`。第二个命令在听到回复开始后自动 stop，人工输入 `y` 后应返回 `status=real_gate_complete`。

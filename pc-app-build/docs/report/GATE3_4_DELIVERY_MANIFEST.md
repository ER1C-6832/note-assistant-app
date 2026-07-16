# Gate 3.4 增量覆盖交付清单

基线 HEAD：`9f204735e338ff7e87010ca58e628406673e13ae`  
分支：`rewrite/single-process-runtime`  
交付形式：从仓库根目录解压并覆盖同名文件。未修改远程仓库，未创建 commit。

## 1. 新增文件

- `VERIFY_GATE3_3.ps1`
- `RUN_GATE3_3_REAL_STREAMING.ps1`
- `pc-app-build/docs/adr/ADR-007-current-pc-audio-and-gate3-boundary.md`
- `pc-app-build/docs/report/GATE3_4_FINAL_ACCEPTANCE_REPORT.md`
- `pc-app-build/docs/report/GATE3_4_DELIVERY_MANIFEST.md`
- `pc-app-build/tests/gate3_3/test_gate3_3_capability_projection.py`
- `pc-app-build/tests/gate3_4/conftest.py`
- `pc-app-build/tests/gate3_4/test_gate3_4_architecture.py`
- `pc-app-build/tests/gate3_4/test_gate3_4_controller_lifecycle.py`
- `pc-app-build/tests/gate3_4/test_gate3_4_state_semantics.py`

## 2. 修改文件

- `pc-app-build/apps/notes-pyside/app/assistant/controller.py`
- `pc-app-build/tools/verify_gate3_3_fake_streaming.py`
- `pc-app-build/tests/gate3_1/test_gate3_1_view_model.py`
- `pc-app-build/tests/gate3_2/test_gate3_2_architecture.py`
- `pc-app-build/docs/PC_ASSISTANT_RUNTIME_MASTER_PLAN.md`
- `pc-app-build/docs/amendments/PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE3_AMENDMENT.md`
- `pc-app-build/docs/spec/gate0/CONCURRENCY_OWNERSHIP_SPEC.md`
- `pc-app-build/docs/spec/gate0/PC_RUNTIME_REWRITE_SPEC.md`
- `pc-app-build/docs/spec/gate3/GATE3_IMPLEMENTATION_PLAN.md`
- `pc-app-build/docs/spec/gate3/GATE3_STREAMING_CONVERSATION_SPEC.md`
- `pc-app-build/docs/spec/gate3/GATE3_TEST_AND_ACCEPTANCE_PLAN.md`
- `pc-app-build/docs/adr/ADR-002-pc-audio-stack.md`
- `pc-app-build/docs/report/GATE3_2_IMPLEMENTATION_REPORT.md`
- `pc-app-build/docs/report/GATE3_3_IMPLEMENTATION_REPORT.md`

## 3. 删除文件

无。

未添加空壳 `INSTALL_GATE3_2_AUDIO_DEPS.ps1`。当前依赖契约以 `pc-app-build/pyproject.toml` 中的 PyAudio/PyAV runtime dependencies 和 `python -m pip install -e ".[dev]"` 为准。

## 4. 状态语义与异常矩阵测试映射

### Gate 3.3 capability 投影

- `test_streaming_capability_is_active_and_view_model_projects_true`
  - `STREAMING_CONVERSATION` capability 为 active；
  - ViewModel 投影 `streamingCapabilityReady=True`；
  - TTS playback、barge-in 仍为 not-ready。

### Gate 3.4 Reducer/状态语义（14 个参数化测试实例）

- `test_valid_assistant_transcript_parks_session_without_auto_next_turn`
  - assistant text 与可读 TTS transcript 两种输入；
  - 进入 `WAITING_FOR_NEXT_TURN`；session 保持 active；audio idle；只取消 response timeout；不产生下一轮 capture effect。
- `test_playback_ended_is_not_activated_before_gate4`
  - Gate 4 前 `PlaybackEnded` 不得触发自动开麦。
- `test_voice_turn_completes_once_and_late_reply_is_a_noop_for_current_turn`
  - 当前 turn 最多完成一次；迟到回复不重开 turn。
- `test_stale_connection_session_and_turn_tokens_are_harmless`
  - 旧 connection/session/turn/timeout 事件无害 no-op。
- `test_timeout_then_session_stop_then_repeated_user_stop_finalizes_once`
  - response timeout、session stop、重复 stop 的确定顺序。
- `test_stop_then_late_end_of_speech_does_not_finalize_again`
  - stop 后迟到 EoS 不重复 finalize。
- `test_waiting_manual_stop_and_late_repeated_stop_complete_session_once`
  - WAITING 状态手动停止只完成一次。
- `test_uplink_overflow_ends_streaming_capture_without_leaking_logical_lease`
  - uplink overflow 后逻辑音频状态和麦克风 owner 归零。
- `test_disable_invalidates_late_streaming_reply_and_timeout`
  - disable 后迟到 reply/timeout 无效。
- `test_disconnect_during_thinking_enters_recovery_without_auto_capture`
  - thinking 断线进入 recovering；不立即自动 capture。
- `test_timeout_stop_disconnect_orders_emit_at_most_one_turn_stop`
  - timeout/stop/disconnect 三种排列；每个排列最多一个 turn stop effect，无自动下一轮。

### Gate 3.4 Controller/Effect 生命周期（6 个参数化测试实例）

- `test_waiting_for_next_turn_keeps_session_but_never_auto_restarts_capture`
  - WAITING 保持 session；capture/uplink/VAD/timer/worker/lease 归零；无第二次 listen/start。
- `test_end_of_speech_then_manual_stop_sends_only_one_turn_finalizer`
  - 使用受控异步屏障固定 effect 排列；只发送一次 `listen/stop`，不补发 `abort`，session stop 一次。
- `test_repeated_streaming_start_does_not_create_a_second_capture`
  - 连续模式重复 start 不产生第二 capture。
- `test_manual_stop_during_listening_or_speaking_is_single_and_leak_free`
  - waiting/speaking 两种状态；stop 单次且资源归零。
- `test_disable_and_shutdown_leave_no_assistant_tasks_or_audio_resources`
  - disable/shutdown 后无 capture/uplink/VAD/timer/worker/lease 或 pending `assistant-*` task。

### Gate 3.4 静态架构（6 个测试实例）

- cumulative PowerShell verifier fail-fast 与覆盖范围；
- real runner 0/1/2 exit contract；
- PyAudio/PyAV 由 `pyproject.toml` 管理；
- Runtime 源码不引入 subprocess/multiprocessing 第二 Python 助手进程；
- 总纲、修正案、ADR、最终报告存在并互相指向；
- turn/session finalize 账本有界且存在。

本次新增测试静态计数：27 个参数化测试实例。实际完整收集数量以目标工作树运行 `VERIFY_GATE3_3.ps1` 的 pytest 输出为准。

## 5. 运行时修改摘要

`EffectRunner` 增加两个有界幂等账本：

- `(streaming_generation, capture_generation, turn_token)` turn-finalize 账本，最多 256 项；
- `streaming_generation` session-stop 账本，最多 64 项。

这些账本只负责 effect 层协议终结去重，不建立第二状态机。它们覆盖事件泵已确定顺序、但异步 effect task 可能交错执行的窗口，保证重复 stop/timeout/disconnect cleanup 不重复发送 `listen/stop`、`abort` 或 `StreamingSessionStopped`。

## 6. 覆盖后必跑命令

```powershell
python -m pip install -e ".[dev]"
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE3_3.ps1
```

真实麦克风独立复测：

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE3_3_REAL_STREAMING.ps1
```

真实 runner 返回：0=通过，1=实现/验收失败，2=环境、设备、网络或激活阻塞。

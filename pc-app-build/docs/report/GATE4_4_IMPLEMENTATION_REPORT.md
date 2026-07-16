# Gate 4.4 实施报告

基线：`9f37041cc5a955d0f943e552a465a8e9b02046a0` (`fix runner`)

## 范围

Gate 4.4 是收口 Gate，不引入全双工插话。现有生产链路已在 `PlaybackEffectRunner` 中保证：`StopStreamingConversation`、disconnect、mode switch 和 shutdown 会先取消/关闭 playback coordinator，再继续原有 Runtime effect。

本次唯一生产代码修复：

- `TwoTurnConversationStateMachine._playback_ended()` 现在要求当前仍处于 active playback；这样 `RuntimePlaybackCancelled` 后迟到的同 generation physical-end callback 直接 no-op，不能重新触发自动续轮。

本次新增：

- stop-before-session-stop 行为测试；
- cancel 不产生 natural PlaybackEnded 的真实 Fake engine 测试；
- duplicate/stale/failure/disable/mode-switch 终态矩阵；
- canonical cumulative verifier；
- Windows stop-during-playback Real runner；
- Gate 4 Final Freeze、ADR、Master Plan amendment 和最终报告；
- README 真实性修正，不再声明 MCP/KWS/full-duplex barge-in 已完成。

## 已知输入证据

- Gate 4.2：330 项累计测试与 58 项 Gate 4 定向测试通过；真实一轮播放 `real_gate_complete`；
- Gate 4.3：真实两轮 runner `real_gate_complete`，auto-next request/start=2，overlap=0，退出无残留 task；
- Gate 4.3 日志问题已修复并由用户确认无问题。

## 当前环境验证

本交付环境执行：

```text
compileall: passed
Black check: passed
Ruff check: passed
Gate 4.4 isolated behavior tests: 16 passed
Gate 4.4 architecture/docs tests: 3 passed
Gate 4.3 reducer regression subset: 8 passed
```

当前环境没有完整仓库和 Windows 音频设备，因此不声称执行了目标工作树完整累计 pytest 或 4.4 Real stop。

## 目标工作树验收

```powershell
python tools/verify_gate4_4_cumulative.py
python tools/verify_gate4_4_real_stop_during_playback.py
```

也可显式执行：

```powershell
python -m compileall -q apps tools tests
python -m black --check apps tools tests
python -m ruff check apps tools tests
python -m pytest -W error tests
python -m pytest -W error tests/gate4_0 tests/gate4_1 tests/gate4_2 tests/gate4_3 tests/gate4_4 -q
python tools/verify_gate4_2_fake_playback.py
python tools/verify_gate4_3_fake_two_turn.py
```

4.4 Real runner 应返回 `real_gate_complete`，并证明 natural summary 未创建、auto-next request 未增加、所有音频资源和 assistant task 归零。

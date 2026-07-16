# Gate 4.3 精简实施报告

## 基线与已知输入

- 远程基线：`e66c30b550bd7959fb916431033053f3bac244ac`（real playback）。
- 用户侧 Gate 4.2：330 项累计测试、58 项 Gate 4 定向测试全绿。
- 真实播放：628 个 packet，decoded/played 均为 602,880 sample frames，物理 drain 成功，人工听感确认通过，无残留 assistant task。

## 本次范围

- 新增 `TwoTurnConversationStateMachine`：actual PlaybackEnded 唯一续轮。
- 新增 `TwoTurnController`：auto-next effect 按 event 顺序同步准入，有界 key ledger 防重复。
- 自动分配下一轮 turn token、capture generation、turn index，并保持同一 streaming generation/session。
- stop、mode switch、disconnect、disable、shutdown、失败、取消、陈旧 generation 不续轮。
- 下一轮 capture start failure 复用现有 `AudioCaptureFailed` 回收。
- 新增 Fake 两轮 runner、Windows Real 两轮 runner 和 Gate 4.3 测试。
- 将 Gate 4.2 Real runner 固定使用 4.2 reducer，避免 4.3 顶层 alias 让历史一轮验收意外自动续轮。

## 当前环境实际执行

```text
Gate 4.0～4.3 最小隔离回归：60 passed
Gate 4.3 定向回归：12 passed
Fake two-turn runner：fake_gate_complete
playback_started_count=2
playback_ended_count=2
auto_next_turn_request_count=2
capture_generations=[2, 3]
turn_tokens=[2, 3]
capture_playback_overlap_count=0
```

当前环境无法 clone GitHub 完整工作树，也没有 Windows 输入/输出设备，因此未执行完整累计回归和真实两轮 runner。

## 覆盖后验收

在 `pc-app-build` 执行：

```powershell
python -m compileall -q apps tools tests
python -m black --check apps tools tests
python -m ruff check apps tools tests
python -m pytest -W error tests
python -m pytest -W error tests/gate4_0 tests/gate4_1 tests/gate4_2 tests/gate4_3 -q
python tools/verify_gate4_3_fake_two_turn.py
python tools/verify_gate4_3_real_two_turn.py
```

真实 runner 操作：第一轮说话并听完回复；应用自动开启第二轮后说第二句；听完第二轮后保持安静，runner 会在自动第三轮刚启动时立即手动结束 session，并要求确认两轮听感。

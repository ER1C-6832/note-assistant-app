# Gate 4.3 验收日志修复报告

基线：`077bbdcdbdb8855fa3f31ea429c9a33738b6a121` (`auto next turn`)

## 问题与修复

1. **disable 后迟到的 actual `PlaybackEnded` 破坏状态 invariant**
   - 原因：`TwoTurnConversationStateMachine._playback_ended()` 先调用 Gate 4.2 的完成投影；该投影会把 phase 设为 `CONNECTED`，与 `enabled=false` 冲突。
   - 修复：当助手已 disabled、连接已失效或 phase 已为 `DISABLED` 时，迟到的物理 drain callback 直接 no-op，不再进入 Gate 4.2 cleanup，也不会产生自动续轮。

2. **Fake 两轮 runner 构造非法 active/completed token**
   - 原因：runner 同时把当前 active turn 和 `last_completed_*_turn_token` 设为同一 token，违反“active streaming turn 必须新于 completed turn”的冻结 invariant。
   - 修复：初始 turn 1 保持 completed token 为 0；模拟 turn 2 capture/submit 时保留 turn 1 为 completed，不再提前把 turn 2 标记 completed。

真实两轮 runner 已返回 `real_gate_complete`，因此本次不修改真实 transport、真实 playback、真实 runner 或 auto-next 主链。

## 本地检查

```text
compileall: passed
Black check: passed
Ruff check: passed
```

当前容器没有完整仓库工作树，未执行累计 pytest 和完整 Fake runner；请在 Windows 覆盖后执行：

```powershell
python -m compileall -q apps tools tests
python -m black --check apps tools tests
python -m ruff check apps tools tests
python -m pytest -W error tests
python -m pytest -W error tests/gate4_0 tests/gate4_1 tests/gate4_2 tests/gate4_3 -q
python tools/verify_gate4_3_fake_two_turn.py
python tools/verify_gate4_3_real_two_turn.py
```

预期：累计测试无失败；Fake runner 返回 `fake_gate_complete`；真实 runner 继续返回 `real_gate_complete`。

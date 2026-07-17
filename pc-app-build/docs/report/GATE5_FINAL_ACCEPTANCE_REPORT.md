# Gate 5 Final Acceptance Report

状态：Pending Real Evidence

## Frozen surface

```text
Tool count: 31
Name-set SHA-256: 58840e01b41f8f3cf08a406428bab9261d07a664be7212d3d650e5016da22693
Unsupported Android-only tools advertised: 0
Runtime: single process
```

## Automated evidence

待填写 Windows 输出：

```powershell
python -m pytest -W error tests
python tools/verify_gate5_4_freeze.py
python tools/verify_gate5_4_cumulative.py
```

## Real evidence

待填写用户自由自然语言验收：

```powershell
python tools/verify_gate5_4_real_manual.py --confirm-effects
```

必须记录：

- 31-tool checklist 的 observed status；
- create/read/search/update/tag/UI 的真实数据库或界面效果；
- delete -> reject 零写入；
- delete -> confirm 软删除；
- trash/list_deleted/restore；
- duplicate request id、same id/different payload；
- disconnect/reconnect 和 shutdown terminal matrix；
- 不含正文、原始 arguments、token 或完整 identity 的脱敏 JSON 摘要。

## Sign-off

当前不得填写 Accepted。只有 Windows 自动测试和真实用户语言证据均通过后，才能把状态改为 `Accepted`。

## 推荐执行顺序

```powershell
python -m pytest -W error tests
python tools/verify_gate5_4_freeze.py
python tools/verify_gate5_4_cumulative.py
python tools/verify_gate5_4_real_manual.py --list
python tools/verify_gate5_4_real_manual.py --confirm-effects
```

包含 Gate 4 Real stop 与 Gate 5 Real protocol/manual 的累计命令：

```powershell
python tools/verify_gate5_4_cumulative.py --include-gate4-real --include-gate5-real-manual
```

该累计命令对手工验收子进程使用直通控制台，用户能够看到并回答每一步提示；它不会自动向助手发送参考命令。

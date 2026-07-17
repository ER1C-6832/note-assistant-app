# Gate 5 Final Acceptance Report

状态：Pending Gate 5.4.1 Retest

## Frozen surface

```text
Tool count: 32
Name-set SHA-256: 543129cc3d6c8fae161ddb716f6cdbf803920ba8fa674d6c5cf6571a198a10e9
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

- 32-tool checklist 的 observed status；
- create/read/search/update/tag/UI 的真实数据库或界面效果；
- delete -> reject 零写入；
- delete -> confirm 软删除；
- trash/list_deleted/restore；
- duplicate request id、same id/different payload；
- disconnect/reconnect 和 shutdown terminal matrix；
- 不含正文、原始 arguments、token 或完整 identity 的脱敏 JSON 摘要。

## Sign-off

Windows 自动部分已由用户报告全部通过；真实语言验收除数字标题解析和待办 UI 导航外基本通过。修复后仍需重测这两项及新的 32-tool hash，之后才能填写 `Accepted`。

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

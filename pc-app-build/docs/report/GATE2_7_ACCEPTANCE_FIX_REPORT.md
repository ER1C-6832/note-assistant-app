# Gate 2.7 acceptance fix report

修复基线：`1f0ea9ff38e0204f62bc2e418b1b9cd04236de12`

## 修复内容

### Gate 2.6 历史 UI smoke 契约

Gate 2.6 架构测试不再要求根目录永久保留 `RUN_GATE2_6_UI_SMOKE.ps1`。历史 Gate 的稳定验收资产是：

```text
pc-app-build/tools/verify_gate2_6_ui_smoke.py
```

当前 Gate verifier 继续执行该工具即可。这样 Gate 2.7 替换根目录 runner 后，不会导致已完成的 Gate 2.6 回归失败。

### Gate 2.7 真实文本长度

真实服务端会截断超过十个字符的文本输入。Gate 2.7 Real acceptance 现在：

- 默认发送 `回复验收通过`；
- 默认文本不超过十个字符；
- `NOTE_ASSISTANT_GATE2_7_TEXT` 自定义值在发送前本地截取到十个字符；
- 验收输出增加 `prompt_limit_chars=10`；
- 文本回合超时时输出脱敏阶段诊断，而不是无信息返回。

该限制只用于 Gate 2.7 Real acceptance 的确定性测试文本，不新增第二套 Runtime，也不修改产品 UI 的文本输入路径。

## 验收

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE2_7.ps1
powershell -ExecutionPolicy Bypass -File .\RUN_GATE2_7_REAL_ACCEPTANCE.ps1
```

只有两个脚本均返回 `0`，才允许声明 Gate 2 完成。

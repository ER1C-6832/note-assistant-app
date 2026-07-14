# Gate 2.1 验收脚本兼容修复

## 问题

Gate 1.7 架构测试把根目录的 `VERIFY_GATE1_7.ps1` 当作永久固定文件。
进入 Gate 2.1 后，仓库使用当前验收脚本 `VERIFY_GATE2_1.ps1`，旧脚本不再存在，导致全量测试在业务和 Runtime 测试全部通过后仍失败。

## 修复

不恢复过期脚本。Gate 1.7 测试改为：

- 根目录至少存在一个 `VERIFY_GATE*.ps1`；
- 对所有现存 Gate 验收脚本检查 `$LASTEXITCODE`；
- 对所有现存 Gate 验收脚本检查失败分支包含 `exit 1`。

该契约兼容后续 `VERIFY_GATE2_2.ps1`、`VERIFY_GATE2_3.ps1` 等脚本，不再绑定某个已经结束的 Gate 文件名。

## 未修改

- Assistant Runtime；
- QML；
- Bootstrap；
- Gate 1 便签业务；
- `VERIFY_GATE2_1.ps1` 本身。

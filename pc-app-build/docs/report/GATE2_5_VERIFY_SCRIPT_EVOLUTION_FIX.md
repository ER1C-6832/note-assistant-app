# Gate 2.5 verifier script evolution fix

修复历史 Gate 架构测试固定读取已被新 Gate 脚本替换的根目录脚本问题。

变更范围：

- Gate 2.3、2.4、2.5 架构测试改为查找当前 `VERIFY_GATE*.ps1`；
- 当前 verifier 必须继续覆盖对应历史测试目录并保持 fail-fast；
- 历史 Real Gate 改为检查仓库内持久化的 Python 验收工具；
- 根目录只要求存在当前 `RUN_GATE2_*_REAL_*.ps1`，不再固定依赖旧 Gate runner 文件名；
- 不修改 Runtime、Recovery、WebSocket、Text Turn 或真实连接逻辑。

基线提交：`9e7e9cbc83063a8fc9c55abde98bf57f5f641545`。

# Gate 3 Spec Package 使用说明

## 覆盖路径

把 ZIP 解压到仓库根目录，保持 `pc-app-build/docs/...` 路径。

本包只新增文档，不修改运行时代码，也不删除 Gate 2 资产。

## 基线

```text
872d5be8b44f679a0531b081c61ac3d7b0921255
```

## 建议提交

```text
docs: freeze Gate 3 floating assistant and streaming voice architecture
```

## 进入 Gate 3.1 前

确认：

- Gate 2.7 两个 runner 都已返回 0；
- 本包文档已推送；
- 后续实现按 `GATE3_IMPLEMENTATION_PLAN.md` 拆分；
- 先移除 fixed AssistantPanel 布局，再接真实音频；
- 不在 Gate 3.1 顺手实现 MCP/KWS/AEC。

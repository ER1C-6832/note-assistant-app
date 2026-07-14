# Gate 1.7 Black 验收修复

## 原因

上一版最终打包副本没有在打包后重新执行 Black，几处手工换行并不是 Black 的规范输出。此外项目允许 `black>=24.0`，不同 Black 版本对单参数三引号调用存在格式差异。

## 修复

- 使用 Black 实际重写两个 Gate 1.7 测试文件。
- 重构 legacy SQL 建表字符串，避免 Black 24/25/26 之间反复改写。
- 不修改应用功能和 Main.qml。

## 验证

以下版本均显示两个文件 `would be left unchanged`：

- Black 24.10.0
- Black 25.1.0
- Black 26.5.1

同时通过 Ruff 和 compileall。

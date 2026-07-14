# ADR-003：本地数据位置

状态：Accepted for Gate 0

## 决策

运行时数据使用 `%LOCALAPPDATA%\NoteAssistant\`，不默认写入 Git Worktree。

## 原因

Worktree、打包和升级路径稳定；避免数据库误提交；未来安装包无需迁移仓库内相对路径。

## 后果

Gate 1 提供一次旧数据库迁移，迁移前强制备份；测试使用临时目录。

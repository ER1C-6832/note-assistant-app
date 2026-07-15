# 小智便签

小智便签是一款面向 Windows 的本地优先桌面便签应用，内置兼容小智协议的语音助手。应用将便签管理、文字对话、按住说话和连续语音交互整合在统一界面中，助手可以通过 MCP 创建、查找和删除便签。

便签内容默认保存在本机，无网络连接时仍可进行日常管理。设备激活、在线对话和助手工具调用需要连接所配置的小智兼容服务。

## 主要功能

### 本地便签管理

- 创建、编辑、搜索、置顶和分类管理便签
- 使用标签组织内容，并提供待办分类
- 支持多选置顶、取消置顶和移入最近删除
- 支持软删除、恢复和彻底删除
- 搜索标题、正文和标签，连续输入时仅展示最新查询结果
- 手动操作与助手操作共享同一业务规则和数据视图

### 内置语音助手

- 兼容小智设备激活、WebSocket 会话和 MCP 协议
- 支持文字输入、按住说话和连续对话
- 支持 Opus 音频上行、语音回复播放和多轮会话
- 连续对话通过本地 VAD 自动识别说话区间并提交回合
- 可选插话，可在助手播报过程中重新开始讲话
- 网络异常后按有界退避策略自动重连
- 音频设备中断、模式切换和应用退出时有序释放资源
- 可选本地唤醒词，用于免手持进入连续对话

### 全局悬浮交互

- Aurora 助手按钮在应用的所有页面保持单一实例
- 按钮可拖动并记忆位置，窗口尺寸或 DPI 变化后保持可见
- 默认折叠，不占用便签主界面宽度
- 展开后提供会话文本、连接状态、输入框和语音模式设置
- 颜色、运动和状态标签由助手状态机统一驱动
- 诊断信息与普通产品界面分离，敏感标识仅显示脱敏值

### 可确认、可追溯的操作

- 删除等高风险助手操作必须经过用户明确确认
- 未确认的操作不会修改便签数据库
- 重复协议请求不会造成重复写入
- 工具调用使用稳定结果结构，并记录必要的本地审计信息
- 未注册或不可用的工具默认拒绝执行，不影响当前连接

## 架构

应用采用单进程架构。Qt 界面、异步网络、助手状态机、音频管线、MCP 工具和本地数据库由同一个 Python 进程管理，Qt 与 asyncio 通过 qasync 共享事件循环。

```text
QML
  -> Qt ViewModel
      -> Notes Application Services / AssistantController
          -> Domain Interfaces and State Machine
              -> SQLite / WebSocket / Audio / MCP Adapters
```

核心设计约束：

- `bootstrap.py` 是唯一组合根，负责对象创建和应用生命周期
- `AssistantController` 是助手状态的唯一写入者
- 手动界面与 MCP 共用便签命令、查询和持久化边界
- SQLite 操作在单线程 Executor 中串行执行，不阻塞 Qt 主线程
- 网络发送、音频队列和长期任务均有明确所有者与容量上限
- QML 不直接访问数据库、网络或音频设备
- 运行时不依赖 Sidecar、本地 HTTP 控制接口或外部助手进程

## 开始使用

### 环境要求

- Windows
- Python 3.10 或更高版本
- 支持的麦克风和音频输出设备（使用语音功能时）
- 可访问小智兼容服务的网络连接（使用助手时）

### 从源码运行

克隆仓库并安装运行时依赖：

```powershell
git clone https://github.com/ER1C-6832/note-assistant-app.git
cd note-assistant-app\pc-app-build
python -m pip install -e .
```

启动应用：

```powershell
python apps\notes-pyside\main.py
```

开发环境包含测试、格式化和静态检查工具：

```powershell
python -m pip install -e ".[dev]"
```

### 基本使用

1. 在主界面创建便签，使用标签、待办和置顶分类整理内容。
2. 通过顶部搜索框查找标题、正文或标签。
3. 使用“已删除”页面恢复便签或执行彻底删除。
4. 展开 Aurora 助手按钮，按界面提示完成设备激活和授权。
5. 选择按住说话或连续对话模式；首次使用语音功能时允许应用访问麦克风。

按住说话是默认语音模式。连续对话、插话和唤醒词均由用户主动启用，不会因应用启动而自动占用麦克风。

## 数据与隐私

应用数据默认存放在：

```text
%LOCALAPPDATA%\NoteAssistant\
├─ data\       # 便签数据库、标签、助手配置和偏好
├─ logs\       # 本地运行日志
├─ metrics\    # 本地性能指标
└─ backups\    # 数据迁移与升级备份
```

便签内容、标签、助手偏好、设备身份和操作记录保存在本机。配置文件采用版本化结构和原子更新，日志及诊断界面不会输出完整令牌、密钥或设备身份。

本地唤醒词识别和语音活动检测在设备端运行。只有在用户发起在线助手会话时，文字消息、必要的会话上下文和语音音频才会发送至所配置的小智兼容服务，以完成识别、生成回复和工具调用。

| 资源 | 用途 |
| --- | --- |
| 麦克风 | 按住说话、连续对话和本地唤醒词 |
| 音频输出 | 播放助手语音回复 |
| 网络 | 设备激活、在线对话、音频传输和 MCP 消息 |
| 本地存储 | 便签、设置、日志、指标和备份 |

普通便签操作不需要麦克风权限，也不会自动建立助手语音会话。

## MCP 工具

助手通过 MCP 调用本地便签能力。工具执行与手动界面共用 `NoteCommandService`，因此搜索语义、删除规则和界面刷新保持一致。

```text
notes.create
notes.search
notes.delete
```

`notes.delete` 首次调用只生成待确认操作；只有用户明确批准后才会执行软删除。MCP 支持初始化、工具发现和工具调用，并对同一会话中的重复请求进行去重。

## 技术栈

- Python 3.10+
- PySide6 与 QML
- qasync 与 asyncio
- SQLAlchemy 与 SQLite
- Pydantic
- websockets
- PyAudio / PortAudio
- Opus
- 本地 VAD 与 KWS
- pytest、pytest-asyncio 与 pytest-qt

## 项目结构

```text
note-assistant-app/
├─ pc-app-build/
│  ├─ apps/notes-pyside/
│  │  ├─ main.py                 # 桌面应用入口
│  │  └─ app/
│  │     ├─ assistant/           # 状态机、协议、网络、音频与 MCP
│  │     ├─ notes/               # 便签领域、服务与持久化
│  │     ├─ ui/                  # Qt ViewModel 和列表模型
│  │     ├─ qml/                 # 桌面界面
│  │     ├─ bootstrap.py         # 组合根
│  │     └─ lifecycle.py         # 有界关闭与资源释放
│  ├─ tests/                     # 单元、集成、UI 与协议测试
│  ├─ docs/                      # 架构决策、规格和验收文档
│  └─ pyproject.toml             # 依赖与工程配置
└─ README.md
```

## 质量保证

运行完整测试：

```powershell
cd pc-app-build
python -m pytest -q
```

运行静态检查和格式检查：

```powershell
python -m ruff check apps tests
python -m black --check apps tests
```

测试体系覆盖便签命令与查询、数据库迁移、Qt 模型、助手状态转换、激活与身份、协议路由、重连、音频替身、MCP 风险控制、QML 集成和有界关闭。真实语音链路的发布验收使用 Windows 音频设备和目标小智兼容服务完成端到端验证。

## 技术文档

- [Runtime 架构规格](pc-app-build/docs/spec/gate0/PC_RUNTIME_REWRITE_SPEC.md)
- [助手状态契约](pc-app-build/docs/spec/gate0/ASSISTANT_STATE_CONTRACT.md)
- [并发所有权规格](pc-app-build/docs/spec/gate0/CONCURRENCY_OWNERSHIP_SPEC.md)
- [便签应用边界](pc-app-build/docs/adr/ADR-004-notes-application-boundary.md)
- [协议兼容矩阵](pc-app-build/docs/spec/gate2/GATE2_PROTOCOL_COMPATIBILITY.md)
- [音频管线规格](pc-app-build/docs/spec/gate3/GATE3_AUDIO_PIPELINE_SPEC.md)
- [连续对话规格](pc-app-build/docs/spec/gate3/GATE3_STREAMING_CONVERSATION_SPEC.md)
- [悬浮助手界面规格](pc-app-build/docs/spec/gate3/GATE3_UI_SHELL_AND_AURORA_SPEC.md)
- [MCP 便签工具范围](pc-app-build/docs/spec/gate0/MCP_NOTE_TOOL_SCOPE.md)

## 参与贡献

欢迎通过 Issue 报告可复现的问题或提出经过论证的改进建议。Pull Request 应说明用户可感知的变化、架构影响和验证方式，并保持以下约束：

- 行为变化应同步更新对应规格和用户文档
- 高风险助手操作必须保留确认与审计机制
- 不得引入第二套助手状态、便签写入边界或运行时进程
- 新增异步任务、队列或设备资源时必须定义所有权、容量和关闭行为
- 提交前应运行受影响测试以及 Ruff、Black 检查

安全问题或可能涉及用户数据、凭据和远程执行的问题，不应在公开 Issue 中披露完整细节；请通过项目维护者指定的私密渠道报告。

## 许可证

本仓库当前未附带开源许可证，项目元数据标记为 Proprietary。除非版权所有者另行提供书面许可，否则保留所有权利；公开可访问的源代码不自动授予复制、修改、分发或商业使用许可。

## 致谢

语音运行时兼容小智协议，并参考配套的 [xiaozhi-android](https://github.com/ER1C-6832/xiaozhi-android) 与 [小泓便签 Android](https://github.com/ER1C-6832/note-assistant-android) 项目在状态管理、协议和可信工具调用方面的设计经验。

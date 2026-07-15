# Gate 2.6 当前 Assistant UI 审计

基线提交：`872d5be8b44f679a0531b081c61ac3d7b0921255`

## 1. 观察结果

当前 `Main.qml` 的主内容是：

```text
Sidebar
+ pageLoader
+ AssistantPanel
```

`AssistantPanel` 被放在主 `RowLayout` 内，设置了：

```text
preferredWidth = 370
minimumWidth = 330
maximumWidth = 410
fillHeight = true
```

这意味着助手始终参与主界面布局计算。截图中可见：

- 便签列表、详情和助手形成四列；
- 详情区域明显被压缩；
- 窗口宽度不足时，基础便签功能先受到影响；
- 面板不能拖动到空闲区域；
- 即使用户只想查看便签，助手仍永久占据右侧空间；
- Developer 诊断虽可折叠，但整个助手列不能折叠成入口按钮。

## 2. 根因

这不是 Assistant Runtime 问题，而是 Shell 组合问题：

```qml
RowLayout {
    Sidebar { ... }
    Loader { ... }
    AssistantPanel { ... }
}
```

只要 `AssistantPanel` 是 RowLayout 子项，它就一定会改变便签区域尺寸。把面板宽度调小只能缓解，不能解决。

## 3. 产品目标

Gate 3.1 后应变为：

```text
ApplicationWindow
├─ NotesLayout（只包含 Sidebar + PageLoader）
└─ AssistantOverlay（高 z，不参与 Layout）
   ├─ AuroraAssistantButton
   └─ AssistantFloatingPanel（按需展开）
```

基本便签布局在助手展开、折叠、拖动时都不得重新分配宽度。

## 4. 保留内容

现有 `AssistantPanel.qml` 中以下产品能力继续保留：

- 助手启用开关；
- 连接、断开、重试；
- 最近用户/助手文本；
- 文本输入；
- 激活状态；
- Fake/Real 开发切换；
- 脱敏身份、Session、协议诊断；
- 模拟断线/故障入口。

需要改变的是承载方式，不是删除诊断能力。

## 5. 不采用的方案

### 固定窄侧栏

仍会占布局空间，窗口越窄问题越明显。

### 独立顶层窗口

会引入焦点、置顶、多显示器、任务栏和生命周期问题；当前产品只要求应用内全局入口。

### 每个页面各放一个按钮

会重复 UI 状态、位置和生命周期，破坏“一个全局入口”的语义。

### 用系统托盘代替

系统托盘可作为未来补充，但不能替代应用内可见入口和状态反馈。

## 6. Gate 3.1 验收基准

- `Main.qml` 主 `RowLayout` 内不再存在 `AssistantPanel`；
- 助手展开/折叠前后 `pageLoader` 可用宽度不变；
- 按钮和面板可在窗口内拖动或停靠；
- 默认以折叠按钮启动，不遮住主要编辑区域；
- 面板可展开并继续使用现有 Developer 诊断；
- 切换页面时入口不销毁、不重复创建；
- 普通鼠标事件可穿透 Overlay 空白区域，便签仍可点击、选择和编辑。

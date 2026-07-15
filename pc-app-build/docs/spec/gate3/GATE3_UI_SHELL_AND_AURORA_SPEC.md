# Gate 3 全局悬浮 Assistant Shell 与 Aurora UI Spec

## 1. 目标

把 Gate 2.6 固定右侧 `AssistantPanel` 迁移成应用内全局悬浮入口：

- 不占便签主布局宽度；
- 所有页面共享同一实例；
- 可折叠为 Aurora 按钮；
- 展开后保留当前产品面板与 Developer 诊断；
- 可拖动并在窗口尺寸变化后保持可见；
- 后续 PTT、连续对话、TTS 状态直接驱动 Aurora 视觉。

## 2. 结构

推荐 QML 结构：

```text
Main.qml
├─ ColumnLayout / Notes RowLayout
│  ├─ TopBar
│  ├─ Sidebar
│  └─ PageLoader
└─ AssistantOverlay.qml
   ├─ AssistantFloatingPanel.qml
   │  └─ AssistantPanelContent.qml
   └─ AuroraAssistantButton.qml
```

允许第一步复用 `AssistantPanel.qml` 作为内容，但最终应分离：

```text
AssistantPanelContent  = 业务和诊断内容
AssistantFloatingPanel = 阴影、定位、拖动、展开/关闭
AssistantOverlay       = 全局坐标、边界、z-order、持久化
AuroraAssistantButton  = 状态视觉与主要手势
```

## 3. 布局与 z-order

- Overlay 是 `ApplicationWindow` 的直接子项或 `contentItem` 最后一个子项。
- Overlay 填满窗口，但自身没有背景、MouseArea 或 modal 行为。
- 只有按钮、面板、拖动标题栏和明确的交互控件接收指针事件。
- Overlay 空白区域不得阻塞下面的便签页面。
- 助手层高于普通页面，低于删除确认、危险操作确认、菜单和系统级模态对话框。
- 不使用 `RowLayout`/`ColumnLayout` 为悬浮面板分配宽度。

建议层级：

```text
Notes content: z 0
Assistant overlay: z 40
Non-modal assistant panel: z 41
Menus / confirmation popups: z 80+
```

## 4. 初始位置与尺寸

### 折叠按钮

- 默认位于内容区右下角，安全边距 24 px；
- 视觉直径建议 72～80 px；
- Windows 触控/高 DPI 下命中区域不小于 52 px；
- 第一次升级到 Gate 3.1 时默认折叠。

### 展开面板

- 建议宽 360～400 px；
- 高度按内容和窗口可用高度约束，最大不超过窗口高度减 48 px；
- 如果按钮靠右，面板优先向左上展开；靠左时向右上展开；
- 展开后必须整体 clamp 到窗口安全区域；
- 面板展开不改变按钮的持久化锚点。

## 5. 拖动

- 按钮可直接拖动；点击与拖动用位移阈值区分，避免拖动后误触发主操作。
- 面板只允许从标题栏拖动，文本输入、滚动和按钮区域不启动拖动。
- 使用 `DragHandler` / Pointer Handlers，避免一个覆盖全窗口的 `MouseArea`。
- 坐标以窗口 contentItem 为参照，不使用屏幕绝对坐标。
- 拖动结束后保存归一化锚点：

```text
x_ratio = x / max(1, available_width - launcher_width)
y_ratio = y / max(1, available_height - launcher_height)
```

- 窗口 resize、DPI 变化或屏幕迁移后，根据 ratio 恢复并再次 clamp。
- 至少保留整个按钮可见；面板关闭按钮和拖动标题栏必须可见。
- Gate 3.1 不要求跨应用桌面悬浮，也不要求吸附到操作系统屏幕边缘。

## 6. 展开状态

- App 每次启动默认折叠，避免永久遮挡便签。
- 展开状态是 UI 临时状态，不写入 AssistantState。
- Developer 诊断展开状态也不写入 AssistantState，默认收起。
- 切换便签页面不自动关闭面板；进入删除确认等模态流程时可暂时降低非必要交互，但不能销毁 Runtime。
- Esc 只关闭展开面板，不关闭助手、不断开连接。

## 7. 主按钮手势

### 未具备音频能力时（Gate 3.1 初始）

- 单击：展开/收起面板；
- 连接、激活等操作继续由展开面板完成；
- 不显示可用但未实现的录音手势。

### `hold_to_talk`

- 短按：展开/收起；
- 长按达到阈值后：请求 PTT start；
- 松开：请求 PTT stop；
- 若未连接，长按不能乐观显示 Listening，Controller 先完成必要连接或返回可见错误。

### `streaming_conversation`

- 单击主操作：开始连续会话；
- 连续会话活动时再次单击：停止会话；
- 活跃连续会话期间忽略 PTT 长按；
- 面板展开动作可放到辅助点击区域或右键/小箭头，具体交互在 Gate 3.1 UI smoke 中确认，但不得让开始/停止和展开产生双重命令。

第一版允许使用“双层命中区”：中央主操作 + 外围/附属展开按钮，以避免手势冲突。

## 8. Aurora 视觉

Android 设计语言在 PC 上采用本地 QML Canvas 实现，不拷贝 Compose 代码。

### 绘制

- 2～3 个带羽化的径向渐变 blob；
- blob 以小幅不同相位轨迹移动；
- 状态切换时对 alpha、scale、speed 和颜色做 500～700 ms 平滑插值；
- 中心保留半透明深色圆和简短状态标签；
- 不依赖图片资源，不引入 WebView 或视频动画。

### 状态映射

| Assistant State | 主色 | 运动 |
|---|---|---|
| disabled / disconnected | slate + muted blue | 低 alpha、极慢漂移 |
| activation required | amber + lilac | 缓慢脉冲 |
| activating / connecting / reconnecting | blue + amber | 中速旋转/汇聚 |
| connected / online | blue + lilac | 缓慢稳定漂移 |
| listening / recording | peach + blue | 呼吸放大、速度提高 |
| user speaking | peach + blue + lilac | 更强呼吸，保持稳定不闪烁 |
| thinking / uploading | blue + lilac | 反向轨道 |
| speaking / playing | peach + lilac + amber | 柔和三团流动 |
| recovering | blue + slate + amber | 收缩后恢复 |
| error / audio error | rose + slate | 低频警示脉冲，不做快速闪烁 |

### 视觉数据来源

`AssistantViewModel` 提供只读投影：

```text
auroraVisualState
auroraColorA / B / C
auroraScale
auroraSpeed
auroraAlpha
auroraBorderColor
compactStatusLabel
```

QML 不自行组合 `phase`、`audio`、`streaming_state` 来重建第二套业务状态。允许颜色常量留在 UI 层，但“选择哪个视觉目标”必须由单一映射函数产生并有单元测试。

## 9. 性能与生命周期

- 动画只在窗口可见且未最小化时更新；
- disabled/idle 状态降低刷新频率或运动速度；
- 不在每帧创建大对象、格式化日志或访问 Python；
- Python State 更新只触发目标参数变化，不按帧调用 Python Slot；
- 关闭窗口时 Overlay 不拥有独立长期 asyncio Task；
- QML Canvas 销毁不得影响 AssistantController shutdown。

## 10. Developer 诊断

现有诊断保留在展开面板内，默认折叠：

- Real/Fake；
- identity / session 脱敏值；
- activation；
- reconnect；
- protocol trace；
- 模拟断线/故障。

产品收口时可把 Developer 区隐藏到开发开关，但 Gate 3 不删除它，也不另建第二个调试窗口。

## 11. 禁止项

- 固定占用主 RowLayout 的右侧助手栏；
- QML 拖动直接修改 AssistantState；
- 独立 Python/Qt 窗口承载 Runtime；
- Overlay 空白区域吞掉所有鼠标事件；
- 状态颜色由按钮点击乐观切换；
- 每个页面创建独立 AssistantPanel；
- 为 Aurora 引入第二个动画事件循环。

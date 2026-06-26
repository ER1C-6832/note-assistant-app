# Phase 9.1 备用演示路径

## 什么时候使用

当以下任一情况出现时，切换到 Mock 模式：

- 麦克风不可用。
- py-xiaozhi 启动失败。
- ASR / TTS / LLM 不稳定。
- 现场网络影响语音链路。
- 时间紧张，需要优先展示产品 UI 流程。

## 操作

1. 关闭真实 Sidecar 窗口。
2. 运行：

```bat
cd /d C:\yuyinzhushou\note-assistant-app\pc-app-build
scripts\start_demo_mock_mode.bat
```

3. 打开 App 后点击右下角语音按钮。
4. 每次点击会轮流演示：
   - 结果卡片
   - 多候选确认
   - 删除二次确认
   - 失败提示

## 讲解口径

“为了避免现场音频设备和网络影响演示，这里切换到 Mock 语音桥接。它不替代真实语音能力，只用于稳定展示语音交互产品化流程。”

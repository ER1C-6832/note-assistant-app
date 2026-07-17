# Gate 6 Specification Index

状态：Frozen for implementation  
目标分支：`rewrite/single-process-runtime`  
制定基线：`note-assistant-app@2bd25c3677cf2aecd2784d089e8f971c40bb377e`  
前置事实：Gate 5 32-tool Windows Automated/Fake/Real 已由用户验收通过。

## 1. Gate 6 目标

Gate 6 在现有单进程 Runtime 内完成跨平台音频设备底座、离线 KWS、AEC/NS 处理和声学 barge-in，使 Windows 当前产品能够可靠使用，并保持未来 macOS 真实落地能力。

Gate 6 不重写 Gate 2～5 已验证的 WebSocket、Controller、状态机、播放、连续对话或 MCP 工具链。

## 2. 固定子阶段

```text
6.0  Cross-platform probe and contract freeze
6.1  Device registry, route handling and duplex audio foundation
6.2  Offline KWS and microphone-owner handoff
6.3  AEC/NS processing; AGC probe only and default-off
6.4  Acoustic barge-in, settings completion and cumulative closeout
```

依赖顺序不可颠倒：

```text
6.0 -> 6.1 -> 6.2 -> 6.3 -> 6.4
                  \------------^  KWS 与 barge-in 只在最终累计验收汇合
```

KWS 不依赖 AEC，但依赖 6.1 的长期麦克风所有权和设备恢复；声学 barge-in 必须依赖 6.3 的有效 processed path。

## 3. 权威文档

| 文件 | 用途 |
|---|---|
| `GATE6_AUDIO_DEVICE_KWS_AEC_BARGE_IN_SPEC.md` | 产品行为、架构、状态、Ports、失败和跨平台总契约 |
| `GATE6_ANDROID_REFERENCE_AUDIT.md` | Android 已验证事实、可复用原则与 PC 不可照搬项 |
| `GATE6_IMPLEMENTATION_PLAN.md` | 6.0～6.4 的实施顺序、交付物与退出条件 |
| `GATE6_TEST_AND_ACCEPTANCE_PLAN.md` | Automated/Fake/Real、设备、异常和资源终态矩阵 |
| `GATE6_SPEC_MANIFEST.json` | 冻结文件集合和关键决策机器可读摘要 |
| `../../adr/ADR-010-gate6-cross-platform-audio-session.md` | 不可逆架构决策 |

冲突优先级：

1. 当前平台真实 probe 和 Real runner 证据；
2. 本目录主 Spec；
3. Accepted ADR；
4. Test and Acceptance Plan；
5. Implementation Plan；
6. Implementation/Delivery Report；
7. Android 参数和历史 Gate 文档。

## 4. 当前冻结默认值

```text
AEC                automatic
NS                 automatic / conservative
AGC                disabled
KWS                disabled until user opt-in
Acoustic barge-in  disabled until user opt-in and processed path ready
Input device       system default unless user pins a device
Output device      system default unless user pins a device
Raw PCM dump       disabled
Second process     forbidden
```

## 5. 签字等级

- `Accepted-Windows`：Windows Automated/Fake/Real、设备矩阵和 6.4 累计验收通过；
- `Accepted-CrossPlatform`：在前项基础上，真实 macOS capture/playback/KWS/AEC/barge-in/terminal matrix 通过。

没有真实 Mac 证据时不得写“macOS 已通过”，但 Windows 实施可以继续推进。

## 6. 完成定义

Gate 6 只有满足以下条件才可按对应等级签字：

- 设备选择、默认回退和 route generation 可观测；
- KWS、assistant capture、barge-in monitor 不并发抢占麦克风；
- KWS 不参与播放期插话；
- speaker-route barge-in 只使用 AEC/NS 后 PCM；
- raw microphone fallback 不会静默激活声学 barge-in；
- AGC 关闭不阻塞 Gate 完成；
- barge-in 取消不伪造 natural `PlaybackEnded`；
- 迟到旧 TTS/PCM/event 不污染新回合；
- system interruption、hotplug、disable、shutdown 后资源全零；
- Gate 1 through Gate 6 累计回归通过；
- 单进程、单 event loop、单 sender、单 Controller state writer 保持。


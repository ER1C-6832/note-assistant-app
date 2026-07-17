# PC Assistant Runtime Master Plan — Gate 6 Amendment

状态：Accepted and merged into Master Plan  
适用基线：`2bd25c3677cf2aecd2784d089e8f971c40bb377e`

## 修改结论

1. Gate 5 更新为完成：32 个工具 Windows Automated/Fake/Real 验收通过。
2. 原 Gate 6.5 KWS 合并进 Gate 6，不再作为独立总 Gate。
3. Gate 6 固定为 6.0～6.4 五个阶段。
4. 顺序冻结为设备/双工 -> KWS -> AEC/NS -> acoustic barge-in。
5. AGC 只做 capability probe，首版 default-off，且不是 Gate 完成依赖。
6. 引入小型“语音与设备”面板，不扩建完整设置中心。
7. AEC concrete backend 由 6.0 Windows/macOS probe 决定，Spec 不提前假定。
8. Windows 与 macOS 使用分级签字，禁止无真机证据的跨平台完成声明。

## Superseded 范围

以下历史表述在当前规划中失效：

- “Gate 5 未开始”；
- “Gate 6 仅 1～2 日”；
- 独立 `Gate 6.5 KWS`；
- “AEC/NS/AGC”作为一个不区分目的的并列增强项；
- 以 Android threshold 直接作为 PC 参数。

历史报告仍保留当时语境，不要求机械改写。当前状态和后续实施以 Master Plan 与 `docs/spec/gate6/` 为准。

## 不改变的契约

- 单进程、单 qasync event loop、单 Controller state writer；
- 单 WebSocket sender；
- natural `PlaybackEnded` 唯一正常自动续轮源；
- stop/disconnect/disable/shutdown 优先；
- Gate 5 32-tool 工具面保持冻结；
- 原始 PCM/Opus 不进入 AssistantState、QML 或普通日志。


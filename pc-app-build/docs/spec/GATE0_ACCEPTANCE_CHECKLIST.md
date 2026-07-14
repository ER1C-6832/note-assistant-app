# Gate 0 Acceptance Checklist

## A. 基线

- [ ] 不包含 Sidecar、外部 py-xiaozhi Runtime、Notes API。
- [ ] 旧架构只存在于 Git 历史和 Tag。
- [ ] 不通过兼容层恢复旧 Runtime。

## B. 架构

- [ ] 单 Python 进程被接受。
- [ ] Qt + qasync 单事件循环被接受。
- [ ] Assistant Core 和 Notes Domain 不依赖 PySide6。
- [ ] QML 只通过 ViewModel 操作业务。
- [ ] Bootstrap 是唯一 Composition Root。
- [ ] 不使用 localhost HTTP 作为本地业务路径。

## C. 并发

- [ ] State 只有 Controller 单写者。
- [ ] 音频 callback 只搬运帧。
- [ ] 队列容量和溢出策略已冻结。
- [ ] DB 使用单线程 Executor。
- [ ] WebSocket 发送只有一个所有者。
- [ ] Generation token 规则已冻结。
- [ ] Shutdown 有有界超时。

## D. 协议与音频

- [ ] Hello JSON 与 Android 一致。
- [ ] 服务端 hello 必须包含 session_id。
- [ ] 上行 16kHz/mono/PCM16/20ms、Opus 24kbps 已冻结。
- [ ] 下行采样率属于平台适配层。
- [ ] PTT 优先，连续对话后置，KWS 不做。

## E. MCP

- [ ] initialize/tools/list/tools/call 已冻结。
- [ ] 未注册工具 fail-closed。
- [ ] MVP 只有 create/search/delete。
- [ ] delete 必须确认。
- [ ] request_id 去重。
- [ ] UI 和语音共享 NoteCommandService。

## F. 性能

- [ ] 使用 perf_counter_ns。
- [ ] 冷启动、PTT、TTS、MCP 事件命名已冻结。
- [ ] p50/p95/max 统计规则已冻结。
- [ ] 新 PC 不允许控制轮询、本地 HTTP 和外部 Runtime 进程。

## G. Gate 0 输出

- [ ] 所有 Spec 已 Review。
- [ ] ADR 已接受。
- [ ] 不存在互相矛盾的决策。
- [ ] Mentor 已确认快速验证范围。
- [ ] 可以进入 Gate 1：恢复单进程手动便签。

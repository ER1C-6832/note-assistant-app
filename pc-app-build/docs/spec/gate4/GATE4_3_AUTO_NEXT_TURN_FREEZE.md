# Gate 4.3 Actual PlaybackEnded Auto Next Turn Freeze

状态：Accepted；由 GATE4_FINAL_FREEZE.md 纳入 Gate 4 最终冻结
实现基线：`077bbdcdbdb8855fa3f31ea429c9a33738b6a121`；日志修复：`9f37041cc5a955d0f943e552a465a8e9b02046a0`

## 唯一续轮规则

只有当前 generation/token 对应的自然物理 `ActualPlaybackEnded` 可以分配下一轮。Transcript、`tts/stop`、input terminal、decoder flush、queue empty、timer、失败和取消都不能续轮。

合法事件一次性分配：

```text
streaming_turn_index + 1
voice turn_token + 1
capture_generation + 1
-> StreamingConversationState.STARTING
-> exactly one StartStreamingConversation effect
```

## 排列语义

事件泵顺序决定结果，不由 effect task 调度决定：

- `PlaybackEnded -> stop/disconnect/mode switch`：先启动一次已合法分配的新 capture，随后立即按后一事件取消；
- `stop/disconnect/mode switch -> PlaybackEnded`：不分配新 capture；
- duplicate/stale `PlaybackEnded`：no-op；
- playback failure/cancel/non-natural end：no-op；
- next capture start failure：进入现有可恢复音频错误和 session 回收路径。

自动 next-turn effect 在 event pump 中顺序准入；仅该 effect 使用同步准入，其他既有 effect 调度方式不变。Controller 使用有界 `(streaming_generation, capture_generation, turn_token)` ledger 作为第二层 exactly-once 防线。

## 非目标

- 不在播放期间默认开麦；
- 不实现 acoustic/full-duplex barge-in 或 AEC；
- 不改变真实 Opus/PyAV/PyAudio 热路径；
- 不把 payload 放入 Runtime event queue；
- 不增加进程、event loop 或本地桥接。

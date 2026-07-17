# Gate 6.0 Probe Report

状态：Template — 未执行前不得填写 Passed  
Commit：`<exact commit>`  
平台：`Windows | macOS`  
OS/build：`<public version>`

## 1. Execution summary

```text
Automated/Fake: not_run
Device inventory: not_run
Duplex probe: not_run
AEC far-end-only: not_run
AEC double-talk: not_run
KWS probe: not_run
Package smoke: not_run
Terminal zero: not_run
```

## 2. Public device route

```text
input_public_name:
output_public_name:
input_host_api:
output_host_api:
capture_format:
render_format:
duplex_supported:
reported_input_latency_ms:
reported_output_latency_ms:
```

不得填写完整 endpoint GUID/UID。

## 3. Backend candidates

| Backend | Create/import | Current route | Far-end-only | Double-talk | Package | Decision |
|---|---|---|---|---|---|---|
| WebRTC APM | not_run | not_run | not_run | not_run | not_run | pending |
| Windows system/endpoint AEC | n/a/not_run | n/a/not_run | n/a/not_run | n/a/not_run | n/a/not_run | pending |
| macOS voice processing | n/a/not_run | n/a/not_run | n/a/not_run | n/a/not_run | n/a/not_run | pending |

## 4. AEC/NS/AGC effective configuration

```text
selected_backend:
aec_available:
aec_effective:
ns_available:
ns_effective:
agc_available:
agc_effective: false
internal_block_ms:
delay_strategy:
drift_strategy:
```

## 5. Far-end-only evidence

用户保持安静，只播放测试 TTS。记录：

```text
render_frames:
capture_frames:
processed_frames:
queue_overflow:
raw_level_summary:
processed_level_summary:
processed_vad_trigger_count:
product_uplink_frames: 0
human_observation:
```

不保存或粘贴 PCM。

## 6. Double-talk evidence

播放 TTS 期间用户说固定短句。记录：

```text
processed_near_speech_seen:
first_processed_speech_sample_ms:
raw_level_summary:
processed_level_summary:
human_observation:
```

本阶段不发送产品 abort，不执行正式 barge-in。

## 7. KWS candidate

```text
engine:
model_public_name:
model_size_bytes:
load_success:
live_microphone_hit:
duplicate_cooldown_verified:
cpu_sample:
rss_sample:
shutdown_success:
```

单次样本不宣称 FAR/FRR。

## 8. Resource terminal

```text
capture_stream: 0
output_stream: 0
duplex_session: 0
render_queue_items: 0
capture_queue_items: 0
processing_worker: 0
kws_worker: 0
microphone_lease: none
pending_tasks: []
second_python_process: 0
```

## 9. Decision

```text
Windows default backend:
macOS target backend:
fallback policy:
initial PC barge-in VAD profile:
queue/watchdog budgets:
packaging dependencies:
known unsupported routes:
```

若 macOS 未在真实设备执行，必须写：

```text
macOS status: Pending macOS Real Evidence
```

## 10. Gate 6.1 authorization

只有 backend strategy、Ports、numerical budgets、Windows evidence 和 terminal zero 已冻结后，才填写：

```text
Gate 6.1 may start: yes
```


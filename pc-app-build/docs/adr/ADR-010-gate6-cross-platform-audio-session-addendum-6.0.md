# ADR-010 Addendum: Gate 6.0 Probe Implementation

状态：Accepted-Windows — superseded for product routing by the Gate 6.1 addendum
基线：`19953b12d15ad5e76dfd4da0ca3dfa9aa353dec8`

## Decision implemented in 6.0

1. Core-facing contracts are frozen in a framework-neutral module and preserve separate responsibilities for device registry, route observation, duplex I/O, processing and KWS.
2. Gate 6.0 real probes are explicit CLI actions. Importing the application or probe modules does not open a device, load a model or change the Gate 3/4 product path.
3. Probe queues fail visibly on overflow. They do not silently drop old render/capture frames and then claim valid AEC evidence.
4. Probe output is bounded and privacy-filtered. Raw audio and complete endpoint identity are prohibited.
5. AGC remains disabled in every candidate adapter invocation.
6. The first optional AEC adapter target is the WebRTC-based `aec-audio-processing` Python wheel, but it is not selected as the product backend until Windows far-end-only, double-talk, packaging and lifecycle results pass.
7. The first KWS candidate remains sherpa-onnx. Models are user-supplied local files; no runtime download is allowed.

## Numerical candidates pending Windows evidence

```text
internal_block_ms        10
public_frame_ms          20
render_queue_capacity    64
capture_queue_capacity   64
probe_watchdog_ms        2000
kws_cooldown_ms          1500
```

## Decisions after Windows evidence

```text
Windows AEC candidate       aec-audio-processing/WebRTC APM
Windows provisional mode    AEC on, NS off, AGC off
internal DSP block          10 ms
delay                       route-reported auto (120 ms on tested route)
KWS candidate               sherpa-onnx with existing local zipformer model
macOS target backend        pending real Mac
production barge-in profile deferred to Gate 6.3 evidence
```

## Consequence

The corrected Windows AEC-only and KWS probes authorize Gate 6.1. No formal AEC, KWS or acoustic barge-in capability becomes active in the product from this addendum; product routing decisions continue in the Gate 6.1 addendum.

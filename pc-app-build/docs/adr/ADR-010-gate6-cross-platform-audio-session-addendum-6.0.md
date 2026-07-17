# ADR-010 Addendum: Gate 6.0 Probe Implementation

状态：Provisional — Real evidence required  
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

## Still undecided

```text
Windows default AEC backend
macOS target backend
backend fallback order
production queue/watchdog budgets
supported production route/format matrix
delay and drift estimator
KWS model package and wake phrase
initial PC barge-in VAD profile
```

## Consequence

Gate 6.0 implementation may be merged and used to collect evidence, but Gate 6.1 authorization remains `no` until the Windows report freezes the undecided items. No formal AEC, KWS or acoustic barge-in capability is active in the product.

# ADR-010 Addendum: Gate 6.2 Offline KWS Ownership

状态：Implemented; Windows Real acceptance pending  
实施基线：`d02b928ef4e71b6ab8019423f1f8fdcd3064e3e6`

## Decision

1. Offline KWS is a product service beside `AudioSessionSupervisor`, not a second assistant runtime or process.
2. sherpa-onnx is the selected Windows adapter; its imports are lazy and its dependency remains in the `kws` optional dependency set.
3. The model registry resolves one versioned local model layout. No product path downloads models at runtime.
4. KWS owns one bounded 20 ms PCM queue and one daemon worker only while the assistant is eligible and idle.
5. `WAKEWORD_KWS -> ASSISTANT_CAPTURE` is an owner/generation/route-generation transfer. The subsequent controller acquire is idempotent only for the exact transferred tuple.
6. Manual voice start may synchronously ask KWS to yield before acquiring the lease. The yield callback runs outside the lease lock.
7. Playback, thinking, speaking, capture, barge-in monitoring, interrupted routes, disabled state and shutdown all pause KWS.
8. Cooldown and debounce reject duplicate hits. Reconciliation is coalesced so terminal notifications resume KWS exactly once.
9. Model/backend errors affect only offline wake. The existing button and PTT paths remain available.
10. Settings expose enablement, wake phrase and public model/status summaries; private model paths are not sent to QML.

## Consequences

- Long-lived idle microphone use is explicit, default-off and represented by `WAKEWORD_KWS`.
- No idle PCM enters Opus or transport uplink code.
- KWS cannot be reused as the Gate 6.4 playback interruption detector.
- Gate 6.3 may insert processed capture behind the frozen KWS/runtime ports without changing ownership semantics.
- macOS remains deferred; this implementation claims Windows readiness only after the supplied Real acceptance succeeds.

# Gate 6.2 Offline KWS and Owner Handoff Freeze

状态：Implemented; Windows acceptance correction delivered; corrected rerun pending  
实施基线：`d02b928ef4e71b6ab8019423f1f8fdcd3064e3e6`

## Product boundary

- Offline KWS is device-local and default-off.
- The selected adapter is sherpa-onnx behind `KeywordSpotterPort`.
- Models are installed below the application data root; the runtime never downloads a model.
- Idle PCM is consumed only by the bounded KWS queue. It is not encoded, uploaded or persisted.
- KWS is an idle entry source, never a playback-period interruption detector.

## Eligibility

KWS may own the microphone only when all facts below are true:

- preference enabled;
- assistant enabled and connected;
- continuous-conversation mode selected;
- phase `connected`, no active text/voice/streaming turn;
- capture and playback inactive;
- route ready and permission available;
- microphone owner `none` or the current KWS generation.

Every other state pauses KWS. Route generation change stops the old stream before a new generation may start.

## Assistant startup policy

- the assistant controller is enabled during every application startup;
- connection is attempted automatically by default after identity initialization;
- existing preference files without the new key inherit auto-connect enabled;
- settings may disable future automatic connection attempts, but do not disable the assistant service;
- the home panel exposes connection/retry state and no longer exposes an assistant enable switch;
- KWS remains independently opt-in/default-off and still requires an established assistant connection.

## Ownership protocol

1. Idle KWS acquires `(WAKEWORD_KWS, kws_generation, route_generation)`.
2. An accepted hit stops the native stream and worker while retaining the lease.
3. The lease transfers atomically to `(ASSISTANT_CAPTURE, next_capture_generation, route_generation)`.
4. The controller command uses entry source `wakeword`; the normal Gate 3 effect claims the transferred lease idempotently.
5. A simultaneous button/PTT start may ask KWS to yield. Only one assistant capture can claim the lease.
6. Session terminal, route recovery, lease release or failed handoff schedules one coalesced reconciliation; a dirty notification received during reconciliation is retained and duplicate notifications cannot create duplicate KWS streams.

## Failure policy

- missing/incomplete model -> visible model error, no microphone lease;
- native import/model load failure -> visible KWS error, manual voice modes remain usable;
- bounded queue overflow -> drop oldest, increment public counter;
- stale generation/hit -> reject;
- cooldown/debounce duplicate -> count and reject;
- disable/shutdown -> stop worker/stream, empty queue, release lease, never auto-resume.

## Frozen terminal facts

```text
kws worker                  false
kws capture stream          false
kws bounded queue size      0
microphone owner            none
idle uploaded frames        0
pending KWS reconcile task  0
second Python process       0
```

Windows Real acceptance must separately prove model load, a natural single wake hit, background/media negatives, device/default change, post-session resume, and disable-no-resume. Fake evidence cannot authorize Real acceptance.

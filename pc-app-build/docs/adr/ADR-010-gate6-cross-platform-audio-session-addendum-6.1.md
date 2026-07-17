# ADR-010 Addendum: Gate 6.1 Product Audio Session

状态：Implemented-Windows; real route acceptance required after overlay
实施基线：`0be8159de4f6fe2161b7de82d971c5f32266c9b3`

## Decision

1. The desktop product creates exactly one application-scoped `AudioSessionSupervisor`.
2. Existing Gate 3 capture remains the uplink worker, but its capture adapter resolves the supervised input route and rejects callbacks from an old route generation.
3. Existing Gate 4 playback remains the downlink worker, but output planning resolves the supervised output route and projects buffering/playing/draining/cancelling as an independent playback fact.
4. The microphone lease key is owner + lease generation + route generation. Legacy Gate 3 callers receive `ASSISTANT_CAPTURE` and the current route generation by default.
5. Persisted device preference is either follow-system-default or a private device fingerprint. PortAudio indexes are snapshot-local and are never persisted or shown in QML.
6. If a pinned device disappears, the product visibly falls back to the current system default without erasing the pinned preference.
7. A route generation change while capture or playback is active cancels playback and finalizes the active voice capture through existing controller commands. No automatic microphone restart is introduced.
8. Capture, playback, processing and route state remain orthogonal. `AssistantAudioStatus` stays a compatibility projection only.
9. Gate 6.1 adds bounded capture/render-reference buffers and the concrete duplex session boundary, but does not activate AEC, NS, KWS or acoustic barge-in in the product.
10. macOS is retained behind the same contracts and remains deferred until a real Mac is available; Windows completion does not claim cross-platform acceptance.

## Consequences

- Bootstrap no longer creates an independent product capture adapter, microphone lease and default-output planner.
- Device refresh and selection are available from the existing Assistant settings sheet.
- The microphone test is local-only, does not encode/upload/persist PCM and releases its lease on every exit.
- PortAudio polling is the Windows-first route observer for this gate. A native endpoint observer can replace it behind the port without changing controller, QML or stored preferences.
- Gate 6.2 may attach KWS only through an owner-aware lease handoff; it must not introduce a second microphone owner.

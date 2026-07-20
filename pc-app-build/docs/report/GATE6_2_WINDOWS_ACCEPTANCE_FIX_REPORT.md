# Gate 6.2 Windows Acceptance Fix Report

状态：Implemented; focused automated acceptance passed; Windows cumulative and real rerun pending  
基线：Gate 6.2 overlay on `d02b928ef4e71b6ab8019423f1f8fdcd3064e3e6`

## User-observed failures

- Windows cumulative acceptance: 488 tests passed and four Gate 6.2 lifecycle assertions failed while a replacement Fake KWS runtime was still starting.
- Offline wake depended on the assistant already being enabled and connected, but the home page defaulted to an off/disconnected presentation.
- A 15-second isolated real KWS attempt loaded the model but did not detect the phrase.
- A soft-deleted note could still reference a tag while the UI exposed a delete action; after hard-delete, the cached tag usage did not refresh until restart.

## Corrections

1. `MicrophoneLeaseCoordinator` now publishes acquire/release/transfer changes. `OfflineKwsCoordinator` subscribes to those changes and retains a dirty reconciliation request while another reconciliation is active.
2. Windows lifecycle assertions wait for the public `active` fact, then retain strict exactly-once instance/resume assertions.
3. KWS runtime shutdown is a handoff barrier: capture stops, the worker joins and the bounded queue drains before the lease transfers to `ASSISTANT_CAPTURE`.
4. Assistant startup always enables the controller. Auto-connect is default-on, configurable in settings, and inherited by existing preference files. The home enable switch is removed; connect/retry remains.
5. The real KWS runner has a 30-second maximum observation window but exits as soon as one wake hit is accepted.
6. Tag usage is recalculated from active plus soft-deleted notes after queries and mutations. In-use deletion errors are localized, and hard-delete updates the tag affordance without restart.

## Local evidence

```text
Black                              passed (327 files unchanged)
Ruff                               passed
compileall                          passed
Gate 6.2 tests                     17 passed
Gate 6.2 + tag + lease regression  24 passed
Gate 6.2 Fake verifier             passed
QML lint                           no errors (pre-existing warnings only)
full Qt suite                      environment-blocked: libEGL.so.1 absent
```

No Windows result is fabricated. The user must run `VERIFY_GATE6_2.ps1` and the real KWS runner after applying this overlay.

## Required Windows rerun

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_2.ps1
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_2_REAL_KWS.ps1
```

For the product path, restart the app, keep continuous conversation selected, enable offline wake, wait for “正在本地等待唤醒”, and say “小智” once. One hit may create at most one streaming session; ending it must restore exactly one KWS capture.

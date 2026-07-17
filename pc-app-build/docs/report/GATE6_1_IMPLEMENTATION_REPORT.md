# Gate 6.1 Implementation Report

状态：Implementation complete; automated/Fake verification recorded below; Windows Real route rerun required after overlay
实施基线：`0be8159de4f6fe2161b7de82d971c5f32266c9b3`
阶段：Device Registry, Route Handling and Duplex Foundation

## 1. Delivered production behavior

### One product audio owner

- one application-scoped `AudioSessionSupervisor` is created by bootstrap;
- Gate 3 capture is routed through `SupervisorCaptureAdapter`;
- Gate 4 output plan is resolved by the supervisor;
- Gate 3 controller and local microphone test share one owner-aware microphone lease;
- playback activity is projected from the existing `PlaybackCoordinator`;
- lifecycle shutdown order is ViewModel -> Controller -> Supervisor.

### Device and route handling

- Windows-first `PyAudioDeviceRegistry` enumerates public name, host API, directions, defaults, formats and reported latency;
- PortAudio index exists only in the current in-memory snapshot;
- stored pinned identity is a private fingerprint and QML receives only a transient hashed key;
- system-default and pinned-device modes are persisted independently for input/output;
- pinned-device loss performs visible temporary default fallback without deleting the pin;
- polling route observer emits bounded public events and owns one non-daemon thread;
- route generation invalidates stale capture callbacks;
- an active capture/playback is finalized through existing controller/coordinator paths when its route changes.

### Duplex foundation and state

- concrete `PyAudioDuplexSession` opens one paired input/output route for future AEC/barge-in stages;
- capture and render-reference buffers are bounded at 64 frames with visible overflow counters;
- capture, playback, processing and route are four orthogonal state facts;
- processing remains `bypass`; AEC, NS, KWS and acoustic barge-in remain product-disabled.

### Settings and diagnostics

The existing Assistant settings page now provides:

- input selector;
- output selector;
- system-default mode;
- refresh;
- one-second local microphone level test;
- route/fallback error summary.

Diagnostics expose route/activity generations, public device names, lease owner, observer/session/buffer counters and microphone-test summaries. They do not expose private endpoint fingerprints or raw PCM.

## 2. Failure and cleanup rules

- no device or unavailable PyAudio -> route `unavailable`, not a fabricated default;
- stale route callback -> rejected and counted;
- pinned endpoint missing -> temporary default fallback and visible error code;
- route change during active audio -> playback cancel plus existing voice-turn stop;
- duplicate start/refresh/close -> idempotent;
- microphone-test failure -> lease released in `finally`;
- supervisor close -> observer stopped, route tasks cancelled, duplex closed, capture closed, buffers empty, lease owner `none`.

Required terminal facts:

```text
capture_activity              inactive
playback_activity             inactive
microphone_lease.owner        none
route_observer_running        false
duplex_open_stream_count      0
render_reference_buffer.size  0
duplex_capture_buffer.size    0
pending route tasks           0
second Python process         0 (no sidecar is created)
```

## 3. Automated and Fake acceptance

Packaging-environment evidence:

```text
compileall                         passed
Black --check                     passed (316 files unchanged)
Ruff                              passed
Gate 6.1 focused tests            11 passed
non-GUI cumulative regression     465 passed
Gate 6.1 Fake session             gate6_1_fake_session_complete
qmllint new/changed QML           passed without warnings
full QML/application smoke        blocked locally: Linux image lacks libEGL.so.1
Windows real route                pending user overlay run
```

The local `libEGL.so.1` limitation is an execution-environment block, not converted into a pass. The provided cumulative command still runs the complete test and QML suite on the user's configured Windows environment.

Primary command:

```powershell
cd C:\yuyinzhushou\note-assistant-app-runtime-v2\pc-app-build
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_1.ps1
```

Direct equivalent:

```powershell
python tools/verify_gate6_1_cumulative.py
```

The cumulative verifier is fail-fast and executes compileall, Black, Ruff, all tests with warnings as errors, QML smoke, the complete Gate 6.0 cumulative verifier (including retained Gate 5 checks) and the Gate 6.1 product-session Fake verifier.

## 4. Windows Real acceptance after overlay

Route/device-only run; it does not open the microphone:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_1_REAL_ROUTE.ps1
```

Route plus one-second local microphone test:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_1_REAL_ROUTE.ps1 `
  -MicrophoneTest `
  -Duration 1
```

Then launch the application and verify:

1. Assistant settings lists system default plus real input/output devices.
2. Select the Realtek devices, close and reopen the app, and confirm the selection persists.
3. Change either selector back to system default.
4. If a USB headset is available, pin it, unplug it while idle, refresh, and confirm the visible temporary fallback.
5. Start/stop PTT or one streaming turn and play one assistant reply; Gate 3/4 behavior must not regress.
6. Exit the app; no second Python process, capture/output stream or route-observer thread may remain.

Real device removal during active capture/playback is intentionally fail-closed: the active turn is stopped. Gate 6.1 does not silently restart capture on another endpoint.

## 5. Deferred scope

- product KWS and owner handoff: Gate 6.2;
- production AEC/NS processed path: Gate 6.3;
- acoustic barge-in: Gate 6.4;
- native Windows endpoint callbacks: optional replacement for polling;
- macOS concrete registry/observer/voice-processing evidence: deferred until a real Mac is available.

Gate 6.1 must be marked `Accepted-Windows` only after the cumulative verifier, real route runner and the short manual UI/voice regression above pass on the user's machine.

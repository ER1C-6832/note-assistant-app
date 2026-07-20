# Gate 6.3+6.4 Implementation Report

状态：Implementation complete；Windows cumulative/Real 待本地运行  
实施基线：`ed62ea77de908a7281fd6ec94bae590b6fd4e91f`  
阶段：Windows processed audio + acoustic barge-in closeout

## Delivered

- `WebRtcApmAudioProcessor`: lazy local AEC adapter, reverse stream required, 10 ms contract, AEC on, NS/AGC off.
- `LocalBargeInMonitorRuntime`: one PyAudio capture, one bounded tagged render/capture queue, one worker and processed-only VAD.
- playback render tap: actual PCM submitted to the output callback is copied to the monitor; no PCM is persisted.
- `AcousticBargeInCoordinator`: playback/route/session eligibility, exclusive owner, fail-closed processing, atomic handoff and lifecycle diagnostics.
- `AcousticBargeInConfirmed`: generation-checked single-writer transition.
- `AbortPlaybackTurn`: old playback cancel plus existing server abort before the new streaming start.
- bounded old-turn invalidation ledger and processed pre-roll staging.
- settings status and backend availability; existing “允许插话” preference now controls real product behavior.
- pinned optional dependency, installer, focused Fake verifier, cumulative verifier and interactive Windows Real runner.

## Frozen product values

```text
AEC                          enabled
NS                           disabled
AGC                          disabled
APM format                   PCM16 mono 16 kHz / 10 ms
monitor capture format       PCM16 mono 16 kHz / 20 ms
monitor queue                96 tagged work items, overflow visible
processed pre-roll           max 8 x 20 ms
barge-in default             off
monitor product upload       zero
raw microphone fallback      prohibited
```

## Delivery-environment evidence

```text
compileall                         passed
Black                              passed for changed app/tools/tests
Ruff                               passed for changed app/tools/tests
Gate 6.3+6.4 focused tests         10 passed
full Windows/Qt cumulative         pending user environment
real Windows acoustic barge-in     pending user environment
```

The delivery container could not install PySide6 from its restricted package mirror, so this report does not claim the Windows QML/full-suite run. `VERIFY_GATE6_3_4.ps1` performs that run in the user’s existing Windows venv.

A broader non-GUI Gate 3/4/6 run executed 218 cases: 208 passed, 5 skipped and 5 failed. The five failures were historical architecture assertions for root scripts intentionally absent from the Git clone because those scripts are gitignored and retained only in the user's working tree; they were not product-code failures.

## Test commands

From `pc-app-build`:

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_3_4.ps1
```

If the AEC package is not present:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_GATE6_3_4_AUDIO_PROCESSING.ps1
```

Then close the normal app so it does not own the microphone, use speakers, and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_3_4_REAL_BARGE_IN.ps1
```

The runner asks for one command that produces a long spoken answer. While that answer is playing, say one new natural-language command. It checks exactly one trigger/cancel/abort/promoted capture and asks the operator to confirm the audible result.

## Deferred

- macOS product adapter and Real evidence;
- enabling NS in product (current evidence says it can erase near-end speech);
- AGC;
- expert DSP controls and advanced device enhancements;
- statistical threshold/FAR/FRR calibration.

These items do not block the requested Windows demo closeout.

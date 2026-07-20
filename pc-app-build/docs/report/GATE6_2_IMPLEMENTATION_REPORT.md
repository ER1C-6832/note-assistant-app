# Gate 6.2 Implementation Report

状态：Implementation complete; Windows acceptance correction delivered; corrected Windows rerun pending  
实施基线：`d02b928ef4e71b6ab8019423f1f8fdcd3064e3e6`  
阶段：Offline KWS and Owner Handoff

## Delivered product behavior

- `KwsModelRegistry` resolves the existing Xiaozhi sherpa model from `%LOCALAPPDATA%\NoteAssistant\models\kws` without runtime download.
- `SherpaOnnxKeywordSpotter` is the selected `KeywordSpotterPort` adapter.
- `LocalKwsCaptureRuntime` owns one PyAudio input, one 64-frame drop-oldest PCM queue and one worker.
- `OfflineKwsCoordinator` applies the frozen idle/pause policy and coalesces state/route reconciliation.
- the lease is `owner + generation + route generation`; a wake hit transfers `WAKEWORD_KWS` to the exact next `ASSISTANT_CAPTURE` generation.
- an exact transferred assistant lease is idempotently claimable by the existing Gate 3 effect; unrelated generations remain rejected.
- manual PTT/streaming start can make KWS yield without opening a two-owner window.
- session terminal resumes KWS once; disable and shutdown never resume it.
- idle KWS frames are neither encoded nor uploaded; public diagnostics freeze `idle_uploaded_frames = 0`.
- the settings sheet adds a default-off KWS switch, wake phrase, model summary, status and classified error.
- the assistant is now always enabled at application startup and auto-connects by default; the home-page enable switch was removed, while connect/retry remains available.
- auto-connect is configurable in the settings sheet and existing preference files inherit the enabled default.
- KWS stop joins its worker and drains its private queue before microphone ownership transfers to assistant capture; KWS PCM cannot enter the assistant uplink queue.

## Model and dependency contract

The selected local layout is:

```text
sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/
  tokens.txt
  encoder-epoch-13-avg-2-chunk-16-left-64.onnx
  decoder-epoch-13-avg-2-chunk-16-left-64.onnx
  joiner-epoch-13-avg-2-chunk-16-left-64.onnx
  keywords_xiaozhi.txt
```

`pyproject.toml` adds optional dependency group `.[kws]` for numpy and sherpa-onnx. Missing dependencies/models are classified KWS failures and do not prevent application startup or manual voice use.

`INSTALL_GATE6_2_KWS_MODEL.ps1` copies the already-owned Android model into the application data layout using ASCII-only script source. Models are intentionally excluded from the overlay ZIP.

## Automated evidence recorded in the delivery environment

```text
compileall                          passed
Black                              passed
Ruff                               passed
Gate 6.2 focused tests             17 passed
actual AssistantController handoff passed
KWS/lease/tag focused regression  24 passed
non-GUI historical tests           431 executed; Gate 6.2 regressions passed
full Qt/QML smoke                  blocked locally: Linux image lacks libEGL.so.1
```

The non-GUI run also exposed repository-root verifier scripts intentionally absent from Git because the user's `.gitignore` keeps them local. Those historical asset assertions are not reported as product-code failures. The supplied Windows cumulative verifier runs against the user's complete working tree, where those scripts are present.

## Automated/Fake acceptance

From `pc-app-build`:

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_2.ps1
```

Direct equivalent:

```powershell
python tools/verify_gate6_2_cumulative.py
```

The verifier is fail-fast and runs compileall, Black, Ruff, every test with warnings as errors, QML smoke, retained Gate 6.1 Fake route acceptance, Gate 6.2 lifecycle/owner matrix, and model-layout inspection.

## Windows Real acceptance

If sherpa/numpy are not already present in the active venv:

```powershell
python -m pip install -e ".[kws]"
```

If the model is not already installed:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_GATE6_2_KWS_MODEL.ps1
```

Model package load plus one natural wake (one hit is sufficient; the runner exits immediately after the first hit and uses a 30-second maximum window):

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_2_REAL_KWS.ps1
```

Then launch the app, select continuous-conversation mode and enable offline wake in the audio settings. The assistant should enable and connect automatically; manual connect/retry is only the fallback. Verify:

1. idle status becomes local wake listening and no continuous idle upload is shown;
2. say “小智” once: exactly one streaming session starts;
3. while the session is active, KWS worker/stream are zero;
4. stop the session: KWS returns once;
5. play background speech/media without the phrase and observe no session;
6. start by button at the same time as a wake attempt and observe only one session;
7. change/default the microphone and observe old-generation stop plus one recovery;
8. disable KWS and verify it does not return after stop/disconnect;
9. remove/rename one model file and verify the button voice path still works;
10. exit with no capture, KWS worker, lease, pending task or second Python process.

## Deferred

- Windows Real results must be appended after the user's run; this report does not fabricate them.
- model embedding into a final installer belongs to the packaging gate; Gate 6.2 proves the installed layout and load smoke.
- AEC/NS processed microphone path is Gate 6.3.
- playback-period acoustic barge-in is Gate 6.4 and must not reuse the KWS detector.
- macOS remains deferred as requested.

## Windows correction evidence

The first Windows cumulative run supplied by the user reached `488 passed` but failed four Gate 6.2 assertions. All four were acceptance timing races: the tests observed a newly constructed Fake runtime before its `start()` call completed on the Windows scheduler. The assertions now wait for the observable active state and still require exactly two total instances and exactly one resume.

The same run also exposed a real lifecycle gap: KWS reconciliation subscribed to assistant state and route state but not to the shared microphone lease. A session could therefore release `ASSISTANT_CAPTURE` after the last state notification and leave KWS paused. The lease now publishes changes, reconciliation coalesces dirty notifications without dropping them, and tests cover session terminal, playback terminal and route-generation replacement.

The user's first 15-second one-hit model probe loaded the packaged model successfully but observed no hit. That result is retained as an inconclusive acoustic sample, not treated as proof that the model is invalid; an earlier live probe with the same model produced three hits. The corrected runner allows 30 seconds but returns immediately on the first accepted hit.

The reported tag defect was also corrected in this overlay. Tag usage is recomputed from both active and soft-deleted notes, deleting an in-use tag produces a Chinese message, and hard-delete refreshes `inUse`/`deletable` without restarting the application.

# Gate 6.0 Real Evidence Correction Delivery

状态：Implemented locally; Windows corrected rerun required  
覆盖基线：`3a8d018f98844bd3ee08b55c919084a0faffc5c1`  
产品音频拓扑修改：否

## Fixed

- AEC real success now requires acoustic semantics, not only clean process exit and terminal-zero.
- Double-talk separates a quiet lead-in from the user speech window and rejects erased near-end speech.
- Far-end-only requires observed acoustic coupling and at least 6 dB RMS attenuation.
- APM stream delay defaults to opened input/output latency instead of a fixed 50 ms.
- The render reference is deterministic speech-like audio generated in memory.
- Backend `has_voice()` remains diagnostic and cannot independently pass the probe.
- Real AEC failure codes propagate through the CLI and cumulative verifier.
- KWS validates model paths before prompting and prompts only after model/microphone readiness.
- KWS live requires two accepted hits separated by cooldown; an empty listening window is inconclusive.

## Local validation

```text
compileall                                      passed
Black                                           passed
Ruff                                            passed
new framework-neutral semantic tests            4 passed
updated architecture semantic test              1 passed
Windows native AEC/KWS                           not available in packaging environment
```

The overlay does not claim that Windows double-talk is fixed acoustically before the corrected runner is executed on the user's Realtek route. It fixes the false-positive verifier and changes the likely-bad 50 ms assumption to measured stream latency.

## Windows rerun

From `pc-app-build`:

```powershell
.\RUN_GATE6_0_REAL_AEC_CORRECTED.ps1
```

During double-talk, remain quiet for the displayed 1.5 second lead-in, then repeatedly say the prompted phrase until the test ends.

Required success fields:

```text
status                                      probe_complete
result.acceptance.accepted                  true
result.acceptance.criteria.raw_near_speech_observed       true
result.acceptance.criteria.near_end_preserved              true
error_code                                  null
terminal                                    all zero
process exit code                           0
```

If `aec_ns` reports `aec_near_end_not_preserved`, run a diagnostic isolation pass:

```powershell
python tools/probe_gate6_aec.py `
  --scenario double_talk `
  --duration 6 `
  --stream-delay-ms auto `
  --processing-mode aec_only `
  --speech-start-delay 1.5
```

- `aec_only` passes while `aec_ns` fails: NS is the primary suspect.
- both fail: delay/reference alignment or the AEC adapter is the primary suspect.
- raw speech is not observed: repeat the human test; the run is inconclusive rather than an AEC failure.

KWS still requires real compatible local model files. Example paths such as `C:\models\kws\encoder.onnx` are placeholders and are not created by installing `sherpa-onnx`.

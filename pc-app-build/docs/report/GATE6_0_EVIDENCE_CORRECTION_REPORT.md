# Gate 6.0 Real Evidence Correction Delivery

状态：v2 short-utterance verifier implemented locally; Windows short-utterance rerun required  
覆盖基线：`0afb861a63f0fdc25a015cc67e90f47aa19ba01c`  
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
- v1 whole-window median acceptance is superseded by aligned short-utterance activity analysis.
- Windows provisional default is AEC-only; NS and AGC are off.

## Local validation

```text
compileall                                      passed
Black                                           passed
Ruff                                            passed
framework-neutral semantic tests                5 passed
updated architecture semantic test              1 passed
Windows native AEC/KWS                           not available in packaging environment
```

The first correction proved AEC-only double-talk and far-end-only on the user's Realtek route. This v2 overlay fixes the remaining false-negative classification for intermittent speech; it does not claim short-utterance acceptance until rerun.

## Windows rerun

From `pc-app-build`:

```powershell
.\RUN_GATE6_0_REAL_AEC_CORRECTED.ps1
```

During double-talk, remain quiet for the displayed 1.5 second lead-in, then say the prompted phrase naturally several times. Continuous speech is no longer required.

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

AEC+NS remains an optional diagnostic comparison:

```powershell
python tools/probe_gate6_aec.py `
  --scenario double_talk `
  --duration 6 `
  --stream-delay-ms auto `
  --processing-mode aec_ns `
  --speech-start-delay 1.5
```

- AEC-only is the provisional Windows default.
- AEC+NS passing a normal short utterance permits further ASR comparison, but does not automatically make NS the default.
- AEC+NS failing while raw activity is observed records `aec_near_end_not_preserved`, not `aec_user_speech_not_observed`.

KWS still requires real compatible local model files. Example paths such as `C:\models\kws\encoder.onnx` are placeholders and are not created by installing `sherpa-onnx`.

# Gate 6.0 Implementation Report

状态：Automated/Fake implemented; Windows duplex/far-end evidence collected; corrected double-talk/KWS rerun pending  
实施基线：`19953b12d15ad5e76dfd4da0ca3dfa9aa353dec8`  
证据修正基线：`3a8d018f98844bd3ee08b55c919084a0faffc5c1`  
产品音频拓扑修改：否

## 1. Scope delivered

### Framework-neutral production boundary

- frozen audio device/route/duplex/processing/KWS protocols;
- device, route, timed PCM, processed PCM and metrics value objects;
- orthogonal audio state enums;
- owner names required by future atomic microphone handoff;
- bounded probe queue and actual resource tracker;
- report privacy/redaction and 64 KiB output bound;
- deterministic Fake device/backend/KWS/overflow scenarios.

### Explicit real probes

- public PyAudio device/Host API/format/latency inventory;
- bounded real capture/render timing probe;
- WebRTC APM candidate capability and live far-end/double-talk probe;
- sherpa-onnx import/model/live microphone/cooldown probe;
- no PCM/model dump and no product uplink;
- terminal resource diagnostics.

### Verification

- `VERIFY_GATE6_0.ps1` automated/Fake fail-fast entry;
- `verify_gate6_0_fake_probe.py`;
- `verify_gate6_0_cumulative.py` with opt-in real flags;
- 16 new framework-neutral unit/architecture tests.

## 2. Candidate backend findings before Windows execution

The implementation intentionally does not freeze a winner from static inspection.

| Candidate | Probe support | Product decision |
|---|---|---|
| `aec-audio-processing` WebRTC APM | Optional native adapter, AGC off, reverse stream required | pending Windows real |
| `webrtc-apm` | import capability inventory only | pending API/package evidence |
| legacy `webrtc-audio-processing` | import capability inventory only | likely fallback research only |
| Windows system/endpoint AEC | platform capability marker | pending concrete endpoint probe |
| macOS voice processing | platform capability marker | Pending macOS Real Evidence |
| bypass | timing/failure baseline only | never sufficient for speaker barge-in |

KWS candidate: sherpa-onnx `KeywordSpotter`, with explicitly supplied local model files.

## 3. Local validation performed in packaging environment

```text
compileall                         passed
Black check                       passed after formatting
Ruff                              passed
Gate 6.0 tests                    16 passed
Gate 6.0 Fake verifier            gate6_0_fake_probe_complete
real audio devices                not run
real duplex                       not run
real AEC far-end-only             not run
real AEC double-talk              not run
real KWS                          not run
macOS real                        pending_real_macos
```

The packaging environment is Linux without the user's Windows devices, so local Fake results are not Windows evidence.

## 4. Windows execution order

Automated/Fake:

```powershell
.\VERIFY_GATE6_0.ps1
```

Real device and duplex:

```powershell
python tools/probe_gate6_audio_devices.py
python tools/probe_gate6_duplex.py --duration 3
```

AEC capability and real acoustic samples:

```powershell
python tools/probe_gate6_aec.py --scenario capability
python tools/probe_gate6_aec.py --scenario far_end_only --duration 5
python tools/probe_gate6_aec.py --scenario double_talk --duration 6
```

If the optional AEC candidate is unavailable:

```powershell
python -m pip install aec-audio-processing==1.0.1
```

This dependency is a probe candidate only and is not added to `pyproject.toml` before evidence.

KWS import probe:

```powershell
python tools/probe_gate6_kws.py
```

KWS live requires local model paths as documented in `GATE6_0_PROBE_CONTRACT_FREEZE.md`.

Optional cumulative real run excluding KWS model-specific arguments:

```powershell
python tools/verify_gate6_0_cumulative.py `
  --include-real-devices `
  --include-real-duplex `
  --include-real-aec
```

KWS 可通过同一 cumulative runner 的 `--include-real-kws` 和五个 `--kws-*` 路径加入；模型参数不会写入普通报告正文。

## 5. Current decision status

```text
Windows default backend: pending_real_probe_report
macOS target backend: pending_real_macos
fallback policy: pending
internal block candidate: 10 ms
public frame compatibility: 20 ms
AGC product default: false
KWS product default: false
acoustic barge-in product default: false
Gate 6.1 may start: no
```

The report must be amended from actual Windows JSON and human observations before Gate 6.0 can be accepted and Gate 6.1 authorized.

## 6. Windows evidence correction after the first real run

The first Windows run supplied after commit `3a8d018f` established:

- full cumulative automated verification passed with `458 passed`;
- default Realtek input/output opened as a real duplex route with ordered capture/render timestamps, no overflow, no product uplink, no persisted PCM and terminal resources at zero;
- far-end-only reduced median RMS from `99.369` to `5.064` (about 25.9 dB) with no reported processed VAD trigger;
- double-talk reduced median RMS from `168.381` to `4.82`, processed peak max was only `23`, and processed VAD trigger count was zero;
- sherpa-onnx imported, but the five example paths under `C:\models\kws` did not exist, so KWS live capture never started.

The original runner incorrectly treated native completion and terminal-zero as acoustic success. The double-talk result is therefore rejected: it did not prove that near-end speech survived. No backend is selected from this evidence.

This correction freezes the following verifier behavior:

- AEC delay defaults to the sum of the opened input/output stream latencies instead of a hard-coded 50 ms; an explicit `0..500` ms override remains available;
- the render fixture is deterministic speech-like audio rather than one 550 Hz sinusoid;
- double-talk has a 1.5 second quiet baseline followed by a speech window;
- raw near-end speech must be observed and processed speech must remain measurably above its quiet baseline;
- semantic failure returns non-zero even when cleanup succeeds;
- the backend VAD flag is diagnostic only and cannot authorize acceptance by itself;
- KWS validates files, loads the model and opens the microphone before prompting;
- KWS live requires two distinct accepted detections separated by the cooldown.

Corrected rerun:

```powershell
python tools/probe_gate6_aec.py `
  --scenario far_end_only `
  --duration 5 `
  --stream-delay-ms auto `
  --processing-mode aec_ns

python tools/probe_gate6_aec.py `
  --scenario double_talk `
  --duration 6 `
  --stream-delay-ms auto `
  --processing-mode aec_ns `
  --speech-start-delay 1.5
```

For diagnosis only, if `aec_ns` does not preserve near-end speech, repeat double-talk with `--processing-mode aec_only`. Do not select a production backend until the corrected runner returns `probe_complete`, `acceptance.accepted = true`, and exit code zero.

## 7. Windows AEC-only/AEC+NS comparison and short-utterance correction

Subsequent real Windows evidence on the same Realtek route:

```text
AEC-only double-talk
  duration                         8 s
  stream delay                     120 ms auto
  echo attenuation                 11.881 dB
  raw baseline/speech RMS          100.464 / 181.707
  processed baseline/speech RMS     29.082 / 46.274
  near-end retention ratio           0.2116
  acceptance                       passed

AEC-only far-end-only
  echo attenuation                  6.547 dB
  minimum budget                    6.000 dB
  acceptance                       passed with limited margin

AEC+NS continuous double-talk
  raw baseline/speech peak          334 / 1215
  processed baseline/speech RMS     5.002 / 6.180
  near-end retention ratio          0.0471
  v1 acceptance                    inconclusive
```

The raw peak increase in the AEC+NS run proves that `aec_user_speech_not_observed` was a misleading v1 classification. The v1 median/absolute-threshold method is superseded by `aligned_short_utterance_activity_v2`:

- bounded per-frame RMS statistics only; no PCM persistence;
- p75/p90/p95 summaries;
- baseline-derived raw and processed activity thresholds;
- minimum raw active frames and consecutive run;
- processed activity evaluated at the same raw-active frame indices;
- aligned active-frame retention ratio;
- no fixed processed RMS floor of 12;
- intermittent short utterances may pass without occupying half the speech window.

The provisional Windows default is now `aec_only`, AEC on, NS off, AGC off, 10 ms internal block and auto delay (120 ms on this route). `aec_ns` remains an explicit diagnostic mode until normal short-utterance evidence proves that its stronger suppression does not damage ASR/barge-in.

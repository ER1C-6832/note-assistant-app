# Gate 6.0 Implementation Report

状态：Automated/Fake implemented; Windows Real pending  
基线：`19953b12d15ad5e76dfd4da0ca3dfa9aa353dec8`  
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

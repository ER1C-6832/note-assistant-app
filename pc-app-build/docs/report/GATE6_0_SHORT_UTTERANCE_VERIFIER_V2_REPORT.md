# Gate 6.0 Short-Utterance Verifier v2 Delivery

状态：Implemented — Windows rerun required  
覆盖基线：`0afb861a63f0fdc25a015cc67e90f47aa19ba01c`  
产品音频拓扑修改：否

## Decision from real evidence

The Realtek comparison supports this provisional Windows profile:

```text
backend                aec-audio-processing / WebRTC APM
AEC                    enabled
NS                     disabled
AGC                    disabled
internal block         10 ms
sample format          16 kHz mono PCM16
delay                  auto; observed 120 ms
```

AEC-only passed double-talk and far-end-only. The far-end-only result was 6.547 dB against a 6 dB minimum, so margin remains limited. AEC+NS produced much stronger far-end suppression but suppressed near-end energy enough that it is not the default candidate.

## Superseded verifier behavior

v1 compared the median RMS of the whole 4.5–6.5 second speech window against fixed multipliers and an absolute processed RMS floor. That incorrectly classified a continuous AEC+NS run as `aec_user_speech_not_observed` even though raw peak increased from 334 to 1215.

## v2 activity contract

The verifier now stores at most 2048 bounded RMS floats per phase; it never stores PCM. It reports only aggregates:

- baseline and speech p75/p90/p95;
- baseline-derived raw/processed activity thresholds;
- raw active frame count and ratio;
- longest raw active run;
- processed activity at the same raw-active indices;
- longest aligned processed run;
- median raw/processed lift on aligned active frames;
- near-end retention ratio.

Machine acceptance requires:

```text
raw active frames                       >= 5
longest raw active run                  >= 3 frames
processed active frames on raw activity >= 3
longest aligned processed run           >= 2 frames
processed/raw active-frame ratio        >= 0.10
near-end retention ratio                >= 0.03
```

These are Gate 6.0 probe thresholds, not final product VAD thresholds. Gate 6.1 may revise them using normal short commands and ASR evidence.

## Local validation

```text
compileall                              passed
Black                                   passed
Ruff                                    passed
framework-neutral semantic tests        5 passed
updated architecture semantic test      1 passed
ZIP audit                               required during packaging
Windows real rerun                      pending
```

## Rerun

After overlay, run automated regression and the corrected AEC-only default:

```powershell
.\VERIFY_GATE6_0.ps1
.\RUN_GATE6_0_REAL_AEC_CORRECTED.ps1
```

During double-talk, wait through the 1.5 second quiet baseline and then say several natural short commands, for example:

```text
小智，停一下。
小智，记录客户报价。
小智，打开今天的待办。
```

Continuous speech for the entire window is not required. A successful report must state `analysis_method = aligned_short_utterance_activity_v2`, `raw_near_speech_observed = true`, `near_end_preserved = true`, `acceptance.accepted = true`, and terminal zero.

# Gate 6.3+6.4 Windows Audio Closeout Freeze

状态：Implemented；Automated/Fake 待用户 Windows cumulative；Real barge-in 待用户听感签字  
实施基线：`ed62ea77de908a7281fd6ec94bae590b6fd4e91f`  
范围：Windows 产品链路

## 1. 合并理由与范围

Gate 6.0 已用真实 Windows 设备证明 WebRTC APM 的 AEC-only far-end 和 double-talk 可行；Gate 6.1 已完成 route/supervisor/owner；Gate 6.2 已完成 KWS 与 owner handoff。为尽快完成产品，本交付将原 6.3 processed path 和 6.4 barge-in 接线合并为一个可回滚阶段。

本阶段只交付：

- 播放 callback 的 render reference；
- 16 kHz/mono/10 ms WebRTC APM AEC processing；
- processed-only 严格 VAD；
- `BARGE_IN_MONITOR -> ASSISTANT_CAPTURE` 原子交接；
- 旧播放取消、旧 turn abort、旧 TTS 拒绝；
- bounded processed pre-roll；
- 设置状态、诊断、Fake/cumulative/Windows Real 验收。

本阶段明确延后 macOS、产品 NS、AGC、复杂设备增强、通用阈值训练和统计 FAR/FRR。

## 2. 冻结产品链路

```text
PyAudio output callback
  -> rendered PCM reference
  -> 16 kHz mono 10 ms conversion
  -> WebRTC APM reverse stream

PyAudio microphone callback
  -> bounded monitor queue
  -> WebRTC APM capture stream (AEC-only)
  -> processed-only VAD
  -> one Confirmed event
  -> cancel old playback + abort old server turn
  -> atomic owner transfer
  -> processed pre-roll + normal AssistantAudioEngine capture
```

Raw microphone PCM is never a fallback barge-in detector. Monitor PCM is not encoded, uploaded, persisted, logged or placed in `AssistantState`/Runtime events.

## 3. DSP decision

| Item | Product value | Reason |
|---|---|---|
| backend | `aec-audio-processing==1.0.1` | Windows probe created reverse-stream APM successfully |
| AEC | enabled | far-end and double-talk evidence accepted |
| NS | disabled | prior `aec_ns` double-talk evidence suppressed near speech and was inconclusive |
| AGC | disabled | avoids changing product gain semantics |
| internal block | 10 ms, 16 kHz, mono PCM16 | backend contract |
| monitor input | 20 ms, converted to two 10 ms blocks | current capture contract |
| pre-roll | max 8 processed 20 ms frames | matches bounded uplink ingress |
| activation | default-off user setting | acoustic/environment variability |

NS remains an available backend capability but is not effective in the product barge-in path.

## 4. State and race contract

One accepted confirmation performs exactly one transition:

1. validate connection/streaming/playback/monitor/capture generations;
2. allocate exactly one new voice token and capture generation;
3. invalidate the old playback turn;
4. cancel physical playback without producing natural `PlaybackEnded`;
5. send existing transport abort for the old turn;
6. start exactly one new streaming capture using the transferred lease.

Duplicate/stale confirmations and late old playback/TTS events are no-ops. Gate 4 automatic next-turn remains driven only by a genuine natural `ActualPlaybackEnded`; acoustic cancellation can never trigger it.

KWS is paused during playback and barge-in monitoring. Button/PTT/streaming capture may synchronously make the monitor yield. Route interruption, disconnect, disable, mode switch and shutdown stop and drain the monitor.

## 5. Failure policy

- missing/import/create/process/format/overflow errors are visible and fail closed;
- no raw-mic fallback and no silent retry loop for the same playback/route context;
- a new route or playback generation permits one new attempt;
- manual PTT/streaming and playback remain available when AEC is unavailable;
- worker/capture/queue/lease/task cleanup is idempotent and bounded.

## 6. Acceptance

Automated/Fake:

```powershell
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_3_4.ps1
```

Dependency and Windows Real:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_GATE6_3_4_AUDIO_PROCESSING.ps1
powershell -ExecutionPolicy Bypass -File .\RUN_GATE6_3_4_REAL_BARGE_IN.ps1
```

Real acceptance requires speakers rather than headphones, one sufficiently long assistant reply, one natural-language interruption during playback, machine counters of exactly one cancel/abort/new turn, and explicit user confirmation that the old reply stopped and the new request was answered.

## 7. Exit condition

Gate 6 is `Accepted-Windows` only after cumulative and Real runners both return zero. macOS stays `deferred` and does not block the requested Windows product closeout.

# ADR-010 Addendum: Gate 6.3+6.4 Windows Acoustic Barge-in

状态：Implemented；Windows Real signoff pending  
实施基线：`ed62ea77de908a7281fd6ec94bae590b6fd4e91f`

## Decision

1. Original Gate 6.3 and 6.4 are delivered together for Windows product closeout.
2. Playback output is the only far-end reference source. The monitor uses WebRTC APM reverse/capture processing at 16 kHz mono in 10 ms blocks.
3. AEC is enabled; NS and AGC are disabled. The prior Windows `aec_ns` result is insufficient for product use because near-end speech was not preserved reliably.
4. Barge-in VAD consumes only processed PCM. Backend failure is fail-closed and never falls back to raw-mic detection.
5. `BARGE_IN_MONITOR` is an exclusive lease owner. Promotion to the next `ASSISTANT_CAPTURE` generation is atomic and carries at most eight processed 20 ms pre-roll frames in memory.
6. One confirmed event invalidates and cancels the current playback, sends one existing protocol abort for the old turn, and starts one new streaming capture.
7. Acoustic cancellation is not a natural `PlaybackEnded`. Gate 4 auto-next therefore cannot create a duplicate turn.
8. Old turn TTS streams are held in a bounded invalidation ledger and rejected after interruption.
9. The setting remains default-off and is disabled when the local AEC adapter is unavailable.
10. macOS, NS tuning, AGC and population-level threshold calibration are deferred.

## Consequences

- No second process, localhost bridge or second assistant runtime is introduced.
- Continuous playback monitoring uses one bounded queue, one capture stream and one worker only while eligible.
- Idle KWS and playback-period acoustic monitoring remain separate services and owners.
- Windows can be closed out independently; the overall cross-platform claim remains incomplete until a later macOS implementation and Real run.

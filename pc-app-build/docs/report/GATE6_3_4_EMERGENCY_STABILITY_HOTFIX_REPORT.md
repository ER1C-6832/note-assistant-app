# Gate 6.3/6.4 Emergency Stability Hotfix Report

## Incident

After Gate 6.3/6.4 was connected to the product runtime, real conversations could terminate the
desktop process during uplink finalization, thinking, downlink startup, or playback. Offline KWS
could also remain unavailable after the failed native audio-owner transition.

The strongest code-level risk is the experimental in-process acoustic monitor: it opens an
additional PortAudio input stream, feeds render and capture frames through the native WebRTC APM
wrapper, and starts or stops this native graph at playback/session boundaries. A native lifetime
race can terminate the process without a catchable Python exception. No crash dump was available,
so this report records that as the leading cause rather than claiming a proven native stack frame.

## Emergency decision

Product stability takes priority over acoustic barge-in. The production composition root now
fails closed and does not create `AcousticBargeInCoordinator`. The existing AEC/barge-in adapters,
Fake tests, and isolated real probe remain in the repository for later investigation, but they are
not allowed onto the normal conversation path.

At startup, a previously persisted `streaming_barge_in_enabled=true` is atomically rewritten to
`false`. If the preference file cannot be rewritten, the in-memory preference is still forced to
`false` so the application can start safely. The rewrite saves the complete already-loaded
preference snapshot, preserving KWS, auto-connect, device route, and UI preferences even when the
preference file has not been created yet.

This guard does not alter:

- assistant auto-enable or auto-connect;
- offline KWS enablement, model selection, or cooldown;
- `WAKEWORD_KWS -> ASSISTANT_CAPTURE` handoff;
- PTT or ordinary continuous conversation;
- server uplink/downlink and playback when barge-in is disabled.

The settings sheet exposes an explicit stability-protection status instead of incorrectly asking
the user to install AEC dependencies.

## Repository hygiene

The Gate 6.3/6.4 commit also contained a generated pytest temporary tree whose name starts with
`Users...AppDataLocalTempnote-assistant-...-pytest-`. The hotfix adds a targeted ignore rule and
`APPLY_GATE6_3_4_STABILITY_HOTFIX.ps1` removes only matching directories under `pc-app-build`.
Running `git add -A` after the cleanup stages their deletion from the next commit.

The pre-existing deleted-note/tag regression now waits for the hard-delete mutation to become
terminal before issuing the next delete command. This matches the QML contract, which disables tag
actions while `mutationBusy` is true, and removes a full-suite-only timing race without weakening
the tag usage assertion.

## Acceptance

Automated acceptance:

```powershell
powershell -ExecutionPolicy Bypass -File .\APPLY_GATE6_3_4_STABILITY_HOTFIX.ps1
powershell -ExecutionPolicy Bypass -File .\VERIFY_GATE6_3_4_STABILITY_HOTFIX.ps1
```

Required Windows manual smoke:

1. Start the app and verify it enables and connects automatically.
2. Verify the KWS setting remains enabled and say the wake phrase once while idle.
3. Complete one spoken request through STT, thinking, TTS downlink, and playback.
4. Repeat at least five turns, including one manual stop and one reconnect.
5. Confirm there is no process termination and that KWS resumes exactly once after a terminal
   session stop.
6. Confirm the acoustic barge-in switch is unavailable and reports stability protection.

Acoustic interruption is intentionally not an exit criterion for this emergency patch.

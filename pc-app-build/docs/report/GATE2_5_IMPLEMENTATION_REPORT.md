# Gate 2.5 Recovery / Error / Shutdown Implementation Report

## Baseline

Implementation is based on repository commit `3f9329c0fb2316b963855c6dd9bdff31bb156f6e`, after Gate 2.4 real text acceptance and the cumulative verifier compatibility fix.

Referenced contracts:

- `GATE2_IMPLEMENTATION_PLAN.md`
- `GATE2_CONTROLLER_CONCURRENCY_SPEC.md`
- `GATE2_FULL_STATE_CONTRACT.md`
- `GATE2_PROTOCOL_COMPATIBILITY.md`
- Android `ReconnectPolicy.kt` and `LocalAssistantController.kt`

## Architecture

The single-writer rule remains unchanged:

```text
command / transport / timer
-> AssistantEvent
-> one event queue
-> one event pump
-> pure reducer
-> immutable AssistantState replacement
```

The reconnect timer never mutates state. It only emits `ReconnectTimerFired` with the scheduled connection generation and attempt number.

## Recovery policy

`assistant/network/reconnect_policy.py` implements:

```text
normal close 1000       -> no reconnect
disabled                -> no reconnect
manual disconnect       -> no reconnect
non-retryable config    -> no reconnect
abnormal close/failure  -> max 3 attempts
base delays             -> 0.5s, 1.5s, 3.0s
```

Jitter is deterministic and bounded for the same State/Event input. It is derived from connection generation, attempt, and the triggering event monotonic timestamp, so Reducer behavior stays reproducible while different failures do not share identical retry timing.

## Ownership and concurrency

Controller-owned tasks:

```text
event_pump_task
effect_tasks set
single reconnect_timer_task
```

Manual reconnect, disable, runtime switch, identity reset, and shutdown explicitly cancel the timer. Automatic and manual reconnect cannot open in parallel.

## Generation behavior

- abnormal close/failure schedules a timer against the failed generation;
- timer fire is ignored when generation or attempt is stale;
- a valid timer fire creates exactly one new connection generation;
- old close/hello callbacks cannot overwrite the new state;
- duplicate close/failure callbacks for one generation cannot create a second timer or consume another attempt;
- successful hello resets reconnect attempt to zero.

## Error classification

Stable recovery codes are defined in `assistant/errors.py`.

Retryable network failures enter bounded recovery. Missing token, invalid endpoint, and runtime adapter mismatch are fail-closed non-retryable errors and do not consume three pointless retries.

## Shutdown

Shutdown order for the Gate 2 runtime boundary:

1. stop accepting public commands;
2. cancel reconnect timer;
3. dispatch `ShutdownRequested` through the event pump;
4. cancel runtime effects;
5. close transport with a bounded timeout;
6. stop the event pump;
7. drain pending events;
8. expose `closed=True` with no owned timer/effect task.

No subprocess, sidecar, localhost HTTP path, second event loop, or second AssistantState is introduced.

## Automated acceptance

`VERIFY_GATE2_5.ps1` runs cumulative formatting, lint, compile, Gate 1, and Gate 2.1-2.5 tests.

Gate 2.5 tests cover:

- exact base backoff and max attempts;
- deterministic bounded jitter;
- normal/manual/disabled no-reconnect decisions;
- abnormal close and transport failure scheduling;
- stale timer rejection;
- generation advancement;
- successful hello reset;
- max-attempt exhaustion;
- disable cancellation;
- manual connect/reconnect vs auto timer mutual exclusion;
- duplicate transport callback ownership;
- non-retryable configuration failures;
- bounded shutdown with a deliberately hanging close adapter;
- the Real transport acceptance interruption preserves close code `1012` at the typed event boundary.

## Mandatory real acceptance

`RUN_GATE2_5_REAL_RECOVERY.ps1`:

1. loads the persisted Gate 2.2 identity/token;
2. completes a real Gate 2.3 hello/session;
3. forces one abnormal close code `1012` on that real socket;
4. waits for automatic recovery;
5. requires a higher connection generation and a second non-empty real session;
6. prints only redacted identity/session diagnostics.

The script does not run activation and does not use Fake transport for the recovered connection.

Automated tests do not replace this Real Gate. Gate 2.5 real recovery is complete only after the runner exits `0` against the real service.

## Local reconstruction validation

The final overlay was validated against a reconstructed Gate 2.4 baseline whose key Runtime blobs match repository commit `3f9329c0fb2316b963855c6dd9bdff31bb156f6e`.

```text
Gate 2.1-2.5 tests: 98 passed
warnings-as-errors: 98 passed
Black: 72 files unchanged
Ruff: passed
compileall: passed
Python 3.10 AST compatibility: 70 files passed
Gate 1.7 architecture checks relevant to single-process ownership: 5 passed
```

The reconstruction does not contain the complete Gate 1 application tree or local PySide6 runtime, so it does not substitute for the cumulative Gate 1 suite. `VERIFY_GATE2_5.ps1` runs Gate 1.1-1.7 and Gate 2.1-2.5 in the complete user checkout.

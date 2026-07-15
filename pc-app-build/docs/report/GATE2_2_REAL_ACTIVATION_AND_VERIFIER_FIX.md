# Gate 2.2 Real Activation and Verifier Fix

## Scope

This correction addresses two separate defects found after the Gate 2.2 overlay was applied.

1. The Gate 2.1 architecture test permanently required `VERIFY_GATE2_1.ps1`, even though the current cumulative verifier is `VERIFY_GATE2_2.ps1` and future gates will continue replacing the top-level verifier.
2. The real activation helper incorrectly required the operator to provide OTA and authorization URLs and generated a new random identity instead of first migrating the already-authorized legacy PC identity.

## Verifier correction

Gate 2.1 now requires at least one current `VERIFY_GATE*.ps1` script that still executes `tests/gate2_1`. The covering verifier must retain fail-fast handling and continue running the Gate 1.7 regression suite. The test no longer binds repository validity to an obsolete filename.

## Real endpoint defaults

The PC Runtime now uses the same established defaults as the previous PC client and the Android client:

- OTA: `https://api.tenclass.net/xiaozhi/ota/`
- authorization: `https://xiaozhi.me/`
- activation protocol: `v2`

Environment variables remain optional overrides. They are no longer required for the normal real check.

## Legacy identity migration

Before generating a new identity, the real-check composition attempts to read:

```text
%LOCALAPPDATA%\py-xiaozhi\config\efuse.json
%LOCALAPPDATA%\py-xiaozhi\config\config.json
```

It migrates the existing `DEVICE_ID`, `CLIENT_ID`, serial number, and HMAC key into `NoteAssistant/data/assistant_runtime.json`. This lets the server recognize an already-authorized PC identity instead of treating the same computer as a new device.

Secrets are never printed. The output only states whether the identity came from the legacy client, the current NoteAssistant config, or a newly generated identity.

## Manual activation semantics

`RUN_GATE2_2_REAL_ACTIVATION.ps1` performs one real server check. It is not an automatic activation loop.

- exit `0`: the server recognizes the identity and returns runtime configuration;
- exit `2`: the server returned a verification code; the user completes authorization manually and runs the check again;
- exit `1`: transport, protocol, or configuration failure.

## Gate completion

This correction does not declare Gate 2 complete. Real WebSocket hello/session and real text acceptance remain mandatory in Gate 2.3/2.4 and the Gate 2.7 Real Gate.

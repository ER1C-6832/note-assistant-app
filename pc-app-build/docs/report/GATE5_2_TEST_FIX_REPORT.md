# Gate 5.2 cumulative test fix report

Status: test-only correction candidate  
Baseline: `80ea5d68a09a57bed9d3e8bd3f4c7b41ab6d6b19` (`tools added`)

## Windows evidence

Gate 5.2 Fake mutation verification completed successfully, but cumulative pytest reported two test defects:

1. The Gate 5.1 architecture test still required the literal production symbol `Gate51ToolExecutor` after Gate 5.2 correctly replaced the composition-root executor with `Gate52ToolExecutor`, which subclasses `Gate51ToolExecutor`.
2. The large conditional-batch test used `all()` over a generator containing `await`. Python treats that expression as an async generator, which is not synchronously iterable.

Neither failure indicates a production mutation defect.

## Fixes

- Update the Gate 5.1 source contract to require `Gate52ToolExecutor` in Bootstrap and explicitly verify `Gate52ToolExecutor(Gate51ToolExecutor)` inheritance, preserving all Gate 5.1 read/UI behavior.
- Resolve all note snapshots with `asyncio.gather()` before asserting that large pin and tag-bind requests made zero writes.
- No application, database, MCP executor, confirmation, UI, or protocol code is changed.

## Local verification

- Black: passed for both changed files.
- Ruff: passed for both changed files.
- Gate 5.1 architecture test: `3 passed`.
- Gate 5.2 mutation test file in the isolated SQLite package: `6 passed`.

Full Windows cumulative verification remains authoritative because the local assembly does not contain every earlier assistant package.

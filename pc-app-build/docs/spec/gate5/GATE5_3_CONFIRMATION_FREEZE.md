# Gate 5.3 Confirmation Freeze

状态：实现候选  
基线：Gate 5.2 + test fix

## 1. Scope

Gate 5.3 enables the final three advertised tools:

```text
assistant.confirm
assistant.reject
assistant.list_pending_confirmations
```

It also completes these high-risk branches:

```text
notes.replace_content
notes.delete
notes.pin when note count > 5
notes.restore when note count > 5
tags.bind replace
tags.bind add/remove when note count > 5
tags.delete
```

All Gate 5.0 through 5.2 behavior remains available through `Gate53ToolExecutor`, which extends `Gate52ToolExecutor`.

## 2. Pending confirmation ownership

`PendingConfirmationService` is the only owner of confirmation state.

Frozen limits:

```text
capacity = 32
TTL = 120 seconds
terminal history = bounded, in memory only
persistence = none
```

Each pending object binds:

```text
confirmation id
origin connection generation
origin session id
tool name and risk
canonical arguments fingerprint
private canonical arguments
safe preview
affected note ids and tags
note updated_at snapshots
created_at and expires_at
```

Private arguments and session ids use repr-safe fields and are never projected to tool results, QML, ordinary logs, reports, or AssistantState.

## 3. Finalization rules

Confirmation, rejection, expiry, disconnect invalidation, and local UI actions serialize through one async lock.

- The first valid finalizer claims the pending object.
- A repeated confirm or reject returns `confirmation_consumed` and performs no mutation.
- Expired objects return `confirmation_expired`.
- A voice confirmation must match both session and connection generation.
- A trusted local UI action may consume the same pending id without pretending to be a remote session.
- Disconnect, disable through transport closure, coordinator closure, and application shutdown invalidate pending objects.
- Capacity overflow returns blocked and creates no pending object.

## 4. Revalidation and execution

Before a confirmed note operation executes, the executor reloads every target and compares its `updated_at` snapshot. Missing, deleted/restored, or otherwise modified targets return `stale_confirmation_target` and do not apply the frozen command.

Confirmed operations still cross the existing application boundaries:

```text
NoteQueryService
NoteCommandService
TagCatalogService
UiCommandBus
```

No confirmation handler imports repositories, SQLAlchemy sessions, SQLite, or QML.

Mutation behavior:

- replace content preserves title and tags;
- delete uses soft delete only;
- large pin and restore use existing batch commands;
- tag binding remains one all-or-nothing repository transaction;
- tag deletion rechecks protected/system/in-use/deletable state immediately before deletion;
- committed database changes followed by UI refresh failure return `partial_success`.

## 5. UI confirmation

`ui.show_confirmation` resolves a pending id in the current MCP context and dispatches a typed `SHOW_CONFIRMATION` command.

The QML dialog receives only:

```text
tool name
safe operation/count preview
affected note ids
affected tags
confirmation id and expiry metadata
```

The dialog never receives note title, note content, replacement content, raw MCP arguments, tokens, or identity values.

The Confirm and Reject buttons call the Qt adapter, which invokes `Gate53ToolExecutor.confirm_local` or `reject_local`. Those paths consume the same `PendingConfirmationService` object used by voice tools.

## 6. Acceptance boundary

Gate 5.3 acceptance is automated/Fake/local integration only. The user has deferred complete natural-language Real CRUD/tag/UI/confirmation acceptance to Gate 5.4.

Gate 5.3 must not be reported as Real accepted based only on the local verifier.

# Gate 5.2 Mutation Contract Freeze

状态：实施冻结  
基线：`f69137bdf11002fc036d6dcda9dfa1f094390c64`

## Scope

Gate 5.2 enables these 13 tools through the production `ToolRegistry`:

```text
notes.create
notes.append
notes.update_title
notes.replace_content
notes.convert_type
notes.pin
notes.delete
notes.restore
tags.create
tags.search
tags.list
tags.delete
tags.bind
```

Read/resolve/UI tools from Gate 5.1 remain enabled. Confirmation execution tools remain blocked until Gate 5.3.

## Immediate mutations

The following operations execute immediately after schema and current-state validation:

- `notes.create`, forcing `source=voice_pc`;
- `notes.append`, preserving title and tags;
- `notes.update_title`, preserving content and tags;
- `notes.convert_type`, mapping todo to the protected `待办` tag;
- `notes.pin` for one through five notes;
- `notes.restore` for one through five deleted notes;
- `tags.create`;
- `tags.bind add/remove` for one through five notes.

All note writes cross `NoteCommandService`. MCP code does not import Repository, SQLAlchemy, SQLite, Qt, or QML.

## Confirmation previews

The following return `status=requires_confirmation` and perform zero database/catalog writes in Gate 5.2:

- `notes.replace_content`;
- `notes.delete`;
- `notes.pin` for more than five notes;
- `notes.restore` for more than five notes;
- `tags.bind replace`;
- `tags.bind add/remove` for more than five notes;
- `tags.delete`.

The result contains a safe count/operation preview only. `confirmation_id` is `null` and `confirmation_available=false` until Gate 5.3. Raw replacement content is not copied into preview, logs, lifecycle events, or reports.

## Tag ownership

`TagCatalogService` is the shared UI/MCP facade around one `TagCatalog` instance. Synchronous UI calls and asynchronous MCP calls use the same re-entrant lock, preventing concurrent JSON catalog writes from overwriting each other.

`BatchUpdateTagsCommand` and `SqlAlchemyNoteRepository.update_tags_many()` apply add/remove/replace to all active targets in one database transaction. Missing or deleted targets abort the entire operation.

## UI refresh semantics

Committed mutations dispatch an internal typed UI refresh command. A refresh failure does not claim that the database transaction rolled back:

```text
status=partial_success
error_code=ui_refresh_failed
result.committed=true
result.ui_refreshed=false
```

## Idempotency

Gate 5.0 request-id dedupe remains the mutation idempotency owner. The same generation/session/request-id and canonical payload executes at most one transaction. Reusing the id with different arguments remains a conflict.

## Real-language acceptance

Automated/Fake/local integration proves deterministic mutation behavior. Real acceptance is user-driven in the normal desktop UI: the user chooses natural-language commands and verifies visible UI/database effects. A scripted runner that tells the model an internal tool name is not sufficient evidence.

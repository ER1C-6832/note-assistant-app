# Gate 5.2 User-Driven Natural-Language Acceptance

状态：验收契约

## Principle

Run the normal desktop application and speak or type ordinary requests of your own choosing. Do not read a fixed runner script and do not mention internal MCP tool names. The purpose is to verify that the real endpoint chooses the advertised tool and that the existing UI/database shows the intended result.

## Minimum evidence

Use a unique temporary prefix so test data is easy to remove later. Demonstrate these effects in any natural wording and order:

1. create a normal note;
2. create a todo note and verify the `待办` category;
3. append content without losing title/tags;
4. rename a note without losing content/tags;
5. convert normal to todo or todo to normal;
6. create a custom tag and bind it to one or more notes;
7. pin or unpin a small batch;
8. restore a previously soft-deleted test note;
9. request replace-content, delete, tag deletion, or replace-binding and verify Gate 5.2 does **not** write before confirmation support exists.

## What to record

Record only safe evidence:

- tool name and lifecycle status;
- affected note IDs and tag names;
- before/after UI category and selection;
- database-visible fields needed to prove the operation;
- whether a high-risk request left the database/catalog unchanged;
- terminal task/queue counters after disconnect.

Do not paste tokens, complete identity values, raw MCP payloads, or private note content into reports.

## Acceptance rule

Gate 5.2 can be marked accepted when automated/Fake/local integration passes and the real UI demonstrates the immediate mutations above using genuine user language. High-risk operations must stop at `requires_confirmation`; their execution is a Gate 5.3 acceptance item.

"""Frozen 31-tool Gate 5 descriptor catalog."""

from __future__ import annotations

from .contracts import ConfirmationPolicy, JsonValue, ToolDescriptor, ToolRisk
from .intent_rules import intent_description


def _object_schema(
    properties: dict[str, JsonValue] | None = None,
    *,
    required: tuple[str, ...] = (),
    additional_properties: bool = False,
    one_of_required: tuple[tuple[str, ...], ...] = (),
) -> dict[str, JsonValue]:
    schema: dict[str, JsonValue] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": additional_properties,
    }
    if required:
        schema["required"] = list(required)
    if one_of_required:
        schema["oneOf"] = [{"required": list(names)} for names in one_of_required]
    return schema


def _string(*, min_length: int = 0, max_length: int = 4096, enum=()) -> dict[str, JsonValue]:
    schema: dict[str, JsonValue] = {"type": "string", "maxLength": max_length}
    if min_length:
        schema["minLength"] = min_length
    if enum:
        schema["enum"] = list(enum)
    return schema


def _integer(*, minimum: int = 1, maximum: int = 2_147_483_647) -> dict[str, JsonValue]:
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def _boolean() -> dict[str, JsonValue]:
    return {"type": "boolean"}


def _array(
    items: dict[str, JsonValue], *, min_items: int = 0, max_items: int = 100
) -> dict[str, JsonValue]:
    schema: dict[str, JsonValue] = {
        "type": "array",
        "items": items,
        "maxItems": max_items,
        "uniqueItems": True,
    }
    if min_items:
        schema["minItems"] = min_items
    return schema


NOTE_ID = _integer()
NOTE_IDS = _array(NOTE_ID, min_items=1, max_items=50)
TAG = _string(min_length=1, max_length=64)
TAGS = _array(TAG, max_items=20)
NONEMPTY_TAGS = _array(TAG, min_items=1, max_items=20)
LIMIT_5 = _integer(minimum=1, maximum=5)
LIMIT_10 = _integer(minimum=1, maximum=10)
LIMIT_20 = _integer(minimum=1, maximum=20)


def _descriptor(
    name: str,
    description: str,
    schema: dict[str, JsonValue],
    risk: ToolRisk,
    *,
    mutates: bool = False,
    confirmation: ConfirmationPolicy = ConfirmationPolicy.NEVER,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        description=intent_description(name, description),
        input_schema=schema,
        risk=risk,
        mutates=mutates,
        confirmation=confirmation,
    )


GATE5_TOOL_DESCRIPTORS: tuple[ToolDescriptor, ...] = (
    _descriptor(
        "notes.resolve",
        "Resolve a note target without choosing an ambiguous candidate.",
        _object_schema(
            {
                "query": _string(min_length=1, max_length=200),
                "exact_title": _string(min_length=1, max_length=200),
                "scope": _string(enum=("active", "deleted", "all"), max_length=16),
                "limit": LIMIT_5,
            },
            one_of_required=(("query",), ("exact_title",)),
        ),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.search",
        "Search active notes with bounded snippets.",
        _object_schema(
            {
                "query": _string(min_length=1, max_length=500),
                "tags": TAGS,
                "scope": _string(enum=("active", "deleted", "all"), max_length=16),
                "limit": LIMIT_10,
            },
            required=("query",),
        ),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.list_recent",
        "List recently updated active notes.",
        _object_schema({"limit": LIMIT_20}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.get",
        "Get one note by id.",
        _object_schema({"note_id": NOTE_ID, "include_deleted": _boolean()}, required=("note_id",)),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.list_by_tag",
        "List active notes matching an exact tag.",
        _object_schema({"tag": TAG, "limit": LIMIT_20}, required=("tag",)),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.list_deleted",
        "List soft-deleted notes.",
        _object_schema({"limit": LIMIT_20}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.list_todos",
        "List active notes carrying the protected todo tag.",
        _object_schema({"limit": LIMIT_20}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.list_pinned",
        "List active pinned notes.",
        _object_schema({"limit": LIMIT_20}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "notes.create",
        "Create a normal or todo note.",
        _object_schema(
            {
                "title": _string(min_length=1, max_length=200),
                "content": _string(max_length=20_000),
                "type": _string(enum=("normal", "todo"), max_length=16),
                "tags": TAGS,
                "pinned": _boolean(),
                "open_after_create": _boolean(),
            },
            required=("title",),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
    ),
    _descriptor(
        "notes.append",
        "Append content while preserving title and tags.",
        _object_schema(
            {
                "note_id": NOTE_ID,
                "content": _string(min_length=1, max_length=20_000),
                "separator": _string(enum=("newline", "space", "none"), max_length=16),
            },
            required=("note_id", "content"),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
    ),
    _descriptor(
        "notes.update_title",
        "Update a note title while preserving other fields.",
        _object_schema(
            {"note_id": NOTE_ID, "title": _string(min_length=1, max_length=200)},
            required=("note_id", "title"),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
    ),
    _descriptor(
        "notes.replace_content",
        "Replace note content after explicit confirmation.",
        _object_schema(
            {
                "note_id": NOTE_ID,
                "content": _string(max_length=20_000),
                "expected_updated_at": _string(min_length=1, max_length=64),
            },
            required=("note_id", "content"),
        ),
        ToolRisk.HIGH,
        mutates=True,
        confirmation=ConfirmationPolicy.ALWAYS,
    ),
    _descriptor(
        "notes.convert_type",
        "Convert between normal and todo note semantics.",
        _object_schema(
            {
                "note_id": NOTE_ID,
                "target_type": _string(enum=("normal", "todo"), max_length=16),
            },
            required=("note_id", "target_type"),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
    ),
    _descriptor(
        "notes.pin",
        "Pin or unpin notes; large batches require confirmation.",
        _object_schema(
            {"note_ids": NOTE_IDS, "pinned": _boolean()},
            required=("note_ids", "pinned"),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
        confirmation=ConfirmationPolicy.CONDITIONAL,
    ),
    _descriptor(
        "notes.delete",
        "Soft-delete notes after explicit confirmation.",
        _object_schema({"note_ids": NOTE_IDS}, required=("note_ids",)),
        ToolRisk.HIGH,
        mutates=True,
        confirmation=ConfirmationPolicy.ALWAYS,
    ),
    _descriptor(
        "notes.restore",
        "Restore soft-deleted notes; large batches require confirmation.",
        _object_schema({"note_ids": NOTE_IDS}, required=("note_ids",)),
        ToolRisk.MEDIUM,
        mutates=True,
        confirmation=ConfirmationPolicy.CONDITIONAL,
    ),
    _descriptor(
        "tags.create",
        "Create a custom tag.",
        _object_schema({"name": TAG}, required=("name",)),
        ToolRisk.MEDIUM,
        mutates=True,
    ),
    _descriptor(
        "tags.search",
        "Search known tags.",
        _object_schema(
            {"query": _string(min_length=1, max_length=64), "limit": LIMIT_10},
            required=("query",),
        ),
        ToolRisk.LOW,
    ),
    _descriptor(
        "tags.list",
        "List known tags and usage metadata.",
        _object_schema({"include_usage": _boolean()}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "tags.delete",
        "Delete an eligible custom tag after confirmation.",
        _object_schema({"name": TAG}, required=("name",)),
        ToolRisk.HIGH,
        mutates=True,
        confirmation=ConfirmationPolicy.ALWAYS,
    ),
    _descriptor(
        "tags.bind",
        "Atomically add, remove, or replace note tags.",
        _object_schema(
            {
                "note_ids": NOTE_IDS,
                "operation": _string(enum=("add", "remove", "replace"), max_length=16),
                "tags": NONEMPTY_TAGS,
            },
            required=("note_ids", "operation", "tags"),
        ),
        ToolRisk.MEDIUM,
        mutates=True,
        confirmation=ConfirmationPolicy.CONDITIONAL,
    ),
    _descriptor(
        "ui.open_note",
        "Open a specific note in the desktop UI.",
        _object_schema({"note_id": NOTE_ID}, required=("note_id",)),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_search",
        "Open and focus search with an optional query.",
        _object_schema({"query": _string(max_length=500)}),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_note_list",
        "Show the active note list.",
        _object_schema(),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_tag",
        "Show an exact tag category.",
        _object_schema({"tag": TAG}, required=("tag",)),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_trash",
        "Show the deleted-note view.",
        _object_schema(),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_pinned",
        "Show the pinned-note view.",
        _object_schema(),
        ToolRisk.LOW,
    ),
    _descriptor(
        "ui.show_confirmation",
        "Display an existing pending confirmation.",
        _object_schema(
            {"confirmation_id": _string(min_length=1, max_length=128)},
            required=("confirmation_id",),
        ),
        ToolRisk.LOW,
    ),
    _descriptor(
        "assistant.confirm",
        "Consume and execute one valid pending confirmation.",
        _object_schema(
            {"confirmation_id": _string(min_length=1, max_length=128)},
            required=("confirmation_id",),
        ),
        ToolRisk.HIGH_GATEWAY,
        mutates=True,
        confirmation=ConfirmationPolicy.PENDING_ID,
    ),
    _descriptor(
        "assistant.reject",
        "Reject and consume one pending confirmation.",
        _object_schema(
            {"confirmation_id": _string(min_length=1, max_length=128)},
            required=("confirmation_id",),
        ),
        ToolRisk.LOW,
    ),
    _descriptor(
        "assistant.list_pending_confirmations",
        "List safe summaries for pending confirmations in the current session.",
        _object_schema(),
        ToolRisk.LOW,
    ),
)

FROZEN_GATE5_TOOL_NAMES = tuple(descriptor.name for descriptor in GATE5_TOOL_DESCRIPTORS)
UNSUPPORTED_ANDROID_TOOL_NAMES = frozenset(
    {
        "notes.list_archived",
        "notes.list_done",
        "notes.toggle_done",
        "notes.archive",
        "notes.restore_revision",
        "notes.clear_done",
        "tags.rename",
        "ui.show_archive",
    }
)

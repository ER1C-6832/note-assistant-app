from __future__ import annotations

import pytest

from app.assistant.mcp import (
    FROZEN_GATE5_TOOL_NAMES,
    GATE5_TOOL_DESCRIPTORS,
    UNSUPPORTED_ANDROID_TOOL_NAMES,
    ConfirmationPolicy,
    ToolRegistry,
)
from app.assistant.mcp.validation import SchemaValidationError, validate_arguments

EXPECTED_NAMES = {
    "notes.resolve",
    "notes.search",
    "notes.list_recent",
    "notes.get",
    "notes.list_by_tag",
    "notes.list_deleted",
    "notes.list_todos",
    "notes.list_pinned",
    "notes.create",
    "notes.append",
    "notes.update_title",
    "notes.replace_content",
    "notes.convert_type",
    "notes.pin",
    "notes.delete",
    "notes.restore",
    "tags.create",
    "tags.search",
    "tags.list",
    "tags.delete",
    "tags.bind",
    "ui.open_note",
    "ui.show_search",
    "ui.show_note_list",
    "ui.show_tag",
    "ui.show_trash",
    "ui.show_pinned",
    "ui.show_confirmation",
    "assistant.confirm",
    "assistant.reject",
    "assistant.list_pending_confirmations",
}


def test_registry_freezes_exactly_31_supported_tools() -> None:
    registry = ToolRegistry()
    assert len(registry.names) == 31
    assert set(registry.names) == EXPECTED_NAMES
    assert set(FROZEN_GATE5_TOOL_NAMES) == EXPECTED_NAMES
    assert len(set(FROZEN_GATE5_TOOL_NAMES)) == 31
    assert set(registry.names).isdisjoint(UNSUPPORTED_ANDROID_TOOL_NAMES)


def test_every_descriptor_has_public_schema_and_risk_metadata() -> None:
    assert len(GATE5_TOOL_DESCRIPTORS) == 31
    for descriptor in GATE5_TOOL_DESCRIPTORS:
        public = descriptor.public_dict()
        assert public["name"] == descriptor.name
        assert isinstance(public["description"], str) and public["description"]
        assert public["inputSchema"]["type"] == "object"
        assert public["inputSchema"]["additionalProperties"] is False
        assert public["risk"] in {"low", "medium", "high", "high_gateway"}
        assert isinstance(public["mutates"], bool)
        assert public["confirmation"] in {policy.value for policy in ConfirmationPolicy}


def test_high_risk_tools_do_not_claim_unconfirmed_execution() -> None:
    registry = ToolRegistry()
    for name in ("notes.replace_content", "notes.delete", "tags.delete"):
        descriptor = registry.get(name)
        assert descriptor is not None
        assert descriptor.mutates is True
        assert descriptor.confirmation is ConfirmationPolicy.ALWAYS
    confirm = registry.get("assistant.confirm")
    assert confirm is not None
    assert confirm.confirmation is ConfirmationPolicy.PENDING_ID


def test_schema_validator_rejects_unknown_invalid_and_duplicate_values() -> None:
    create = ToolRegistry().get("notes.create")
    assert create is not None
    validate_arguments({"title": "测试", "tags": ["客户"]}, create.input_schema)
    with pytest.raises(SchemaValidationError):
        validate_arguments({}, create.input_schema)
    with pytest.raises(SchemaValidationError):
        validate_arguments({"title": "x", "unknown": True}, create.input_schema)
    bind = ToolRegistry().get("tags.bind")
    assert bind is not None
    with pytest.raises(SchemaValidationError):
        validate_arguments(
            {"note_ids": [1, 1], "operation": "add", "tags": ["a"]},
            bind.input_schema,
        )

    resolve = ToolRegistry().get("notes.resolve")
    assert resolve is not None
    validate_arguments({"query": "最近"}, resolve.input_schema)
    with pytest.raises(SchemaValidationError):
        validate_arguments({}, resolve.input_schema)
    with pytest.raises(SchemaValidationError):
        validate_arguments({"query": "最近", "exact_title": "最近"}, resolve.input_schema)

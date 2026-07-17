"""Gate 5.2 note and tag mutation executor."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

from ...notes import (
    BatchUpdateTagsCommand,
    CreateNoteCommand,
    Note,
    NoteCommandService,
    NoteQueryService,
    NoteServiceError,
    NoteSource,
    RestoreCommand,
    SetPinnedCommand,
    TagCatalogError,
    TagCatalogService,
    TagInUseError,
    TagValidationError,
    UpdateNoteCommand,
)
from .contracts import (
    JsonValue,
    ToolCall,
    ToolDescriptor,
    ToolExecutor,
    ToolResult,
    ToolRisk,
)
from .gate5_1_executor import Gate51ToolExecutor
from .registry import GateNotReadyExecutor
from .ui_bus import UiCommand, UiCommandBus, UiCommandKind

NOTE_MUTATION_TOOL_NAMES = frozenset(
    {
        "notes.create",
        "notes.append",
        "notes.update_title",
        "notes.replace_content",
        "notes.convert_type",
        "notes.pin",
        "notes.delete",
        "notes.restore",
    }
)
TAG_TOOL_NAMES = frozenset(
    {
        "tags.create",
        "tags.search",
        "tags.list",
        "tags.delete",
        "tags.bind",
    }
)

_TODO_TAG = "待办"
_CONFIRMATION_LIMIT = 5


class Gate52ToolExecutor(Gate51ToolExecutor):
    """Execute Gate 5.0 through 5.2 handlers and fail closed for Gate 5.3."""

    def __init__(
        self,
        query_service: NoteQueryService,
        command_service: NoteCommandService,
        tag_service: TagCatalogService,
        ui_bus: UiCommandBus,
        *,
        fallback: ToolExecutor | None = None,
    ) -> None:
        super().__init__(query_service, ui_bus, fallback=fallback or GateNotReadyExecutor())
        self._commands = command_service
        self._tags = tag_service

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        try:
            if call.tool_name in NOTE_MUTATION_TOOL_NAMES:
                return await self._execute_note_mutation(call, descriptor)
            if call.tool_name in TAG_TOOL_NAMES:
                return await self._execute_tag_tool(call, descriptor)
            return await super().execute(call, descriptor)
        except NoteServiceError as exc:
            return self._failure(
                call.tool_name,
                descriptor,
                "便签写入服务暂时不可用",
                exc.code,
            )
        except TagInUseError:
            return self._failure(
                call.tool_name,
                descriptor,
                "标签仍被便签使用，不能删除",
                "tag_in_use",
            )
        except TagValidationError:
            return self._failure(
                call.tool_name,
                descriptor,
                "标签名称不允许用于此操作",
                "invalid_tag",
            )
        except TagCatalogError:
            return self._failure(
                call.tool_name,
                descriptor,
                "标签目录暂时不可用",
                "tag_catalog_error",
            )
        except (TypeError, ValueError):
            return self._failure(
                call.tool_name,
                descriptor,
                "工具参数无法安全处理",
                "invalid_tool_arguments",
            )
        except Exception:
            return self._failure(
                call.tool_name,
                descriptor,
                "工具执行失败",
                "tool_execution_failed",
            )

    async def _execute_note_mutation(
        self, call: ToolCall, descriptor: ToolDescriptor
    ) -> ToolResult:
        name = call.tool_name
        args = call.arguments
        if name == "notes.create":
            return await self._create(args, descriptor)
        if name == "notes.append":
            return await self._append(args, descriptor)
        if name == "notes.update_title":
            return await self._update_title(args, descriptor)
        if name == "notes.replace_content":
            return await self._replace_preview(args, descriptor)
        if name == "notes.convert_type":
            return await self._convert_type(args, descriptor)
        if name == "notes.pin":
            return await self._pin(args, descriptor)
        if name == "notes.delete":
            return await self._delete_preview(args, descriptor)
        if name == "notes.restore":
            return await self._restore(args, descriptor)
        raise ValueError("unsupported Gate 5.2 note mutation")

    async def _execute_tag_tool(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        name = call.tool_name
        args = call.arguments
        if name == "tags.create":
            tag = str(args["name"]).strip()
            created = await self._tags.add_async(tag)
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_TAGS))
            status = "success" if refresh.accepted else "partial_success"
            return ToolResult(
                status=status,
                message="标签已创建" if created else "标签已存在",
                tool_name=name,
                risk=descriptor.risk,
                affected_tags=(tag,),
                result={"created": created, "ui_refreshed": refresh.accepted},
                error_code=None if refresh.accepted else "ui_refresh_failed",
            )
        if name == "tags.search":
            items = await self._tags.search_public(
                str(args["query"]), limit=int(args.get("limit", 10))
            )
            return ToolResult(
                status="success",
                message="标签搜索完成",
                tool_name=name,
                risk=descriptor.risk,
                affected_tags=tuple(str(item["name"]) for item in items),
                result={"count": len(items), "tags": list(items)},
            )
        if name == "tags.list":
            items = await self._tags.list_public(
                include_usage=bool(args.get("include_usage", True))
            )
            return ToolResult(
                status="success",
                message="标签列表已返回",
                tool_name=name,
                risk=descriptor.risk,
                affected_tags=tuple(str(item["name"]) for item in items),
                result={"count": len(items), "tags": list(items)},
            )
        if name == "tags.delete":
            inspection = await self._tags.inspect_delete(str(args["name"]))
            if not inspection.exists:
                return self._failure(name, descriptor, "标签不存在", "tag_not_found")
            if inspection.protected or inspection.system:
                return self._failure(name, descriptor, "受保护或系统标签不能删除", "tag_protected")
            if inspection.in_use:
                return self._failure(name, descriptor, "标签仍被便签使用，不能删除", "tag_in_use")
            return self._confirmation(
                name,
                descriptor,
                message="删除标签需要确认",
                affected_tags=(inspection.name,),
                preview={"operation": "delete_tag", "tag_count": 1},
            )
        if name == "tags.bind":
            return await self._bind_tags(args, descriptor)
        raise ValueError("unsupported Gate 5.2 tag tool")

    async def _create(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note_type = str(args.get("type", "normal"))
        tags = list(_strings(args.get("tags", ())))
        if note_type == "todo" and _TODO_TAG not in tags:
            tags.append(_TODO_TAG)
        command = CreateNoteCommand(
            title=str(args["title"]),
            content=str(args.get("content", "")),
            tags=tuple(tags),
            is_pinned=bool(args.get("pinned", False)),
            source=NoteSource.VOICE_PC,
        )
        note = await self._commands.create(command)
        await self._tags.observe_async(note.tags)
        open_after = bool(args.get("open_after_create", False))
        refresh = await self._ui_bus.dispatch(
            UiCommand(
                (UiCommandKind.OPEN_NOTE if open_after else UiCommandKind.REFRESH_CURRENT),
                {"note_id": note.id} if open_after else {},
            )
        )
        return self._committed_note(
            "notes.create",
            descriptor,
            "便签已创建",
            note,
            refresh.accepted,
            {"note_id": note.id, "source": note.source.value},
        )

    async def _append(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note = await self._require_active(int(args["note_id"]), descriptor, "notes.append")
        if isinstance(note, ToolResult):
            return note
        separator = {"newline": "\n", "space": " ", "none": ""}.get(
            str(args.get("separator", "newline")), "\n"
        )
        suffix = str(args["content"])
        content = f"{note.content}{separator if note.content else ''}{suffix}"
        updated = await self._commands.update(
            UpdateNoteCommand(note.id, note.title, content, note.tags)
        )
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return self._committed_note(
            "notes.append",
            descriptor,
            "内容已追加",
            updated,
            refresh.accepted,
            {"note_id": updated.id},
        )

    async def _update_title(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note = await self._require_active(int(args["note_id"]), descriptor, "notes.update_title")
        if isinstance(note, ToolResult):
            return note
        updated = await self._commands.update(
            UpdateNoteCommand(note.id, str(args["title"]), note.content, note.tags)
        )
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return self._committed_note(
            "notes.update_title",
            descriptor,
            "标题已更新",
            updated,
            refresh.accepted,
            {"note_id": updated.id},
        )

    async def _replace_preview(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note = await self._require_active(int(args["note_id"]), descriptor, "notes.replace_content")
        if isinstance(note, ToolResult):
            return note
        expected = str(args.get("expected_updated_at", "")).strip()
        if expected and not _timestamp_matches(note, expected):
            return self._failure(
                "notes.replace_content",
                descriptor,
                "便签已发生变化，请重新读取后再操作",
                "stale_note_version",
                affected_note_ids=(note.id,),
            )
        return self._confirmation(
            "notes.replace_content",
            descriptor,
            message="替换正文需要确认",
            affected_note_ids=(note.id,),
            preview={
                "operation": "replace_content",
                "note_count": 1,
                "expected_version_checked": bool(expected),
            },
        )

    async def _convert_type(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note = await self._require_active(int(args["note_id"]), descriptor, "notes.convert_type")
        if isinstance(note, ToolResult):
            return note
        target = str(args["target_type"])
        tags = [tag for tag in note.tags if tag != _TODO_TAG]
        if target == "todo":
            tags.append(_TODO_TAG)
        updated = await self._commands.update(
            UpdateNoteCommand(note.id, note.title, note.content, tuple(tags))
        )
        await self._tags.observe_async(updated.tags)
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return self._committed_note(
            "notes.convert_type",
            descriptor,
            "便签类型已转换",
            updated,
            refresh.accepted,
            {"note_id": updated.id, "type": target},
        )

    async def _pin(self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor) -> ToolResult:
        note_ids = _note_ids(args["note_ids"])
        validation = await self._validate_active_targets(note_ids, descriptor, "notes.pin")
        if validation is not None:
            return validation
        if len(note_ids) > _CONFIRMATION_LIMIT:
            return self._confirmation(
                "notes.pin",
                descriptor,
                message="批量置顶状态变更需要确认",
                affected_note_ids=note_ids,
                preview={"operation": "pin", "note_count": len(note_ids)},
            )
        notes = await self._commands.set_pinned(SetPinnedCommand(note_ids, bool(args["pinned"])))
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return self._committed_many(
            "notes.pin",
            descriptor,
            "置顶状态已更新",
            notes,
            refresh.accepted,
            {"pinned": bool(args["pinned"])},
        )

    async def _delete_preview(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note_ids = _note_ids(args["note_ids"])
        validation = await self._validate_active_targets(note_ids, descriptor, "notes.delete")
        if validation is not None:
            return validation
        return self._confirmation(
            "notes.delete",
            descriptor,
            message="删除便签需要确认",
            affected_note_ids=note_ids,
            preview={"operation": "soft_delete", "note_count": len(note_ids)},
        )

    async def _restore(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note_ids = _note_ids(args["note_ids"])
        validation = await self._validate_deleted_targets(note_ids, descriptor, "notes.restore")
        if validation is not None:
            return validation
        if len(note_ids) > _CONFIRMATION_LIMIT:
            return self._confirmation(
                "notes.restore",
                descriptor,
                message="批量恢复需要确认",
                affected_note_ids=note_ids,
                preview={"operation": "restore", "note_count": len(note_ids)},
            )
        await self._commands.restore(RestoreCommand(note_ids))
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return ToolResult(
            status="success" if refresh.accepted else "partial_success",
            message="便签已恢复",
            tool_name="notes.restore",
            risk=descriptor.risk,
            affected_note_ids=note_ids,
            result={"restored_count": len(note_ids), "ui_refreshed": refresh.accepted},
            error_code=None if refresh.accepted else "ui_refresh_failed",
        )

    async def _bind_tags(
        self, args: Mapping[str, JsonValue], descriptor: ToolDescriptor
    ) -> ToolResult:
        note_ids = _note_ids(args["note_ids"])
        operation = str(args["operation"])
        tags = _strings(args["tags"])
        command = BatchUpdateTagsCommand(note_ids, operation, tags)
        validation = await self._validate_active_targets(note_ids, descriptor, "tags.bind")
        if validation is not None:
            return validation
        if operation == "replace" or len(note_ids) > _CONFIRMATION_LIMIT:
            return self._confirmation(
                "tags.bind",
                descriptor,
                message="该标签绑定操作需要确认",
                affected_note_ids=note_ids,
                affected_tags=tags,
                preview={
                    "operation": operation,
                    "note_count": len(note_ids),
                    "tag_count": len(tags),
                },
            )
        notes = await self._commands.update_tags(command)
        await self._tags.observe_async(tag for note in notes for tag in note.tags)
        refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
        return self._committed_many(
            "tags.bind",
            descriptor,
            "标签绑定已更新",
            notes,
            refresh.accepted,
            {"operation": operation},
            affected_tags=tags,
        )

    async def _require_active(
        self, note_id: int, descriptor: ToolDescriptor, tool_name: str
    ) -> Note | ToolResult:
        note = await self._queries.get(note_id)
        if note is None:
            return self._failure(
                tool_name,
                descriptor,
                "未找到活动便签",
                "note_not_found",
                affected_note_ids=(note_id,),
            )
        return note

    async def _validate_active_targets(
        self, note_ids: tuple[int, ...], descriptor: ToolDescriptor, tool_name: str
    ) -> ToolResult | None:
        missing: list[int] = []
        invalid: list[int] = []
        for note_id in note_ids:
            note = await self._queries.get(note_id, include_deleted=True)
            if note is None:
                missing.append(note_id)
            elif note.is_deleted:
                invalid.append(note_id)
        if missing:
            return self._failure(
                tool_name,
                descriptor,
                "部分便签不存在",
                "note_not_found",
                affected_note_ids=tuple(missing),
            )
        if invalid:
            return self._failure(
                tool_name,
                descriptor,
                "部分便签不在活动状态",
                "invalid_note_state",
                affected_note_ids=tuple(invalid),
            )
        return None

    async def _validate_deleted_targets(
        self, note_ids: tuple[int, ...], descriptor: ToolDescriptor, tool_name: str
    ) -> ToolResult | None:
        missing: list[int] = []
        invalid: list[int] = []
        for note_id in note_ids:
            note = await self._queries.get(note_id, include_deleted=True)
            if note is None:
                missing.append(note_id)
            elif not note.is_deleted:
                invalid.append(note_id)
        if missing:
            return self._failure(
                tool_name,
                descriptor,
                "部分便签不存在",
                "note_not_found",
                affected_note_ids=tuple(missing),
            )
        if invalid:
            return self._failure(
                tool_name,
                descriptor,
                "部分便签不在已删除状态",
                "invalid_note_state",
                affected_note_ids=tuple(invalid),
            )
        return None

    @staticmethod
    def _confirmation(
        tool_name: str,
        descriptor: ToolDescriptor,
        *,
        message: str,
        preview: Mapping[str, JsonValue],
        affected_note_ids: tuple[int, ...] = (),
        affected_tags: tuple[str, ...] = (),
    ) -> ToolResult:
        return ToolResult(
            status="requires_confirmation",
            message=message,
            tool_name=tool_name,
            risk=ToolRisk.HIGH,
            requires_confirmation=True,
            confirmation_id=None,
            affected_note_ids=affected_note_ids,
            affected_tags=affected_tags,
            result={"preview": dict(preview), "confirmation_available": False},
            error_code="confirmation_gate_not_ready",
        )

    @staticmethod
    def _failure(
        tool_name: str,
        descriptor: ToolDescriptor,
        message: str,
        error_code: str,
        *,
        affected_note_ids: tuple[int, ...] = (),
        affected_tags: tuple[str, ...] = (),
    ) -> ToolResult:
        return ToolResult(
            status="failed",
            message=message,
            tool_name=tool_name,
            risk=descriptor.risk,
            affected_note_ids=affected_note_ids,
            affected_tags=affected_tags,
            error_code=error_code,
        )

    @staticmethod
    def _committed_note(
        tool_name: str,
        descriptor: ToolDescriptor,
        message: str,
        note: Note,
        ui_refreshed: bool,
        result: Mapping[str, JsonValue],
    ) -> ToolResult:
        payload = dict(result)
        payload.update({"committed": True, "ui_refreshed": ui_refreshed})
        return ToolResult(
            status="success" if ui_refreshed else "partial_success",
            message=message,
            tool_name=tool_name,
            risk=descriptor.risk,
            affected_note_ids=(note.id,),
            affected_tags=note.tags,
            result=payload,
            error_code=None if ui_refreshed else "ui_refresh_failed",
        )

    @staticmethod
    def _committed_many(
        tool_name: str,
        descriptor: ToolDescriptor,
        message: str,
        notes: tuple[Note, ...],
        ui_refreshed: bool,
        result: Mapping[str, JsonValue],
        *,
        affected_tags: tuple[str, ...] = (),
    ) -> ToolResult:
        payload = dict(result)
        payload.update(
            {
                "committed": True,
                "updated_count": len(notes),
                "ui_refreshed": ui_refreshed,
            }
        )
        return ToolResult(
            status="success" if ui_refreshed else "partial_success",
            message=message,
            tool_name=tool_name,
            risk=descriptor.risk,
            affected_note_ids=tuple(note.id for note in notes),
            affected_tags=affected_tags,
            result=payload,
            error_code=None if ui_refreshed else "ui_refresh_failed",
        )


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        tag = str(item).strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return tuple(result)


def _note_ids(value: object) -> tuple[int, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        raise ValueError("note_ids must be an array")
    result: list[int] = []
    seen: set[int] = set()
    for item in value:
        if isinstance(item, bool):
            raise ValueError("note id must be an integer")
        note_id = int(item)
        if note_id <= 0:
            raise ValueError("note id must be positive")
        if note_id not in seen:
            seen.add(note_id)
            result.append(note_id)
    if not result:
        raise ValueError("note_ids must not be empty")
    return tuple(result)


def _timestamp_matches(note: Note, expected: str) -> bool:
    try:
        parsed = datetime.fromisoformat(expected.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return note.updated_at.astimezone(timezone.utc) == parsed.astimezone(timezone.utc)


__all__ = ["Gate52ToolExecutor", "NOTE_MUTATION_TOOL_NAMES", "TAG_TOOL_NAMES"]

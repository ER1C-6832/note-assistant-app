"""Gate 5.3 confirmation gateway and high-risk mutation closure."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import timezone

from ...notes import (
    BatchUpdateTagsCommand,
    Note,
    NoteCommandService,
    NoteQueryService,
    NoteServiceError,
    RestoreCommand,
    SetPinnedCommand,
    SoftDeleteCommand,
    TagCatalogError,
    TagCatalogService,
    TagInUseError,
    TagValidationError,
    UpdateNoteCommand,
)
from .confirmation import (
    ConfirmationResolution,
    PendingConfirmation,
    PendingConfirmationService,
)
from .contracts import JsonValue, ToolCall, ToolDescriptor, ToolResult, ToolRisk
from .descriptors import GATE5_TOOL_DESCRIPTORS
from .gate5_2_executor import Gate52ToolExecutor
from .ui_bus import UiCommand, UiCommandBus, UiCommandKind

CONFIRMATION_TOOL_NAMES = frozenset(
    {
        "assistant.confirm",
        "assistant.reject",
        "assistant.list_pending_confirmations",
    }
)
_CONFIRMATION_LIMIT = 5
_DESCRIPTOR_MAP = {descriptor.name: descriptor for descriptor in GATE5_TOOL_DESCRIPTORS}


class Gate53ToolExecutor(Gate52ToolExecutor):
    """Execute all Gate 5.0 through 5.3 tools with one confirmation service."""

    def __init__(
        self,
        query_service: NoteQueryService,
        command_service: NoteCommandService,
        tag_service: TagCatalogService,
        ui_bus: UiCommandBus,
        *,
        confirmation_service: PendingConfirmationService | None = None,
    ) -> None:
        super().__init__(query_service, command_service, tag_service, ui_bus)
        self._confirmations = confirmation_service or PendingConfirmationService()

    @property
    def confirmation_service(self) -> PendingConfirmationService:
        return self._confirmations

    @property
    def pending_confirmation_count(self) -> int:
        return self._confirmations.pending_count

    async def execute(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        try:
            if call.tool_name in CONFIRMATION_TOOL_NAMES:
                return await self._execute_confirmation_tool(call, descriptor)
            if call.tool_name == "ui.show_confirmation":
                return await self._show_confirmation(call, descriptor)
            if self._is_high_risk_request(call):
                return await self._prepare_high_risk(call, descriptor)
            return await super().execute(call, descriptor)
        except asyncio.CancelledError:
            raise
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
        except (TypeError, ValueError, KeyError):
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

    async def close_generation(self, generation: int, reason: str) -> None:
        await self._confirmations.invalidate_generation(generation, reason)

    async def close(self) -> None:
        await self._confirmations.close()

    async def confirm_local(self, confirmation_id: str) -> ToolResult:
        resolution = await self._confirmations.confirm(
            confirmation_id,
            connection_generation=0,
            session_id=None,
            executor=self._execute_pending,
            trusted_local=True,
        )
        return self._confirm_resolution_result(
            resolution,
            confirmation_id=confirmation_id,
            tool_name="assistant.confirm",
        )

    async def reject_local(self, confirmation_id: str) -> ToolResult:
        resolution = await self._confirmations.reject(
            confirmation_id,
            connection_generation=0,
            session_id=None,
            trusted_local=True,
        )
        return self._reject_resolution_result(
            resolution,
            confirmation_id=confirmation_id,
        )

    def _is_high_risk_request(self, call: ToolCall) -> bool:
        name = call.tool_name
        args = call.arguments
        if name in {"notes.replace_content", "notes.delete", "tags.delete"}:
            return True
        if name in {"notes.pin", "notes.restore"}:
            return len(_note_ids(args.get("note_ids"))) > _CONFIRMATION_LIMIT
        if name == "tags.bind":
            operation = str(args.get("operation", ""))
            return (
                operation == "replace" or len(_note_ids(args.get("note_ids"))) > _CONFIRMATION_LIMIT
            )
        return False

    async def _prepare_high_risk(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        name = call.tool_name
        args = call.arguments
        note_ids: tuple[int, ...] = ()
        tags: tuple[str, ...] = ()
        target_versions: dict[int, str] = {}
        preview: dict[str, JsonValue]
        message: str

        if name == "notes.replace_content":
            note_id = int(args["note_id"])
            note = await self._require_active(note_id, descriptor, name)
            if isinstance(note, ToolResult):
                return note
            expected = str(args.get("expected_updated_at", "")).strip()
            if expected and not _timestamp_matches(note, expected):
                return self._failure(
                    name,
                    descriptor,
                    "便签已发生变化，请重新读取后再操作",
                    "stale_note_version",
                    affected_note_ids=(note.id,),
                )
            note_ids = (note.id,)
            target_versions = {note.id: _note_version(note)}
            preview = {
                "operation": "replace_content",
                "note_count": 1,
                "expected_version_checked": bool(expected),
            }
            message = "替换正文需要确认"
        elif name == "notes.delete":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            target_versions = await self._capture_versions(note_ids)
            preview = {"operation": "soft_delete", "note_count": len(note_ids)}
            message = "删除便签需要确认"
        elif name == "notes.pin":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            target_versions = await self._capture_versions(note_ids)
            preview = {
                "operation": "pin",
                "note_count": len(note_ids),
                "pinned": bool(args["pinned"]),
            }
            message = "批量置顶状态变更需要确认"
        elif name == "notes.restore":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_deleted_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            target_versions = await self._capture_versions(note_ids)
            preview = {"operation": "restore", "note_count": len(note_ids)}
            message = "批量恢复需要确认"
        elif name == "tags.bind":
            note_ids = _note_ids(args["note_ids"])
            operation = str(args["operation"])
            tags = _strings(args["tags"])
            BatchUpdateTagsCommand(note_ids, operation, tags)
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            target_versions = await self._capture_versions(note_ids)
            preview = {
                "operation": operation,
                "note_count": len(note_ids),
                "tag_count": len(tags),
            }
            message = "该标签绑定操作需要确认"
        elif name == "tags.delete":
            inspection = await self._tags.inspect_delete(str(args["name"]))
            if not inspection.exists:
                return self._failure(name, descriptor, "标签不存在", "tag_not_found")
            if inspection.protected or inspection.system:
                return self._failure(name, descriptor, "受保护或系统标签不能删除", "tag_protected")
            if inspection.in_use:
                return self._failure(name, descriptor, "标签仍被便签使用，不能删除", "tag_in_use")
            tags = (inspection.name,)
            preview = {"operation": "delete_tag", "tag_count": 1}
            message = "删除标签需要确认"
        else:
            raise ValueError("unsupported high-risk tool")

        if call.connection_generation <= 0 or not (call.session_id or "").strip():
            return self._confirmation(
                name,
                descriptor,
                message=message,
                preview=preview,
                affected_note_ids=note_ids,
                affected_tags=tags,
            )

        pending = await self._confirmations.create(
            connection_generation=call.connection_generation,
            session_id=call.session_id or "",
            tool_name=name,
            risk=ToolRisk.HIGH,
            arguments=args,
            preview=preview,
            affected_note_ids=note_ids,
            affected_tags=tags,
            target_versions=target_versions,
        )
        if pending is None:
            return ToolResult(
                status="blocked",
                message="待确认操作数量已达上限或确认服务不可用",
                tool_name=name,
                risk=ToolRisk.HIGH,
                affected_note_ids=note_ids,
                affected_tags=tags,
                error_code="confirmation_capacity_or_closed",
            )
        public = self._confirmations.public_view(pending)
        return ToolResult(
            status="requires_confirmation",
            message=message,
            tool_name=name,
            risk=ToolRisk.HIGH,
            requires_confirmation=True,
            confirmation_id=pending.confirmation_id,
            affected_note_ids=note_ids,
            affected_tags=tags,
            result={
                "preview": preview,
                "confirmation_available": True,
                "expires_at": public["expires_at"],
                "seconds_remaining": public["seconds_remaining"],
            },
        )

    async def _execute_confirmation_tool(
        self, call: ToolCall, descriptor: ToolDescriptor
    ) -> ToolResult:
        if call.connection_generation <= 0 or not (call.session_id or "").strip():
            return ToolResult(
                status="blocked",
                message="确认工具必须来自有效的 MCP 会话",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                error_code="confirmation_context_required",
            )
        if call.tool_name == "assistant.list_pending_confirmations":
            items = await self._confirmations.list_for_context(
                connection_generation=call.connection_generation,
                session_id=call.session_id,
            )
            return ToolResult(
                status="success",
                message="待确认操作已返回",
                tool_name=call.tool_name,
                risk=descriptor.risk,
                result={"count": len(items), "confirmations": list(items)},
            )
        confirmation_id = str(call.arguments["confirmation_id"])
        if call.tool_name == "assistant.reject":
            resolution = await self._confirmations.reject(
                confirmation_id,
                connection_generation=call.connection_generation,
                session_id=call.session_id,
            )
            return self._reject_resolution_result(
                resolution,
                confirmation_id=confirmation_id,
            )
        resolution = await self._confirmations.confirm(
            confirmation_id,
            connection_generation=call.connection_generation,
            session_id=call.session_id,
            executor=self._execute_pending,
        )
        return self._confirm_resolution_result(
            resolution,
            confirmation_id=confirmation_id,
            tool_name=call.tool_name,
        )

    async def _show_confirmation(self, call: ToolCall, descriptor: ToolDescriptor) -> ToolResult:
        resolution = await self._confirmations.get(
            str(call.arguments["confirmation_id"]),
            connection_generation=call.connection_generation,
            session_id=call.session_id,
        )
        if resolution.status != "pending" or resolution.pending is None:
            return ToolResult(
                status="blocked",
                message=resolution.message,
                tool_name=call.tool_name,
                risk=descriptor.risk,
                error_code=resolution.error_code or "confirmation_not_available",
            )
        payload = self._confirmations.public_view(resolution.pending)
        dispatched = await self._ui_bus.dispatch(
            UiCommand(UiCommandKind.SHOW_CONFIRMATION, payload)
        )
        return ToolResult(
            status="success" if dispatched.accepted else "blocked",
            message=("确认窗口已显示" if dispatched.accepted else dispatched.message),
            tool_name=call.tool_name,
            risk=descriptor.risk,
            affected_note_ids=resolution.pending.affected_note_ids,
            affected_tags=resolution.pending.affected_tags,
            result={"displayed": dispatched.accepted},
            error_code=None if dispatched.accepted else dispatched.error_code,
        )

    async def _execute_pending(self, pending: PendingConfirmation) -> ToolResult:
        args = pending.arguments()
        expected_fingerprint = hashlib.sha256(
            f"{pending.tool_name}\n{_canonical_json(args)}".encode("utf-8")
        ).hexdigest()
        if expected_fingerprint != pending.argument_fingerprint:
            return _operation_failure(
                pending.tool_name,
                "确认请求参数已损坏",
                "confirmation_fingerprint_mismatch",
                pending,
            )
        stale = await self._validate_snapshot(pending)
        if stale is not None:
            return stale

        descriptor = _DESCRIPTOR_MAP[pending.tool_name]
        name = pending.tool_name
        if name == "notes.replace_content":
            note = await self._queries.get(int(args["note_id"]))
            if note is None:
                return _operation_failure(
                    name, "便签已不存在", "stale_confirmation_target", pending
                )
            updated = await self._commands.update(
                UpdateNoteCommand(note.id, note.title, str(args["content"]), note.tags)
            )
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
            return self._committed_note(
                name,
                descriptor,
                "正文已替换",
                updated,
                refresh.accepted,
                {"note_id": updated.id},
            )
        if name == "notes.delete":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            count = await self._commands.soft_delete(SoftDeleteCommand(note_ids))
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
            return ToolResult(
                status="success" if refresh.accepted else "partial_success",
                message="便签已移入已删除",
                tool_name=name,
                risk=ToolRisk.HIGH,
                affected_note_ids=note_ids,
                result={
                    "committed": True,
                    "deleted_count": count,
                    "ui_refreshed": refresh.accepted,
                },
                error_code=None if refresh.accepted else "ui_refresh_failed",
            )
        if name == "notes.pin":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            notes = await self._commands.set_pinned(
                SetPinnedCommand(note_ids, bool(args["pinned"]))
            )
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
            return self._committed_many(
                name,
                descriptor,
                "置顶状态已更新",
                notes,
                refresh.accepted,
                {"pinned": bool(args["pinned"])},
            )
        if name == "notes.restore":
            note_ids = _note_ids(args["note_ids"])
            validation = await self._validate_deleted_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            count = await self._commands.restore(RestoreCommand(note_ids))
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
            return ToolResult(
                status="success" if refresh.accepted else "partial_success",
                message="便签已恢复",
                tool_name=name,
                risk=ToolRisk.HIGH,
                affected_note_ids=note_ids,
                result={
                    "committed": True,
                    "restored_count": count,
                    "ui_refreshed": refresh.accepted,
                },
                error_code=None if refresh.accepted else "ui_refresh_failed",
            )
        if name == "tags.bind":
            note_ids = _note_ids(args["note_ids"])
            tags = _strings(args["tags"])
            command = BatchUpdateTagsCommand(note_ids, str(args["operation"]), tags)
            validation = await self._validate_active_targets(note_ids, descriptor, name)
            if validation is not None:
                return validation
            notes = await self._commands.update_tags(command)
            await self._tags.observe_async(tag for note in notes for tag in note.tags)
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_CURRENT))
            return self._committed_many(
                name,
                descriptor,
                "标签绑定已更新",
                notes,
                refresh.accepted,
                {"operation": command.operation},
                affected_tags=tags,
            )
        if name == "tags.delete":
            tag = str(args["name"]).strip()
            inspection = await self._tags.inspect_delete(tag)
            if not inspection.deletable:
                return _operation_failure(
                    name,
                    "标签当前不能删除",
                    "stale_confirmation_target",
                    pending,
                )
            deleted = await self._tags.delete_async(tag)
            refresh = await self._ui_bus.dispatch(UiCommand(UiCommandKind.REFRESH_TAGS))
            return ToolResult(
                status="success" if refresh.accepted else "partial_success",
                message="标签已删除" if deleted else "标签不存在",
                tool_name=name,
                risk=ToolRisk.HIGH,
                affected_tags=(tag,),
                result={
                    "committed": deleted,
                    "deleted": deleted,
                    "ui_refreshed": refresh.accepted,
                },
                error_code=None if refresh.accepted else "ui_refresh_failed",
            )
        return _operation_failure(
            name, "确认请求不支持执行", "confirmation_tool_not_supported", pending
        )

    async def _capture_versions(self, note_ids: tuple[int, ...]) -> dict[int, str]:
        result: dict[int, str] = {}
        for note_id in note_ids:
            note = await self._queries.get(note_id, include_deleted=True)
            if note is None:
                raise ValueError("target note disappeared")
            result[note_id] = _note_version(note)
        return result

    async def _validate_snapshot(self, pending: PendingConfirmation) -> ToolResult | None:
        for note_id, expected in pending.target_versions.items():
            note = await self._queries.get(note_id, include_deleted=True)
            if note is None or _note_version(note) != expected:
                return _operation_failure(
                    pending.tool_name,
                    "目标便签已发生变化，请重新发起操作",
                    "stale_confirmation_target",
                    pending,
                )
        return None

    @staticmethod
    def _confirm_resolution_result(
        resolution: ConfirmationResolution,
        *,
        confirmation_id: str,
        tool_name: str,
    ) -> ToolResult:
        if resolution.status == "confirmed" and resolution.tool_result is not None:
            operation = resolution.tool_result
            result = dict(operation.result)
            result.update(
                {
                    "confirmation_id": confirmation_id,
                    "confirmed_tool": (
                        resolution.pending.tool_name if resolution.pending else None
                    ),
                    "terminal_state": resolution.terminal_state,
                }
            )
            return ToolResult(
                status=operation.status,
                message=operation.message,
                tool_name=tool_name,
                risk=ToolRisk.HIGH_GATEWAY,
                affected_note_ids=operation.affected_note_ids,
                affected_tags=operation.affected_tags,
                result=result,
                error_code=operation.error_code,
            )
        if resolution.tool_result is not None:
            operation = resolution.tool_result
            return ToolResult(
                status="failed",
                message=operation.message,
                tool_name=tool_name,
                risk=ToolRisk.HIGH_GATEWAY,
                affected_note_ids=operation.affected_note_ids,
                affected_tags=operation.affected_tags,
                result={
                    "confirmation_id": confirmation_id,
                    "terminal_state": resolution.terminal_state,
                },
                error_code=operation.error_code or "confirmation_execution_failed",
            )
        return ToolResult(
            status="blocked" if resolution.status != "execution_failed" else "failed",
            message=resolution.message,
            tool_name=tool_name,
            risk=ToolRisk.HIGH_GATEWAY,
            result={
                "confirmation_id": confirmation_id,
                "terminal_state": resolution.terminal_state,
            },
            error_code=resolution.error_code or "confirmation_not_available",
        )

    @staticmethod
    def _reject_resolution_result(
        resolution: ConfirmationResolution,
        *,
        confirmation_id: str,
    ) -> ToolResult:
        if resolution.status == "rejected" and resolution.pending is not None:
            return ToolResult(
                status="success",
                message="已拒绝该操作",
                tool_name="assistant.reject",
                risk=ToolRisk.LOW,
                affected_note_ids=resolution.pending.affected_note_ids,
                affected_tags=resolution.pending.affected_tags,
                result={
                    "confirmation_id": confirmation_id,
                    "rejected_tool": resolution.pending.tool_name,
                    "terminal_state": "rejected",
                },
            )
        return ToolResult(
            status="blocked",
            message=resolution.message,
            tool_name="assistant.reject",
            risk=ToolRisk.LOW,
            result={
                "confirmation_id": confirmation_id,
                "terminal_state": resolution.terminal_state,
            },
            error_code=resolution.error_code or "confirmation_not_available",
        )


def _operation_failure(
    tool_name: str,
    message: str,
    error_code: str,
    pending: PendingConfirmation,
) -> ToolResult:
    return ToolResult(
        status="failed",
        message=message,
        tool_name=tool_name,
        risk=ToolRisk.HIGH,
        affected_note_ids=pending.affected_note_ids,
        affected_tags=pending.affected_tags,
        error_code=error_code,
    )


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


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Iterable):
        raise ValueError("tags must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean = str(item).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    if not result:
        raise ValueError("tags must not be empty")
    return tuple(result)


def _note_version(note: Note) -> str:
    return note.updated_at.astimezone(timezone.utc).isoformat()


def _timestamp_matches(note: Note, expected: str) -> bool:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(expected.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    return note.updated_at.astimezone(timezone.utc) == parsed.astimezone(timezone.utc)


def _canonical_json(value: Mapping[str, JsonValue]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = ["CONFIRMATION_TOOL_NAMES", "Gate53ToolExecutor"]

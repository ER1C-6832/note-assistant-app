from __future__ import annotations

import json
from typing import Any

from src.mcp.decorators import Prop, PropType, mcp_tool

from .notes_api_client import NotesApiClient, parse_bool, parse_tags
from .sidecar_event_client import emit_sidecar_event, preview_text


_CONTEXT: dict[str, Any] = {
    "last_search_items": [],
    "last_note": None,
    "last_query": "",
    "last_action": "",
}


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _candidate(item: dict[str, Any]) -> dict[str, Any]:
    content = str(item.get("content", "") or "")
    tags = item.get("tags", []) or []
    return {
        "id": item.get("id"),
        "title": item.get("title", ""),
        "content": preview_text(content, limit=120),
        "tags": "，".join(str(tag) for tag in tags),
        "updated_at": item.get("updated_at", ""),
        "is_pinned": bool(item.get("is_pinned")),
        "is_deleted": bool(item.get("is_deleted")),
    }


def _remember_items(items: list[dict[str, Any]], query: str = "", action: str = "") -> None:
    _CONTEXT["last_search_items"] = list(items or [])
    _CONTEXT["last_query"] = query
    _CONTEXT["last_action"] = action
    if len(items or []) == 1:
        _CONTEXT["last_note"] = items[0]


def _resolve_reference(reference: str = "", note_id: int | None = None) -> dict[str, Any] | None:
    if note_id and int(note_id) > 0:
        try:
            return NotesApiClient().get_note(int(note_id), include_deleted=True)
        except Exception:
            return {"id": int(note_id)}

    ref = (reference or "").strip()
    items = list(_CONTEXT.get("last_search_items") or [])

    if not ref:
        return _CONTEXT.get("last_note")

    index_map = {
        "第一条": 0,
        "第一个": 0,
        "第一项": 0,
        "第一": 0,
        "第二条": 1,
        "第二个": 1,
        "第二项": 1,
        "第二": 1,
        "第三条": 2,
        "第三个": 2,
        "第三项": 2,
        "第三": 2,
        "最后一条": -1,
        "最后一个": -1,
        "最后": -1,
    }

    for key, index in index_map.items():
        if key in ref and items:
            try:
                return items[index]
            except Exception:
                return None

    if ref in {"它", "这个", "这条", "那条", "刚才那条", "刚刚那条", "刚才这个"}:
        if _CONTEXT.get("last_note"):
            return _CONTEXT.get("last_note")
        if len(items) == 1:
            return items[0]

    return None


def _emit_tool_call(tool_name: str, arguments: dict) -> None:
    emit_sidecar_event({
        "type": "tool_call",
        "tool_name": tool_name,
        "status": "started",
        "arguments": arguments,
        "message": f"开始调用 {tool_name}",
    })


def _emit_ui_action(action: str, data: dict | None = None, message: str = "") -> None:
    emit_sidecar_event({
        "type": "ui_action",
        "action": action,
        "data": data or {},
        "message": message or f"请求小智便签界面执行：{action}",
    })


def _emit_voice_result(title: str, message: str, success: bool = True, extra: dict | None = None) -> dict:
    data = {
        "title": title,
        "message": message,
        "success": success,
    }
    if extra:
        data.update(extra)
    _emit_ui_action("voice_result" if success else "voice_failure", data, message)
    return data


def _emit_tool_result(
    tool_name: str,
    success: bool,
    message: str,
    data: dict | None = None,
    note_changed: bool = False,
    ui_action: dict | None = None,
) -> None:
    payload = {
        "type": "tool_result",
        "tool_name": tool_name,
        "status": "success" if success else "error",
        "success": success,
        "message": message,
        "data": data or {},
        "note_changed": note_changed,
    }
    if ui_action:
        payload["ui_action"] = ui_action
    emit_sidecar_event(payload)


def _find_candidates(query: str, limit: int = 8, include_deleted: bool = False) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []

    result = NotesApiClient().search_notes(query=query, limit=limit)
    items = result.get("items", []) if isinstance(result, dict) else []
    if not include_deleted:
        items = [item for item in items if not bool(item.get("is_deleted"))]
    return items


@mcp_tool(
    name="notes.create",
    description=(
        "Create a note in the Note Assistant / 小智便签 app through the local Notes API. "
        "Use this tool whenever the user says 新增便签, 创建便签, 记到便签, 记录客户事项."
    ),
    props=[
        Prop("title", PropType.STR),
        Prop("content", PropType.STR, default=""),
        Prop("tags", PropType.STR, default=""),
        Prop("is_pinned", PropType.BOOL, default=False),
    ],
)
async def tool_create_note(args) -> str:
    title = (args.get("title") or "").strip()
    content = args.get("content", "") or ""
    tag_list = parse_tags(args.get("tags", "") or "")
    is_pinned = parse_bool(args.get("is_pinned", False))

    _emit_tool_call("notes.create", {
        "title": title,
        "content_preview": preview_text(content),
        "tags": tag_list,
        "is_pinned": is_pinned,
    })

    if not title:
        message = "创建便签失败：title 不能为空"
        _emit_voice_result("创建失败", message, False)
        _emit_tool_result("notes.create", False, message)
        return _json({"success": False, "message": message})

    try:
        note = NotesApiClient().create_note(
            title=title,
            content=content,
            tags=tag_list,
            is_pinned=is_pinned,
        )
        _CONTEXT["last_note"] = note
        message = f"便签已创建：{note.get('title', title)}"
        _emit_ui_action("refresh_notes", {"note_id": note.get("id")}, "已在小智便签中刷新列表")
        _emit_voice_result("便签已创建", message, True, {"note_id": note.get("id")})
        _emit_tool_result(
            "notes.create",
            True,
            message,
            data={"note_id": note.get("id"), "title": note.get("title", title)},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已创建", "note": note})
    except Exception as exc:
        message = f"创建便签失败：{exc}"
        _emit_voice_result("创建失败", message, False)
        _emit_tool_result("notes.create", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.get",
    description="Get one exact note by note_id from 小智便签. Use after notes.search when a candidate note_id is known.",
    props=[
        Prop("note_id", PropType.INT),
        Prop("include_deleted", PropType.BOOL, default=False),
    ],
)
async def tool_get_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "读取便签失败：note_id 无效"
        _emit_voice_result("读取失败", message, False)
        _emit_tool_result("notes.get", False, message)
        return _json({"success": False, "message": message})

    include_deleted = parse_bool(args.get("include_deleted", False))
    _emit_tool_call("notes.get", {"note_id": note_id, "include_deleted": include_deleted})

    try:
        note = NotesApiClient().get_note(note_id, include_deleted=include_deleted)
        _CONTEXT["last_note"] = note
        message = f"读取便签成功：{note.get('title', note_id)}"
        _emit_tool_result(
            "notes.get",
            True,
            message,
            data={"note_id": note.get("id", note_id), "title": note.get("title", "")},
            note_changed=False,
        )
        return _json({"success": True, "note": note})
    except Exception as exc:
        message = f"读取便签失败：{exc}"
        _emit_voice_result("读取失败", message, False)
        _emit_tool_result("notes.get", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.get_note",
    description="Alias of notes.get. Get one exact note by note_id from 小智便签.",
    props=[
        Prop("note_id", PropType.INT),
        Prop("include_deleted", PropType.BOOL, default=False),
    ],
)
async def tool_get_note_alias(args) -> str:
    return await tool_get_note(args)


@mcp_tool(
    name="notes.search",
    description=(
        "Search notes in 小智便签. This also opens the PC App Search page with real results. "
        "For delete/update when multiple notes may match, call notes.prepare_delete or notes.context.resolve before destructive tools."
    ),
    props=[
        Prop("query", PropType.STR),
        Prop("limit", PropType.INT, default=10),
    ],
)
async def tool_search_notes(args) -> str:
    query = (args.get("query") or "").strip()
    limit = int(args.get("limit", 10) or 10)

    _emit_tool_call("notes.search", {"query": query, "limit": limit})

    if not query:
        message = "查询便签失败：query 不能为空"
        _emit_voice_result("查询失败", message, False)
        _emit_tool_result("notes.search", False, message)
        return _json({"success": False, "message": message})

    try:
        result = NotesApiClient().search_notes(query=query, limit=limit)
        total = result.get("total", 0)
        items = result.get("items", [])
        _remember_items(items, query=query, action="search")
        message = f"查询完成：找到 {total} 条便签"

        ui_action = {
            "action": "show_search",
            "data": {"query": query, "total": total},
            "message": f"已在小智便签中显示“{query}”的搜索结果",
        }
        _emit_ui_action(**ui_action)
        _emit_voice_result("查询完成", message, True, {"query": query, "total": total})
        _emit_tool_result(
            "notes.search",
            True,
            message,
            data={
                "query": query,
                "total": total,
                "items_preview": [
                    {"id": item.get("id"), "title": item.get("title")}
                    for item in items[:5]
                ],
            },
            ui_action=ui_action,
            note_changed=False,
        )
        return _json({
            "success": True,
            "query": query,
            "total": total,
            "items": items,
            "ui_action": "show_search",
            "context": {"last_search_items": len(items)},
        })
    except Exception as exc:
        message = f"查询便签失败：{exc}"
        _emit_voice_result("查询失败", message, False)
        _emit_tool_result("notes.search", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.prepare_delete",
    description=(
        "Prepare a safe delete operation. Use this before deleting when the user refers to a note by title/content/query "
        "or when multiple candidates may match. It never deletes directly. It opens a candidate selection or delete confirmation UI."
    ),
    props=[
        Prop("query", PropType.STR, default=""),
        Prop("note_id", PropType.INT, default=0),
        Prop("reference", PropType.STR, default=""),
    ],
)
async def tool_prepare_delete(args) -> str:
    query = (args.get("query") or "").strip()
    reference = (args.get("reference") or "").strip()
    try:
        note_id = int(args.get("note_id", 0) or 0)
    except Exception:
        note_id = 0

    _emit_tool_call("notes.prepare_delete", {"query": query, "note_id": note_id, "reference": reference})

    try:
        note = _resolve_reference(reference=reference, note_id=note_id)
        if note and note.get("id"):
            candidate = _candidate(note)
            ui_data = {
                "note_id": candidate["id"],
                "title": candidate["title"],
                "content": candidate["content"],
                "action_type": "delete",
                "message": "为了防止误删，请确认是否删除这条便签。",
            }
            _emit_ui_action("voice_confirm_delete", ui_data, "请求确认删除便签")
            _emit_tool_result("notes.prepare_delete", True, "已打开删除确认", data=ui_data)
            return _json({"success": True, "requires_confirmation": True, "candidate": candidate})

        items = _find_candidates(query, limit=8)
        _remember_items(items, query=query, action="delete")

        if not items:
            message = f"没有找到可删除的便签：{query or reference or note_id}"
            _emit_voice_result("没有找到便签", message, False, {"retry_action": "search"})
            _emit_tool_result("notes.prepare_delete", False, message)
            return _json({"success": False, "message": message})

        if len(items) == 1:
            candidate = _candidate(items[0])
            _CONTEXT["last_note"] = items[0]
            ui_data = {
                "note_id": candidate["id"],
                "title": candidate["title"],
                "content": candidate["content"],
                "action_type": "delete",
                "message": "找到 1 条匹配便签。为了防止误删，请确认是否删除。",
            }
            _emit_ui_action("voice_confirm_delete", ui_data, "请求确认删除便签")
            _emit_tool_result("notes.prepare_delete", True, "已打开删除确认", data=ui_data)
            return _json({"success": True, "requires_confirmation": True, "candidate": candidate})

        candidates = [_candidate(item) for item in items]
        ui_data = {
            "title": "请选择要删除的便签",
            "message": f"找到 {len(candidates)} 条匹配结果。删除前必须选择明确便签。",
            "action_type": "delete",
            "candidates": candidates,
        }
        _emit_ui_action("voice_candidates", ui_data, "请求用户选择要删除的便签")
        _emit_tool_result("notes.prepare_delete", True, "已打开多候选选择", data={"count": len(candidates)})
        return _json({"success": True, "requires_selection": True, "candidates": candidates})
    except Exception as exc:
        message = f"准备删除失败：{exc}"
        _emit_voice_result("准备删除失败", message, False)
        _emit_tool_result("notes.prepare_delete", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.context.resolve",
    description=(
        "Resolve context references like 第一条, 第二条, 刚才那条, 它 from the last search/tool context. "
        "Use this before update/delete/pin when the user uses pronouns."
    ),
    props=[
        Prop("reference", PropType.STR),
        Prop("action", PropType.STR, default="select"),
    ],
)
async def tool_resolve_context(args) -> str:
    reference = (args.get("reference") or "").strip()
    action = (args.get("action") or "select").strip()

    _emit_tool_call("notes.context.resolve", {"reference": reference, "action": action})
    note = _resolve_reference(reference=reference)

    if not note or not note.get("id"):
        message = f"无法确定“{reference}”指的是哪条便签"
        _emit_voice_result("无法确定目标", message, False)
        _emit_tool_result("notes.context.resolve", False, message)
        return _json({"success": False, "message": message})

    _CONTEXT["last_note"] = note
    candidate = _candidate(note)

    if action == "delete":
        ui_data = {
            "note_id": candidate["id"],
            "title": candidate["title"],
            "content": candidate["content"],
            "action_type": "delete",
            "message": "已根据上下文找到目标。删除前请确认。",
        }
        _emit_ui_action("voice_confirm_delete", ui_data, "请求确认删除便签")
    else:
        _emit_voice_result("已确定目标", f"已确定：{candidate['title']}", True, {"note_id": candidate["id"]})

    _emit_tool_result("notes.context.resolve", True, "已确定上下文目标", data=candidate)
    return _json({"success": True, "note": note})


@mcp_tool(
    name="notes.list",
    description="List recent active notes in 小智便签.",
    props=[Prop("limit", PropType.INT, default=10)],
)
async def tool_list_notes(args) -> str:
    limit = int(args.get("limit", 10) or 10)
    _emit_tool_call("notes.list", {"limit": limit})

    try:
        notes = NotesApiClient().list_notes(limit=limit)
        _remember_items(notes, action="list")
        message = f"已列出 {len(notes)} 条最近便签"
        _emit_tool_result("notes.list", True, message, data={"count": len(notes)})
        return _json({"success": True, "items": notes})
    except Exception as exc:
        message = f"列出便签失败：{exc}"
        _emit_voice_result("列出失败", message, False)
        _emit_tool_result("notes.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.deleted.list",
    description="List notes in 已删除 / recycle bin. This opens the Deleted page in the PC App.",
    props=[Prop("limit", PropType.INT, default=50)],
)
async def tool_list_deleted_notes(args) -> str:
    limit = int(args.get("limit", 50) or 50)
    _emit_tool_call("notes.deleted.list", {"limit": limit})

    try:
        notes = NotesApiClient().list_deleted_notes(limit=limit)
        _remember_items(notes, action="deleted")
        message = f"已列出 {len(notes)} 条已删除便签"
        ui_action = {
            "action": "show_deleted",
            "data": {"count": len(notes)},
            "message": "已在小智便签中打开已删除列表",
        }
        _emit_ui_action(**ui_action)
        _emit_voice_result("已打开已删除", message, True, {"count": len(notes)})
        _emit_tool_result(
            "notes.deleted.list",
            True,
            message,
            data={"count": len(notes), "items_preview": [_candidate(item) for item in notes[:8]]},
            ui_action=ui_action,
            note_changed=False,
        )
        return _json({"success": True, "items": notes, "ui_action": "show_deleted"})
    except Exception as exc:
        message = f"列出已删除便签失败：{exc}"
        _emit_voice_result("打开已删除失败", message, False)
        _emit_tool_result("notes.deleted.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.restore",
    description="Restore a soft-deleted note from 已删除 by clear note_id. Safe operation, no destructive confirmation required.",
    props=[Prop("note_id", PropType.INT)],
)
async def tool_restore_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "还原便签失败：note_id 无效"
        _emit_voice_result("还原失败", message, False)
        _emit_tool_result("notes.restore", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.restore", {"note_id": note_id})

    try:
        note = NotesApiClient().restore_note(note_id)
        _CONTEXT["last_note"] = note
        message = f"便签已还原：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_voice_result("便签已还原", message, True, {"note_id": note_id})
        _emit_tool_result(
            "notes.restore",
            True,
            message,
            data={"note_id": note_id, "title": note.get("title", "")},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已还原", "note": note})
    except Exception as exc:
        message = f"还原便签失败：{exc}"
        _emit_voice_result("还原失败", message, False)
        _emit_tool_result("notes.restore", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.hard_delete",
    description=(
        "Permanently delete a note by note_id. Irreversible. Requires confirmed=true. "
        "If confirmed is false or omitted, this only opens a confirmation UI and does not delete."
    ),
    props=[
        Prop("note_id", PropType.INT),
        Prop("confirmed", PropType.BOOL, default=False),
    ],
)
async def tool_hard_delete_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "彻底删除便签失败：note_id 无效"
        _emit_voice_result("彻底删除失败", message, False)
        _emit_tool_result("notes.hard_delete", False, message)
        return _json({"success": False, "message": message})

    confirmed = parse_bool(args.get("confirmed", False))
    _emit_tool_call("notes.hard_delete", {"note_id": note_id, "confirmed": confirmed})

    if not confirmed:
        try:
            note = NotesApiClient().get_note(note_id, include_deleted=True)
        except Exception:
            note = {"id": note_id, "title": f"#{note_id}", "content": ""}
        candidate = _candidate(note)
        ui_data = {
            "note_id": note_id,
            "title": candidate["title"],
            "content": candidate["content"],
            "action_type": "hard_delete",
            "message": "该操作会永久删除，无法还原。请再次确认。",
        }
        _emit_ui_action("voice_confirm_delete", ui_data, "请求确认彻底删除便签")
        _emit_tool_result("notes.hard_delete", True, "已打开彻底删除确认", data=ui_data)
        return _json({"success": True, "requires_confirmation": True, "message": "需要确认后才能彻底删除"})

    try:
        result = NotesApiClient().hard_delete_note(note_id)
        message = f"便签已彻底删除：{note_id}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_voice_result("便签已彻底删除", message, True, {"note_id": note_id})
        _emit_tool_result("notes.hard_delete", True, message, data={"note_id": note_id, "result": result}, note_changed=True)
        return _json({"success": True, "message": "便签已彻底删除", "result": result})
    except Exception as exc:
        message = f"彻底删除便签失败：{exc}"
        _emit_voice_result("彻底删除失败", message, False)
        _emit_tool_result("notes.hard_delete", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.update",
    description="Update an existing note by clear note_id. If target is vague, call notes.search/context.resolve first.",
    props=[
        Prop("note_id", PropType.INT),
        Prop("title", PropType.STR, default=""),
        Prop("content", PropType.STR, default=""),
        Prop("tags", PropType.STR, default=""),
        Prop("is_pinned", PropType.STR, default=""),
    ],
)
async def tool_update_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "更新便签失败：note_id 无效"
        _emit_voice_result("更新失败", message, False)
        _emit_tool_result("notes.update", False, message)
        return _json({"success": False, "message": message})

    title = args.get("title", "")
    content = args.get("content", "")
    tags_text = args.get("tags", "")
    is_pinned_raw = args.get("is_pinned", "")

    _emit_tool_call("notes.update", {
        "note_id": note_id,
        "title": title,
        "content_preview": preview_text(content),
        "tags": parse_tags(tags_text) if tags_text else [],
        "is_pinned": is_pinned_raw,
    })

    try:
        note = NotesApiClient().update_note(
            note_id=note_id,
            title=title if title else None,
            content=content if content else None,
            tags=parse_tags(tags_text) if tags_text else None,
            is_pinned=parse_bool(is_pinned_raw) if str(is_pinned_raw).strip() else None,
        )
        _CONTEXT["last_note"] = note
        message = f"便签已更新：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_voice_result("便签已更新", message, True, {"note_id": note_id})
        _emit_tool_result("notes.update", True, message, data={"note_id": note.get("id", note_id), "title": note.get("title", "")}, note_changed=True)
        return _json({"success": True, "message": "便签已更新", "note": note})
    except Exception as exc:
        message = f"更新便签失败：{exc}"
        _emit_voice_result("更新失败", message, False)
        _emit_tool_result("notes.update", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(name="notes.pin", description="Pin / 置顶 an existing active note by clear note_id.", props=[Prop("note_id", PropType.INT)])
async def tool_pin_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "置顶便签失败：note_id 无效"
        _emit_voice_result("置顶失败", message, False)
        _emit_tool_result("notes.pin", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.pin", {"note_id": note_id})

    try:
        note = NotesApiClient().pin_note(note_id)
        _CONTEXT["last_note"] = note
        message = f"便签已置顶：{note.get('title', note_id)}"
        _emit_ui_action("show_pinned", {"note_id": note_id}, "已在小智便签中显示置顶列表")
        _emit_voice_result("便签已置顶", message, True, {"note_id": note_id})
        _emit_tool_result("notes.pin", True, message, data={"note_id": note_id, "title": note.get("title", "")}, note_changed=True)
        return _json({"success": True, "message": "便签已置顶", "note": note})
    except Exception as exc:
        message = f"置顶便签失败：{exc}"
        _emit_voice_result("置顶失败", message, False)
        _emit_tool_result("notes.pin", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(name="notes.unpin", description="Unpin / 取消置顶 an existing active note by clear note_id.", props=[Prop("note_id", PropType.INT)])
async def tool_unpin_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "取消置顶失败：note_id 无效"
        _emit_voice_result("取消置顶失败", message, False)
        _emit_tool_result("notes.unpin", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.unpin", {"note_id": note_id})

    try:
        note = NotesApiClient().unpin_note(note_id)
        _CONTEXT["last_note"] = note
        message = f"便签已取消置顶：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_voice_result("已取消置顶", message, True, {"note_id": note_id})
        _emit_tool_result("notes.unpin", True, message, data={"note_id": note_id, "title": note.get("title", "")}, note_changed=True)
        return _json({"success": True, "message": "便签已取消置顶", "note": note})
    except Exception as exc:
        message = f"取消置顶失败：{exc}"
        _emit_voice_result("取消置顶失败", message, False)
        _emit_tool_result("notes.unpin", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.delete",
    description=(
        "Soft-delete a note by clear note_id. Anti-misdelete rule: confirmed=true is required for direct deletion. "
        "If confirmed is false or omitted, this opens a delete confirmation UI and does not delete."
    ),
    props=[
        Prop("note_id", PropType.INT),
        Prop("confirmed", PropType.BOOL, default=False),
    ],
)
async def tool_delete_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "删除便签失败：note_id 无效"
        _emit_voice_result("删除失败", message, False)
        _emit_tool_result("notes.delete", False, message)
        return _json({"success": False, "message": message})

    confirmed = parse_bool(args.get("confirmed", False))
    _emit_tool_call("notes.delete", {"note_id": note_id, "confirmed": confirmed})

    if not confirmed:
        try:
            note = NotesApiClient().get_note(note_id, include_deleted=False)
        except Exception:
            note = {"id": note_id, "title": f"#{note_id}", "content": ""}
        candidate = _candidate(note)
        ui_data = {
            "note_id": note_id,
            "title": candidate["title"],
            "content": candidate["content"],
            "action_type": "delete",
            "message": "删除前必须确认。该操作会把便签移入“已删除”，之后可还原。",
        }
        _emit_ui_action("voice_confirm_delete", ui_data, "请求确认删除便签")
        _emit_tool_result("notes.delete", True, "已打开删除确认", data=ui_data)
        return _json({"success": True, "requires_confirmation": True, "message": "需要确认后才能删除"})

    try:
        result = NotesApiClient().delete_note(note_id)
        message = f"便签已移入已删除：{note_id}，可还原或彻底删除"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_voice_result("便签已删除", message, True, {"note_id": note_id})
        _emit_tool_result("notes.delete", True, message, data={"note_id": note_id, "result": result}, note_changed=True)
        return _json({"success": True, "message": "便签已移入已删除，可还原或彻底删除", "result": result})
    except Exception as exc:
        message = f"删除便签失败：{exc}"
        _emit_voice_result("删除失败", message, False)
        _emit_tool_result("notes.delete", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(name="notes.tags.list", description="List tags currently used by notes.", props=[])
async def tool_list_tags(args) -> str:
    _emit_tool_call("notes.tags.list", {})

    try:
        tags = NotesApiClient().list_tags(include_deleted=True)
        message = f"已列出 {len(tags)} 个标签"
        _emit_tool_result("notes.tags.list", True, message, data={"tags": tags})
        return _json({"success": True, "items": tags})
    except Exception as exc:
        message = f"列出标签失败：{exc}"
        _emit_voice_result("列出标签失败", message, False)
        _emit_tool_result("notes.tags.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(name="notes.tags.add", description="Create an empty custom tag in the PC App sidebar.", props=[Prop("tag", PropType.STR)])
async def tool_add_tag(args) -> str:
    tag = (args.get("tag") or "").strip()
    _emit_tool_call("notes.tags.add", {"tag": tag})

    if not tag:
        message = "新增标签失败：tag 不能为空"
        _emit_voice_result("新增标签失败", message, False)
        _emit_tool_result("notes.tags.add", False, message)
        return _json({"success": False, "message": message})

    if tag in {"全部", "置顶", "已删除"}:
        message = "新增标签失败：不能使用系统分类名称"
        _emit_voice_result("新增标签失败", message, False)
        _emit_tool_result("notes.tags.add", False, message)
        return _json({"success": False, "message": message})

    ui_action = {"action": "add_tag", "data": {"tag": tag}, "message": f"已请求小智便签新增标签：{tag}"}
    _emit_ui_action(**ui_action)
    _emit_voice_result("标签已新增", f"标签已新增：{tag}", True, {"tag": tag})
    _emit_tool_result("notes.tags.add", True, f"标签已新增：{tag}", data={"tag": tag}, ui_action=ui_action)
    return _json({"success": True, "message": "标签已新增", "tag": tag, "ui_action": "add_tag"})


@mcp_tool(name="notes.tags.delete_empty", description="Delete an empty custom tag from the PC App sidebar. Refuses if any note still has that tag.", props=[Prop("tag", PropType.STR)])
async def tool_delete_empty_tag(args) -> str:
    tag = (args.get("tag") or "").strip()
    _emit_tool_call("notes.tags.delete_empty", {"tag": tag})

    if not tag:
        message = "删除标签失败：tag 不能为空"
        _emit_voice_result("删除标签失败", message, False)
        _emit_tool_result("notes.tags.delete_empty", False, message)
        return _json({"success": False, "message": message})

    try:
        if NotesApiClient().tag_has_notes(tag):
            message = f"删除标签失败：标签“{tag}”下还有便签，不能删除"
            _emit_voice_result("删除标签失败", message, False)
            _emit_tool_result("notes.tags.delete_empty", False, message, data={"tag": tag})
            return _json({"success": False, "message": message})

        ui_action = {"action": "delete_empty_tag", "data": {"tag": tag}, "message": f"已请求小智便签删除空标签：{tag}"}
        _emit_ui_action(**ui_action)
        _emit_voice_result("标签已删除", f"空标签已删除：{tag}", True, {"tag": tag})
        _emit_tool_result("notes.tags.delete_empty", True, f"空标签已删除：{tag}", data={"tag": tag}, ui_action=ui_action)
        return _json({"success": True, "message": "空标签已删除", "tag": tag, "ui_action": "delete_empty_tag"})
    except Exception as exc:
        message = f"删除标签失败：{exc}"
        _emit_voice_result("删除标签失败", message, False)
        _emit_tool_result("notes.tags.delete_empty", False, message)
        return _json({"success": False, "message": message})

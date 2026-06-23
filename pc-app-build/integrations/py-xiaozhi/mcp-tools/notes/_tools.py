from __future__ import annotations

import json

from src.mcp.decorators import Prop, PropType, mcp_tool

from .notes_api_client import NotesApiClient, parse_bool, parse_tags
from .sidecar_event_client import emit_sidecar_event, preview_text


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _emit_tool_call(tool_name: str, arguments: dict) -> None:
    emit_sidecar_event({
        "type": "tool_call",
        "tool_name": tool_name,
        "status": "started",
        "arguments": arguments,
        "message": f"开始调用 {tool_name}",
    })


def _emit_tool_result(
    tool_name: str,
    success: bool,
    message: str,
    data: dict | None = None,
    note_changed: bool = False,
) -> None:
    emit_sidecar_event({
        "type": "tool_result",
        "tool_name": tool_name,
        "status": "success" if success else "error",
        "success": success,
        "message": message,
        "data": data or {},
        "note_changed": note_changed,
    })


@mcp_tool(
    name="notes.create",
    description=(
        "Create a note in the Note Assistant / 小智便签 app through the local Notes API. "
        "Use this tool whenever the user says: 便签, 小智便签, 便签App, 记到便签, 新增便签, "
        "创建便签, 记录客户事项, 待办便签, 报价便签, 产品便签. "
        "Do NOT use file.write or notepad.write for app notes; those are for local files or Windows Notepad. "
        "Parameters: title is required; content is optional; tags is a comma-separated string like 客户,待办; "
        "is_pinned can be true when the user wants pinned/top note."
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
    tags = args.get("tags", "") or ""
    is_pinned = parse_bool(args.get("is_pinned", False))
    tag_list = parse_tags(tags)

    _emit_tool_call("notes.create", {
        "title": title,
        "content_preview": preview_text(content),
        "tags": tag_list,
        "is_pinned": is_pinned,
    })

    if not title:
        message = "创建便签失败：title 不能为空"
        _emit_tool_result("notes.create", False, message)
        return _json({"success": False, "message": message})

    try:
        note = NotesApiClient().create_note(
            title=title,
            content=content,
            tags=tag_list,
            is_pinned=is_pinned,
        )
        message = f"便签已创建：{note.get('title', title)}"
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
        _emit_tool_result("notes.create", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.search",
    description=(
        "Search notes in the Note Assistant / 小智便签 app through the local Notes API. "
        "Use this when the user asks to 查便签, 搜便签, 找便签, 查询客户事项, 查询报价, 查询待办. "
        "This searches app notes, not files and not Windows Notepad. "
        "Parameter query is the keyword, such as 王总, 包装, 屏幕, 游戏手柄."
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
        _emit_tool_result("notes.search", False, message)
        return _json({"success": False, "message": message})

    try:
        result = NotesApiClient().search_notes(query=query, limit=limit)
        total = result.get("total", 0)
        message = f"查询完成：找到 {total} 条便签"
        _emit_tool_result(
            "notes.search",
            True,
            message,
            data={
                "query": query,
                "total": total,
                "items_preview": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                    }
                    for item in result.get("items", [])[:5]
                ],
            },
            note_changed=False,
        )
        return _json({
            "success": True,
            "query": query,
            "total": total,
            "items": result.get("items", []),
        })
    except Exception as exc:
        message = f"查询便签失败：{exc}"
        _emit_tool_result("notes.search", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.list",
    description=(
        "List recent notes in the Note Assistant / 小智便签 app. "
        "Use this when the user asks 最近便签, 列出便签, 看一下便签列表."
    ),
    props=[Prop("limit", PropType.INT, default=10)],
)
async def tool_list_notes(args) -> str:
    limit = int(args.get("limit", 10) or 10)

    _emit_tool_call("notes.list", {"limit": limit})

    try:
        notes = NotesApiClient().list_notes(limit=limit)
        message = f"已列出 {len(notes)} 条最近便签"
        _emit_tool_result(
            "notes.list",
            True,
            message,
            data={"count": len(notes)},
            note_changed=False,
        )
        return _json({"success": True, "items": notes})
    except Exception as exc:
        message = f"列出便签失败：{exc}"
        _emit_tool_result("notes.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.update",
    description=(
        "Update an existing note in the Note Assistant / 小智便签 app by note_id. "
        "Use only after the target note is clear. If the user gives a vague target, call notes.search first. "
        "Do not use file tools or notepad tools for updating app notes."
    ),
    props=[
        Prop("note_id", PropType.INT),
        Prop("title", PropType.STR, default=""),
        Prop("content", PropType.STR, default=""),
        Prop("tags", PropType.STR, default=""),
        Prop("is_pinned", PropType.BOOL, default=False),
    ],
)
async def tool_update_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "更新便签失败：note_id 无效"
        _emit_tool_result("notes.update", False, message)
        return _json({"success": False, "message": message})

    title = args.get("title", "")
    content = args.get("content", "")
    tags_text = args.get("tags", "")
    is_pinned = args.get("is_pinned", None)

    _emit_tool_call("notes.update", {
        "note_id": note_id,
        "title": title,
        "content_preview": preview_text(content),
        "tags": parse_tags(tags_text) if tags_text else [],
    })

    try:
        note = NotesApiClient().update_note(
            note_id=note_id,
            title=title if title else None,
            content=content if content else None,
            tags=parse_tags(tags_text) if tags_text else None,
            is_pinned=parse_bool(is_pinned) if is_pinned is not None else None,
        )
        message = f"便签已更新：{note.get('title', note_id)}"
        _emit_tool_result(
            "notes.update",
            True,
            message,
            data={"note_id": note.get("id", note_id), "title": note.get("title", "")},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已更新", "note": note})
    except Exception as exc:
        message = f"更新便签失败：{exc}"
        _emit_tool_result("notes.update", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.delete",
    description=(
        "Soft-delete an existing note in the Note Assistant / 小智便签 app by note_id. "
        "Use only after the user clearly confirms the target note. If the target is vague, call notes.search first. "
        "This moves the note to deleted notes; it does not permanently erase it."
    ),
    props=[Prop("note_id", PropType.INT)],
)
async def tool_delete_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "删除便签失败：note_id 无效"
        _emit_tool_result("notes.delete", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.delete", {"note_id": note_id})

    try:
        result = NotesApiClient().delete_note(note_id)
        message = f"便签已删除：{note_id}"
        _emit_tool_result(
            "notes.delete",
            True,
            message,
            data={"note_id": note_id, "result": result},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已删除", "result": result})
    except Exception as exc:
        message = f"删除便签失败：{exc}"
        _emit_tool_result("notes.delete", False, message)
        return _json({"success": False, "message": message})

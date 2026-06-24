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


def _emit_ui_action(action: str, data: dict | None = None, message: str = "") -> None:
    emit_sidecar_event({
        "type": "ui_action",
        "action": action,
        "data": data or {},
        "message": message or f"请求小智便签界面执行：{action}",
    })


@mcp_tool(
    name="notes.create",
    description=(
        "Create a note in the Note Assistant / 小智便签 app through the local Notes API. "
        "Use this tool whenever the user says 新增便签, 创建便签, 记到便签, 记录客户事项. "
        "Do not use file.write or notepad.write for app notes."
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
        _emit_ui_action("refresh_notes", {"note_id": note.get("id")}, "已在小智便签中刷新列表")
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
    name="notes.get",
    description=(
        "Get one exact note by note_id from the Note Assistant / 小智便签 app. "
        "Use after notes.search when a candidate note_id is known."
    ),
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
        _emit_tool_result("notes.get", False, message)
        return _json({"success": False, "message": message})

    include_deleted = parse_bool(args.get("include_deleted", False))
    _emit_tool_call("notes.get", {"note_id": note_id, "include_deleted": include_deleted})

    try:
        note = NotesApiClient().get_note(note_id, include_deleted=include_deleted)
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
        "Search notes in the Note Assistant / 小智便签 app through the local Notes API. "
        "Use this for 查便签, 搜便签, 找便签, 查询客户事项. "
        "This tool also asks the PC App to open the search page and display the results."
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
        items = result.get("items", [])
        message = f"查询完成：找到 {total} 条便签"

        ui_action = {
            "action": "show_search",
            "data": {"query": query, "total": total},
            "message": f"已在小智便签中显示“{query}”的搜索结果",
        }
        _emit_ui_action(**ui_action)
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
        })
    except Exception as exc:
        message = f"查询便签失败：{exc}"
        _emit_tool_result("notes.search", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.list",
    description="List recent active notes in the Note Assistant / 小智便签 app.",
    props=[Prop("limit", PropType.INT, default=10)],
)
async def tool_list_notes(args) -> str:
    limit = int(args.get("limit", 10) or 10)
    _emit_tool_call("notes.list", {"limit": limit})

    try:
        notes = NotesApiClient().list_notes(limit=limit)
        message = f"已列出 {len(notes)} 条最近便签"
        _emit_tool_result("notes.list", True, message, data={"count": len(notes)})
        return _json({"success": True, "items": notes})
    except Exception as exc:
        message = f"列出便签失败：{exc}"
        _emit_tool_result("notes.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.deleted.list",
    description=(
        "List notes in 已删除 / recycle bin. Use when the user asks 查看已删除便签, 回收站, "
        "刚才删除的便签, 找回删除的便签. This also opens the Deleted page in the PC App."
    ),
    props=[Prop("limit", PropType.INT, default=50)],
)
async def tool_list_deleted_notes(args) -> str:
    limit = int(args.get("limit", 50) or 50)
    _emit_tool_call("notes.deleted.list", {"limit": limit})

    try:
        notes = NotesApiClient().list_deleted_notes(limit=limit)
        message = f"已列出 {len(notes)} 条已删除便签"
        ui_action = {
            "action": "show_deleted",
            "data": {"count": len(notes)},
            "message": "已在小智便签中打开已删除列表",
        }
        _emit_ui_action(**ui_action)
        _emit_tool_result(
            "notes.deleted.list",
            True,
            message,
            data={
                "count": len(notes),
                "items_preview": [
                    {"id": item.get("id"), "title": item.get("title")}
                    for item in notes[:8]
                ],
            },
            ui_action=ui_action,
            note_changed=False,
        )
        return _json({"success": True, "items": notes, "ui_action": "show_deleted"})
    except Exception as exc:
        message = f"列出已删除便签失败：{exc}"
        _emit_tool_result("notes.deleted.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.restore",
    description=(
        "Restore a soft-deleted note from 已删除 by note_id. Use after notes.deleted.list "
        "or notes.get(include_deleted=true) when the user confirms the target."
    ),
    props=[Prop("note_id", PropType.INT)],
)
async def tool_restore_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "还原便签失败：note_id 无效"
        _emit_tool_result("notes.restore", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.restore", {"note_id": note_id})

    try:
        note = NotesApiClient().restore_note(note_id)
        message = f"便签已还原：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
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
        _emit_tool_result("notes.restore", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.hard_delete",
    description=(
        "Permanently delete a note by note_id. This is irreversible. Only use after the user explicitly says "
        "彻底删除, 永久删除, 从已删除中删除, 清除回收站里的某条便签, and confirms the exact target."
    ),
    props=[Prop("note_id", PropType.INT)],
)
async def tool_hard_delete_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "彻底删除便签失败：note_id 无效"
        _emit_tool_result("notes.hard_delete", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.hard_delete", {"note_id": note_id})

    try:
        result = NotesApiClient().hard_delete_note(note_id)
        message = f"便签已彻底删除：{note_id}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_tool_result(
            "notes.hard_delete",
            True,
            message,
            data={"note_id": note_id, "result": result},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已彻底删除", "result": result})
    except Exception as exc:
        message = f"彻底删除便签失败：{exc}"
        _emit_tool_result("notes.hard_delete", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.update",
    description=(
        "Update an existing note in 小智便签 by note_id. "
        "If the target is vague, call notes.search first, then notes.get if needed."
    ),
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
        message = f"便签已更新：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
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
    name="notes.pin",
    description="Pin / 置顶 an existing active note by note_id.",
    props=[Prop("note_id", PropType.INT)],
)
async def tool_pin_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "置顶便签失败：note_id 无效"
        _emit_tool_result("notes.pin", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.pin", {"note_id": note_id})

    try:
        note = NotesApiClient().pin_note(note_id)
        message = f"便签已置顶：{note.get('title', note_id)}"
        _emit_ui_action("show_pinned", {"note_id": note_id}, "已在小智便签中显示置顶列表")
        _emit_tool_result(
            "notes.pin",
            True,
            message,
            data={"note_id": note_id, "title": note.get("title", "")},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已置顶", "note": note})
    except Exception as exc:
        message = f"置顶便签失败：{exc}"
        _emit_tool_result("notes.pin", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.unpin",
    description="Unpin / 取消置顶 an existing active note by note_id.",
    props=[Prop("note_id", PropType.INT)],
)
async def tool_unpin_note(args) -> str:
    try:
        note_id = int(args.get("note_id"))
    except Exception:
        message = "取消置顶失败：note_id 无效"
        _emit_tool_result("notes.unpin", False, message)
        return _json({"success": False, "message": message})

    _emit_tool_call("notes.unpin", {"note_id": note_id})

    try:
        note = NotesApiClient().unpin_note(note_id)
        message = f"便签已取消置顶：{note.get('title', note_id)}"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_tool_result(
            "notes.unpin",
            True,
            message,
            data={"note_id": note_id, "title": note.get("title", "")},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已取消置顶", "note": note})
    except Exception as exc:
        message = f"取消置顶失败：{exc}"
        _emit_tool_result("notes.unpin", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.delete",
    description=(
        "Soft-delete an existing note in 小智便签 by note_id. "
        "This only moves the note into 已删除 / recycle bin. It can still be restored. "
        "Use notes.hard_delete only when the user explicitly asks for permanent deletion."
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
        message = f"便签已移入已删除：{note_id}，可还原或彻底删除"
        _emit_ui_action("refresh_notes", {"note_id": note_id}, "已刷新小智便签列表")
        _emit_tool_result(
            "notes.delete",
            True,
            message,
            data={"note_id": note_id, "result": result},
            note_changed=True,
        )
        return _json({"success": True, "message": "便签已移入已删除，可还原或彻底删除", "result": result})
    except Exception as exc:
        message = f"删除便签失败：{exc}"
        _emit_tool_result("notes.delete", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.tags.list",
    description="List tags currently used by notes. Use when the user asks 有哪些标签, 标签列表.",
    props=[],
)
async def tool_list_tags(args) -> str:
    _emit_tool_call("notes.tags.list", {})

    try:
        tags = NotesApiClient().list_tags(include_deleted=True)
        message = f"已列出 {len(tags)} 个标签"
        _emit_tool_result("notes.tags.list", True, message, data={"tags": tags})
        return _json({"success": True, "items": tags})
    except Exception as exc:
        message = f"列出标签失败：{exc}"
        _emit_tool_result("notes.tags.list", False, message)
        return _json({"success": False, "message": message})


@mcp_tool(
    name="notes.tags.add",
    description=(
        "Create an empty custom tag in the PC App sidebar. Use when the user says 新增标签, 创建标签, 加一个标签. "
        "This does not modify note content; it asks the PC App UI to add the tag."
    ),
    props=[Prop("tag", PropType.STR)],
)
async def tool_add_tag(args) -> str:
    tag = (args.get("tag") or "").strip()
    _emit_tool_call("notes.tags.add", {"tag": tag})

    if not tag:
        message = "新增标签失败：tag 不能为空"
        _emit_tool_result("notes.tags.add", False, message)
        return _json({"success": False, "message": message})

    if tag in {"全部", "置顶", "已删除"}:
        message = "新增标签失败：不能使用系统分类名称"
        _emit_tool_result("notes.tags.add", False, message)
        return _json({"success": False, "message": message})

    ui_action = {
        "action": "add_tag",
        "data": {"tag": tag},
        "message": f"已请求小智便签新增标签：{tag}",
    }
    _emit_ui_action(**ui_action)
    _emit_tool_result("notes.tags.add", True, f"标签已新增：{tag}", data={"tag": tag}, ui_action=ui_action)
    return _json({"success": True, "message": "标签已新增", "tag": tag, "ui_action": "add_tag"})


@mcp_tool(
    name="notes.tags.delete_empty",
    description=(
        "Delete an empty custom tag from the PC App sidebar. Use when the user says 删除空标签, 删除已空标签. "
        "This tool refuses if any active or deleted note still has that tag."
    ),
    props=[Prop("tag", PropType.STR)],
)
async def tool_delete_empty_tag(args) -> str:
    tag = (args.get("tag") or "").strip()
    _emit_tool_call("notes.tags.delete_empty", {"tag": tag})

    if not tag:
        message = "删除标签失败：tag 不能为空"
        _emit_tool_result("notes.tags.delete_empty", False, message)
        return _json({"success": False, "message": message})

    try:
        if NotesApiClient().tag_has_notes(tag):
            message = f"删除标签失败：标签“{tag}”下还有便签，不能删除"
            _emit_tool_result("notes.tags.delete_empty", False, message, data={"tag": tag})
            return _json({"success": False, "message": message})

        ui_action = {
            "action": "delete_empty_tag",
            "data": {"tag": tag},
            "message": f"已请求小智便签删除空标签：{tag}",
        }
        _emit_ui_action(**ui_action)
        _emit_tool_result("notes.tags.delete_empty", True, f"空标签已删除：{tag}", data={"tag": tag}, ui_action=ui_action)
        return _json({"success": True, "message": "空标签已删除", "tag": tag, "ui_action": "delete_empty_tag"})
    except Exception as exc:
        message = f"删除标签失败：{exc}"
        _emit_tool_result("notes.tags.delete_empty", False, message)
        return _json({"success": False, "message": message})

"""Natural-language routing guidance and safe spoken-query normalization.

The Xiaozhi endpoint remains responsible for selecting MCP tools.  This module
only provides richer descriptor guidance and deterministic cleanup for query
arguments that still contain polite or conversational filler.
"""

from __future__ import annotations

import re
import unicodedata

_QUOTED_TEXT = re.compile(
    r"[\"“”'‘’《》〈〉【】]([^\"“”'‘’《》〈〉【】]{1,200})[\"“”'‘’《》〈〉【】]"
)
_EXPLICIT_ID_PATTERNS = (
    re.compile(r"(?:便签|笔记)?\s*(?:编号|id|ID)\s*(?:是|为|等于|#|:|：)?\s*(\d{1,10})"),
    re.compile(r"第\s*(\d{1,10})\s*(?:号|个)?\s*(?:便签|笔记)"),
    re.compile(r"(?:便签|笔记)\s*#\s*(\d{1,10})"),
)

# Ordered longest-first so a specific phrase is removed before a shorter part.
_FILLER_PHRASES = tuple(
    sorted(
        {
            "麻烦你帮我",
            "麻烦帮我看看",
            "麻烦帮我",
            "能不能帮我",
            "可以帮我",
            "请你帮我",
            "帮我看一下",
            "帮我看看",
            "帮我找一下",
            "帮我查一下",
            "替我找一下",
            "给我找一下",
            "我想找一下",
            "我想看一下",
            "我想看看",
            "我想知道",
            "我想查一下",
            "请帮我",
            "麻烦你",
            "麻烦",
            "请问",
            "请",
            "能不能",
            "可以不可以",
            "可以",
            "帮忙",
            "帮我",
            "给我",
            "替我",
            "搜索一下",
            "查询一下",
            "查找一下",
            "定位一下",
            "找一下",
            "查一下",
            "搜一下",
            "看一下",
            "找找",
            "查查",
            "搜搜",
            "看一看",
            "搜索",
            "查询",
            "查找",
            "定位",
            "看看",
            "帮我看看",
            "有没有记录过",
            "有没有记过",
            "有没有写过",
            "有没有",
            "我之前记的",
            "之前记的",
            "以前记的",
            "以前",
            "我刚才记的",
            "刚才记的",
            "我刚刚记的",
            "刚刚记的",
            "小智便签应用里面",
            "小智便签应用里",
            "小智便签里面",
            "小智便签里",
            "便签应用里面",
            "便签应用里",
            "便签app里面",
            "便签app里",
            "在便签里面",
            "在便签里",
            "在小智便签里面",
            "在小智便签里",
            "那个关于",
            "这个关于",
            "关于",
            "有关",
            "相关的",
            "那条叫",
            "这条叫",
            "标题叫",
            "标题是",
            "名字叫",
            "名称是",
            "的那条便签",
            "的这条便签",
            "的那个便签",
            "的这个便签",
            "的便签",
            "那条便签",
            "这条便签",
            "那个便签",
            "这个便签",
            "便签记录",
            "便签",
            "笔记",
        },
        key=len,
        reverse=True,
    )
)

_CONTEXT_REFERENCE_WORDS = frozenset(
    {
        "刚才那条",
        "刚刚那条",
        "刚才那个",
        "刚刚那个",
        "上一条",
        "前一条",
        "最近那条",
        "最新那条",
        "最后一条",
        "这条",
        "那条",
        "这个",
        "那个",
        "前面那条",
    }
)

_GENERIC_TOKENS = frozenset(
    {
        "我",
        "你",
        "一下",
        "那个",
        "这个",
        "那条",
        "这条",
        "内容",
        "事情",
        "东西",
        "相关",
        "有关",
        "里面",
        "之前",
        "刚才",
        "刚刚",
    }
)

_SPLIT = re.compile(r"[\s,，、;；:：!?！？。\.\-/\\|]+")

_QUERY_META_PATTERNS = (
    re.compile(
        r"(?:最多|至多|只要|给我|返回|列出|显示)\s*"
        r"(?:\d+|[一二三四五六七八九十百]+)\s*"
        r"(?:条|个)(?:结果|便签|记录)?"
    ),
    re.compile(r"(?:先别|不要|先不要)\s*(?:修改|更改|删除|操作|动它)"),
)


def normalize_spoken_text(value: str) -> str:
    """Return stable case-folded text with punctuation and whitespace normalized."""

    text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    text = _SPLIT.sub(" ", text)
    return " ".join(text.split())


def extract_explicit_note_id(value: str) -> int | None:
    """Extract one explicitly labelled positive note id from conversational text."""

    text = unicodedata.normalize("NFKC", str(value)).strip()
    matches: list[int] = []
    for pattern in _EXPLICIT_ID_PATTERNS:
        for raw in pattern.findall(text):
            note_id = int(raw)
            if note_id > 0 and note_id not in matches:
                matches.append(note_id)
    return matches[0] if len(matches) == 1 else None


def is_contextual_reference(value: str) -> bool:
    """Whether the phrase is only an anaphoric target such as '刚才那条'."""

    normalized = normalize_spoken_text(value).replace(" ", "")
    without_noun = normalized.replace("小智便签", "").replace("便签", "").replace("笔记", "")
    stripped = without_noun
    for phrase in _FILLER_PHRASES:
        compact = normalize_spoken_text(phrase).replace(" ", "")
        if compact not in {"便签", "笔记", "记录"}:
            stripped = stripped.replace(compact, "")
    return (
        normalized in _CONTEXT_REFERENCE_WORDS
        or without_noun in _CONTEXT_REFERENCE_WORDS
        or stripped in _CONTEXT_REFERENCE_WORDS
    )


def extract_search_terms(value: str) -> tuple[str, ...]:
    """Extract ordered, bounded search terms from a verbose spoken query.

    Quoted text and a filler-stripped phrase are preferred.  Shorter tokens are
    only fallbacks, so a precise topic such as '王总报价' is attempted before
    broader terms such as '王总' and '报价'.
    """

    raw = unicodedata.normalize("NFKC", str(value)).strip()
    if not raw:
        return ()

    candidates: list[str] = []
    for quoted in _QUOTED_TEXT.findall(raw):
        _append_term(candidates, quoted)

    cleaned = raw
    for phrase in _FILLER_PHRASES:
        cleaned = cleaned.replace(phrase, " ")
    for pattern in _QUERY_META_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = normalize_spoken_text(cleaned)
    _append_term(candidates, cleaned)

    for token in _SPLIT.split(cleaned):
        _append_term(candidates, token)

    # Chinese phrases often have no spaces.  Split common connective particles
    # only as a fallback and retain the original phrase first.
    for token in re.split(r"(?:以及|还有|或者|和|与|跟|里面|相关|有关)", cleaned):
        _append_term(candidates, token)

    return tuple(candidates[:8])


def _append_term(result: list[str], value: str) -> None:
    term = normalize_spoken_text(value).strip()
    if not term:
        return
    compact = term.replace(" ", "")
    if compact in _GENERIC_TOKENS or len(compact) < 2:
        return
    if term not in result:
        result.append(term)


TOOL_INTENT_DESCRIPTIONS: dict[str, str] = {
    "notes.resolve": (
        "解析一个可能含糊的便签目标，只定位、不修改。适用于‘刚才那条’‘那个关于包装的便签’"
        "‘标题叫客户报价的’或带明确编号的长句。只有‘编号 119’‘ID 119’‘第119号便签’才按"
        "数据库 ID 解析；单独的‘119’或‘标题叫119’必须先按标题/关键词匹配。若候选不唯一必须返回"
        " ambiguous，绝不能猜第一条；后续读取、编辑、删除或打开界面时使用返回的 note_id。"
    ),
    "notes.search": (
        "按关键词和可选标签搜索小智便签，返回有界摘要。适用于‘查便签’‘找一下王总报价’"
        "‘麻烦看看之前记的包装问题’等口语或啰嗦表达；不是文件搜索，也不是系统记事本。"
        "需要修改含糊目标时先搜索或 resolve，再使用明确 note_id。"
    ),
    "notes.list_recent": (
        "列出最近更新的活动便签。适用于‘最近几条便签’‘我刚记了什么’‘把最新五条念一下’。"
        "不要用它代替关键词搜索，也不要把置顶顺序当作最近更新时间。"
    ),
    "notes.get": (
        "按明确 note_id 读取一条便签的公开字段。适用于‘读一下编号 12’。目标只有标题或描述时先调用"
        " notes.resolve/notes.search；读取回收站内容时设置 include_deleted=true。"
    ),
    "notes.list_by_tag": (
        "按精确标签列出活动便签。适用于‘列出客户标签下的便签’‘看看会议分类’。"
        "用户只给模糊关键词而不是标签名时使用 notes.search。"
    ),
    "notes.list_deleted": (
        "列出软删除/回收站中的便签。适用于‘看看已删除便签’‘回收站里有什么’‘找回刚删的记录’。"
        "这里只读取，不自动恢复。"
    ),
    "notes.list_todos": (
        "列出带受保护标签‘待办’的活动便签。适用于‘我的待办有哪些’‘列出还要处理的便签’。"
        "PC 端待办是标签语义，不要声称存在完成状态。"
    ),
    "notes.list_pinned": ("列出活动且已置顶的便签。适用于‘有哪些置顶便签’‘把重要便签列出来’。"),
    "notes.create": (
        "在小智便签中创建普通或待办便签。适用于‘记个便签’‘新增待办’‘把下面这段记录下来’；"
        "不要调用文件或系统记事本工具。若用户未明确标题，可从主题生成简短标题，正文保留用户要求的细节，"
        "不得虚构内容。"
    ),
    "notes.append": (
        "向明确便签末尾追加内容并保留标题和标签。适用于‘在那条后面补一句’‘给编号 12 加上…’。"
        "目标含糊时先 resolve/search；用户要求整体覆盖时应使用 notes.replace_content。"
    ),
    "notes.update_title": (
        "只修改明确便签的标题，保留正文和标签。适用于‘把这条改名为…’。"
        "目标含糊时先 resolve/search；不要用它改正文。"
    ),
    "notes.replace_content": (
        "整体替换明确便签正文，属于高风险操作，始终先返回 pending confirmation。适用于‘把正文全部改成…’"
        "‘用这段覆盖原内容’；不要把普通补充误路由到这里，追加应使用 notes.append。"
    ),
    "notes.convert_type": (
        "在普通便签与待办便签之间转换，保留其他标签和正文。适用于‘把这条变成待办’"
        "‘这项不再是待办了’。目标含糊时先 resolve/search。"
    ),
    "notes.pin": (
        "置顶或取消置顶一组明确便签。适用于‘把这几条置顶’‘取消编号 3 的置顶’；pinned=true/false"
        "必须按用户意图设置，超过 5 条需要确认。"
    ),
    "notes.delete": (
        "把明确便签软删除到回收站，始终需要确认，不会永久擦除。适用于‘删掉那条便签’；"
        "目标含糊时必须先 resolve/search，不能猜测或跳过确认。"
    ),
    "notes.restore": (
        "从回收站恢复明确便签。适用于‘把刚才删的恢复’‘还原编号 8’；先用 list_deleted/resolve"
        "明确目标，超过 5 条需要确认。"
    ),
    "tags.create": (
        "创建一个自定义标签。适用于‘新建项目A标签’‘加一个会议分类’。已有标签返回幂等成功；"
        "不能创建系统分类名或受保护的待办标签。"
    ),
    "tags.search": (
        "搜索已知标签。适用于用户记不清完整标签名，如‘有没有客户相关的标签’。"
        "找到精确名称后再用于 list_by_tag、show_tag 或 tags.bind。"
    ),
    "tags.list": ("列出全部已知标签及使用/可删除信息。适用于‘有哪些标签’‘把分类列一下’。"),
    "tags.delete": (
        "删除未被使用的自定义标签，始终需要确认。适用于‘删掉空的测试标签’；"
        "不会修改任何便签，受保护、系统或仍在使用的标签必须拒绝。"
    ),
    "tags.bind": (
        "原子地给明确便签添加、移除或替换标签。适用于‘给这两条加客户标签’‘移除会议标签’"
        "‘标签全部改成A和B’。replace 始终确认，add/remove 超过 5 条确认；目标含糊时先 resolve/search。"
    ),
    "ui.open_note": (
        "在桌面界面打开并选中一个明确的活动便签。适用于‘打开编号 12’‘把刚找到的那条展示出来’。"
        "只负责导航；目标含糊时先 resolve，已删除便签应先恢复或打开回收站。"
    ),
    "ui.show_search": (
        "打开并聚焦桌面搜索界面，可预填 query。适用于‘在界面里搜索包装’‘把搜索框打开’。"
        "需要返回搜索结果数据时同时或优先使用 notes.search。"
    ),
    "ui.show_note_list": ("让桌面界面回到全部活动便签列表。适用于‘回到全部便签’‘返回主页列表’。"),
    "ui.show_tag": (
        "在桌面界面打开一个精确标签分类。适用于‘打开客户标签页’。标签名不确定时先 tags.search/list。"
    ),
    "ui.show_trash": ("在桌面界面打开已删除/回收站页面。适用于‘打开回收站’‘看看删除的便签’。"),
    "ui.show_pinned": ("在桌面界面打开置顶便签视图。适用于‘切到置顶列表’‘显示重要便签’。"),
    "ui.show_todos": (
        "在桌面界面打开待办便签视图。适用于‘切到待办列表’‘只看还要处理的便签’。"
        "PC 待办使用受保护标签‘待办’，不是完成状态筛选。"
    ),
    "ui.show_confirmation": (
        "在桌面界面展示一个已存在的 pending confirmation。通常在高风险工具返回 confirmation_id 后调用；"
        "没有有效 id 时不得伪造或展示旧确认。"
    ),
    "assistant.confirm": (
        "执行一个有效 pending confirmation，只能使用真实 confirmation_id。用户只说‘确认’‘就这么做’时，"
        "先调用 assistant.list_pending_confirmations；若恰好一个再确认，多个时必须让用户选择。"
    ),
    "assistant.reject": (
        "拒绝并消费一个 pending confirmation，保证零写入。用户说‘取消’‘别改了’时先确定对应"
        " confirmation_id；多个 pending 时不能猜。"
    ),
    "assistant.list_pending_confirmations": (
        "列出当前会话可用的安全确认摘要。适用于用户只说‘确认/取消’但没有 id，或询问‘还有哪些操作等确认’。"
        "只返回安全摘要，不暴露正文或原始参数。"
    ),
}


def intent_description(tool_name: str, fallback: str) -> str:
    """Return the frozen routing description for one tool."""

    return TOOL_INTENT_DESCRIPTIONS.get(tool_name, fallback)


__all__ = [
    "TOOL_INTENT_DESCRIPTIONS",
    "extract_explicit_note_id",
    "extract_search_terms",
    "intent_description",
    "is_contextual_reference",
    "normalize_spoken_text",
]

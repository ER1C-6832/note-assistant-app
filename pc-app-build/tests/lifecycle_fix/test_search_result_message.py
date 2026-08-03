from types import SimpleNamespace

from app.assistant.mcp.gate5_1_executor import _search_result_message


def test_empty_search_result_is_explicit() -> None:
    assert _search_result_message("王总报价", ()) == "没有找到与“王总报价”匹配的便签"


def test_search_result_lists_titles() -> None:
    notes = (
        SimpleNamespace(title="王总屏幕报价"),
        SimpleNamespace(title="联系王总"),
    )
    assert _search_result_message("王总", notes) == "找到2条便签：王总屏幕报价、联系王总"

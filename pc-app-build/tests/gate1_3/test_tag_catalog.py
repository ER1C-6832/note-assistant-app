from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.notes.tag_catalog import (
    DEFAULT_TAGS,
    TagCatalog,
    TagCatalogFormatError,
    TagInUseError,
    TagValidationError,
)


def test_missing_catalog_is_seeded_with_defaults(tmp_path: Path) -> None:
    path = tmp_path / "data" / "custom_tags.json"
    catalog = TagCatalog(path)

    assert catalog.load() == DEFAULT_TAGS
    assert json.loads(path.read_text(encoding="utf-8")) == list(DEFAULT_TAGS)


def test_existing_catalog_is_normalized_and_protected_names_are_removed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "custom_tags.json"
    path.write_text(
        json.dumps([" 客户 ", "客户", "待办", "全部", "新标签"], ensure_ascii=False),
        encoding="utf-8",
    )

    catalog = TagCatalog(path)
    assert catalog.load() == ("客户", "新标签")
    assert json.loads(path.read_text(encoding="utf-8")) == ["客户", "新标签"]


def test_add_rejects_empty_protected_and_system_names(tmp_path: Path) -> None:
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=())
    catalog.load()

    with pytest.raises(TagValidationError):
        catalog.add("  ")
    with pytest.raises(TagValidationError):
        catalog.add("待办")
    with pytest.raises(TagValidationError):
        catalog.add("已删除")


def test_add_and_observe_persist_only_new_exact_tags(tmp_path: Path) -> None:
    path = tmp_path / "tags.json"
    catalog = TagCatalog(path, default_tags=())
    catalog.load()

    assert catalog.add("客户") is True
    assert catalog.add(" 客户 ") is False
    assert catalog.observe(["客户", "客户服务", "待办", "新增"]) == (
        "客户服务",
        "新增",
    )
    assert catalog.custom_tags == ("客户", "客户服务", "新增")

    reloaded = TagCatalog(path, default_tags=())
    assert reloaded.load() == ("客户", "客户服务", "新增")


def test_delete_uses_exact_usage_and_blocks_referenced_tag(tmp_path: Path) -> None:
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=("客户", "客户服务"))
    catalog.load()

    with pytest.raises(TagInUseError):
        catalog.delete("客户", used_tags=("客户",))

    assert catalog.delete("客户", used_tags=("客户服务",)) is True
    assert catalog.custom_tags == ("客户服务",)


def test_default_tag_deletion_remains_deleted_after_reload(tmp_path: Path) -> None:
    path = tmp_path / "tags.json"
    catalog = TagCatalog(path, default_tags=("客户", "跟进"))
    catalog.load()
    assert catalog.delete("客户", used_tags=()) is True

    reloaded = TagCatalog(path, default_tags=("客户", "跟进"))
    assert reloaded.load() == ("跟进",)


def test_items_report_exact_usage_and_deletability(tmp_path: Path) -> None:
    catalog = TagCatalog(tmp_path / "tags.json", default_tags=("客户", "客户服务"))
    catalog.load()

    items = catalog.items(used_tags=("客户服务",))
    assert [(item.name, item.deletable, item.in_use) for item in items] == [
        ("客户", True, False),
        ("客户服务", False, True),
    ]


def test_malformed_catalog_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "tags.json"
    original = '{"not": "a list"}'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(TagCatalogFormatError):
        TagCatalog(path).load()

    assert path.read_text(encoding="utf-8") == original

"""Persistent user tag catalog independent from Qt and database sessions."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TAGS = (
    "客户",
    "报价",
    "屏幕",
    "样机",
    "游戏手柄",
    "测试",
    "包装",
    "跟进",
)
PROTECTED_TAGS = frozenset({"待办"})
SYSTEM_CATEGORY_NAMES = frozenset({"全部", "置顶", "已删除"})


class TagCatalogError(RuntimeError):
    pass


class TagValidationError(TagCatalogError):
    pass


class TagCatalogFormatError(TagCatalogError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"invalid tag catalog {path}: {reason}")


class TagInUseError(TagCatalogError):
    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(f"tag is still referenced by notes: {tag}")


@dataclass(frozen=True, slots=True)
class TagCatalogItem:
    name: str
    deletable: bool
    protected: bool
    in_use: bool


class TagCatalog:
    def __init__(
        self,
        path: str | Path,
        *,
        default_tags: Iterable[str] = DEFAULT_TAGS,
        protected_tags: Iterable[str] = PROTECTED_TAGS,
        system_names: Iterable[str] = SYSTEM_CATEGORY_NAMES,
    ) -> None:
        self._path = Path(path).expanduser().resolve()
        self._default_tags = _normalize_tags(default_tags)
        self._protected_tags = frozenset(_normalize_tags(protected_tags))
        self._system_names = frozenset(_normalize_tags(system_names))
        self._custom_tags: tuple[str, ...] | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def protected_tags(self) -> frozenset[str]:
        return self._protected_tags

    @property
    def custom_tags(self) -> tuple[str, ...]:
        self._ensure_loaded()
        assert self._custom_tags is not None
        return self._custom_tags

    def load(self) -> tuple[str, ...]:
        if not self._path.exists():
            self._custom_tags = self._filter_allowed(self._default_tags)
            self._persist()
            return self._custom_tags

        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TagCatalogFormatError(self._path, str(exc)) from exc
        if not isinstance(value, list):
            raise TagCatalogFormatError(self._path, "root JSON value must be an array")
        if any(not isinstance(item, str) for item in value):
            raise TagCatalogFormatError(self._path, "every tag must be a string")

        normalized = self._filter_allowed(_normalize_tags(value))
        self._custom_tags = normalized
        if list(normalized) != value:
            self._persist()
        return normalized

    def add(self, tag: str) -> bool:
        clean_tag = self._validate_user_tag(tag)
        current = list(self.custom_tags)
        if clean_tag in current:
            return False
        current.append(clean_tag)
        self._custom_tags = tuple(current)
        self._persist()
        return True

    def observe(self, tags: Iterable[str]) -> tuple[str, ...]:
        additions: list[str] = []
        current = list(self.custom_tags)
        known = set(current)
        for tag in _normalize_tags(tags):
            if tag in self._protected_tags or tag in self._system_names or tag in known:
                continue
            known.add(tag)
            current.append(tag)
            additions.append(tag)
        if additions:
            self._custom_tags = tuple(current)
            self._persist()
        return tuple(additions)

    def delete(self, tag: str, *, used_tags: Iterable[str]) -> bool:
        clean_tag = _normalize_single_tag(tag)
        if clean_tag in self._protected_tags:
            raise TagValidationError(f"protected tag cannot be deleted: {clean_tag}")
        if clean_tag in self._system_names:
            raise TagValidationError(
                f"system category is not a custom tag: {clean_tag}"
            )

        used = frozenset(_normalize_tags(used_tags))
        if clean_tag in used:
            raise TagInUseError(clean_tag)

        current = list(self.custom_tags)
        if clean_tag not in current:
            return False
        current.remove(clean_tag)
        self._custom_tags = tuple(current)
        self._persist()
        return True

    def is_deletable(self, tag: str, *, used_tags: Iterable[str]) -> bool:
        clean_tag = _normalize_single_tag(tag)
        return (
            clean_tag in self.custom_tags
            and clean_tag not in self._protected_tags
            and clean_tag not in self._system_names
            and clean_tag not in frozenset(_normalize_tags(used_tags))
        )

    def items(self, *, used_tags: Iterable[str]) -> tuple[TagCatalogItem, ...]:
        used = frozenset(_normalize_tags(used_tags))
        return tuple(
            TagCatalogItem(
                name=tag,
                deletable=tag not in used,
                protected=False,
                in_use=tag in used,
            )
            for tag in self.custom_tags
        )

    def _validate_user_tag(self, tag: str) -> str:
        clean_tag = _normalize_single_tag(tag)
        if clean_tag in self._protected_tags:
            raise TagValidationError(
                f"protected tag cannot be added as custom: {clean_tag}"
            )
        if clean_tag in self._system_names:
            raise TagValidationError(
                f"system category name cannot be used as a tag: {clean_tag}"
            )
        return clean_tag

    def _filter_allowed(self, tags: Iterable[str]) -> tuple[str, ...]:
        return tuple(
            tag
            for tag in tags
            if tag not in self._protected_tags and tag not in self._system_names
        )

    def _ensure_loaded(self) -> None:
        if self._custom_tags is None:
            self.load()

    def _persist(self) -> None:
        assert self._custom_tags is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.tmp")
        temporary.write_text(
            json.dumps(list(self._custom_tags), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._path)


def _normalize_single_tag(value: str) -> str:
    tag = str(value).strip()
    if not tag:
        raise TagValidationError("tag must not be empty")
    return tag


def _normalize_tags(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = str(value).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return tuple(result)

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


def create_legacy_database(
    path: Path,
    *,
    note_titles: tuple[str, ...] = ("legacy note",),
    include_source: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source_column = ", source VARCHAR(50) NOT NULL DEFAULT 'manual'" if include_source else ""

    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                is_pinned BOOLEAN NOT NULL DEFAULT 0,
                is_deleted BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
                {source_column}
            )
            """)

        for index, title in enumerate(note_titles, start=1):
            columns = "id, title, content, tags, is_pinned, " "is_deleted, created_at, updated_at"
            values = [
                index,
                title,
                f"content {index}",
                '["客户"]',
                0,
                0,
                "2026-07-14 00:00:00",
                "2026-07-14 00:00:00",
            ]

            if include_source:
                columns += ", source"
                values.append("manual")

            placeholders = ", ".join("?" for _ in values)
            connection.execute(
                f"INSERT INTO notes ({columns}) VALUES ({placeholders})",
                values,
            )

        connection.commit()

"""Whole wiki pages stored as prose, for reference content that has no schema.

Entity pages (items, monsters, quests) parse into typed columns because they
carry an infobox. Reference pages — game mechanics, calculators, guides — do
not, so they are kept intact: `wikitext` is the raw source and `text` is the
same content with links, templates and emphasis stripped.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_COLUMNS = "id, title, source, wikitext, text"


@dataclass
class WikiPage:
    id: int
    title: str
    source: str
    wikitext: str
    text: str

    @classmethod
    def by_title(cls, conn: sqlite3.Connection, title: str) -> WikiPage | None:
        row = conn.execute(f"SELECT {_COLUMNS} FROM wiki_pages WHERE title = ?", (title,)).fetchone()
        return cls(*row) if row else None

    @classmethod
    def search(cls, conn: sqlite3.Connection, title: str, source: str | None = None) -> list[WikiPage]:
        """Partial match on page title."""
        sql = f"SELECT {_COLUMNS} FROM wiki_pages WHERE title LIKE ?"
        params: list[str] = [f"%{title}%"]
        if source:
            sql += " AND source = ?"
            params.append(source)
        return [cls(*r) for r in conn.execute(sql + " ORDER BY title", params)]

    @classmethod
    def search_text(cls, conn: sqlite3.Connection, query: str, source: str | None = None) -> list[WikiPage]:
        """Partial match on page body, searching the markup-stripped text."""
        sql = f"SELECT {_COLUMNS} FROM wiki_pages WHERE text LIKE ?"
        params: list[str] = [f"%{query}%"]
        if source:
            sql += " AND source = ?"
            params.append(source)
        return [cls(*r) for r in conn.execute(sql + " ORDER BY title", params)]

    @classmethod
    def all(cls, conn: sqlite3.Connection, source: str | None = None) -> list[WikiPage]:
        sql = f"SELECT {_COLUMNS} FROM wiki_pages"
        params: list[str] = []
        if source:
            sql += " WHERE source = ?"
            params.append(source)
        return [cls(*r) for r in conn.execute(sql + " ORDER BY title", params)]

    @classmethod
    def titles(cls, conn: sqlite3.Connection, source: str | None = None) -> list[str]:
        """Page titles only — avoids loading every page body just to enumerate."""
        sql = "SELECT title FROM wiki_pages"
        params: list[str] = []
        if source:
            sql += " WHERE source = ?"
            params.append(source)
        return [r[0] for r in conn.execute(sql + " ORDER BY title", params)]

    @classmethod
    def sources(cls, conn: sqlite3.Connection) -> list[str]:
        """Distinct category names that have been ingested."""
        return [r[0] for r in conn.execute("SELECT DISTINCT source FROM wiki_pages ORDER BY source")]

"""RuneLite Plugin Hub plugin sources, stored whole for local code search.

Hub plugins are working examples of reading live game state — varbits, object
IDs, animations — that neither the wiki nor the cache documents. Searching
their sources answers questions like "which plugins read this varbit?" without
leaving the database. `repository` and `commit_hash` record where each source
snapshot came from.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_PLUGIN_COLUMNS = "id, internal_name, repository, commit_hash"
_FILE_COLUMNS = "id, plugin_id, file_name, content"


@dataclass
class HubPlugin:
    id: int
    internal_name: str
    repository: str
    commit_hash: str

    @classmethod
    def by_name(cls, conn: sqlite3.Connection, internal_name: str) -> HubPlugin | None:
        row = conn.execute(
            f"SELECT {_PLUGIN_COLUMNS} FROM hub_plugins WHERE internal_name = ?", (internal_name,)
        ).fetchone()
        return cls(*row) if row else None

    @classmethod
    def search(cls, conn: sqlite3.Connection, name: str) -> list[HubPlugin]:
        """Partial match on internal name."""
        return [
            cls(*r)
            for r in conn.execute(
                f"SELECT {_PLUGIN_COLUMNS} FROM hub_plugins WHERE internal_name LIKE ? ORDER BY internal_name",
                (f"%{name}%",),
            )
        ]

    @classmethod
    def all(cls, conn: sqlite3.Connection) -> list[HubPlugin]:
        return [
            cls(*r)
            for r in conn.execute(f"SELECT {_PLUGIN_COLUMNS} FROM hub_plugins ORDER BY internal_name")
        ]

    @classmethod
    def names(cls, conn: sqlite3.Connection) -> list[str]:
        """Internal names only — avoids loading rows just to enumerate."""
        return [r[0] for r in conn.execute("SELECT internal_name FROM hub_plugins ORDER BY internal_name")]

    def files(self, conn: sqlite3.Connection) -> list[HubPluginFile]:
        return [
            HubPluginFile(*r)
            for r in conn.execute(
                f"SELECT {_FILE_COLUMNS} FROM hub_plugin_files WHERE plugin_id = ? ORDER BY file_name",
                (self.id,),
            )
        ]


@dataclass
class HubPluginFile:
    id: int
    plugin_id: int
    file_name: str
    content: str

    @classmethod
    def by_file(cls, conn: sqlite3.Connection, internal_name: str, file_name: str) -> HubPluginFile | None:
        row = conn.execute(
            f"""SELECT {_prefixed(_FILE_COLUMNS, "f")} FROM hub_plugin_files f
                JOIN hub_plugins p ON p.id = f.plugin_id
                WHERE p.internal_name = ? AND f.file_name = ?""",
            (internal_name, file_name),
        ).fetchone()
        return cls(*row) if row else None

    @classmethod
    def search_code(cls, conn: sqlite3.Connection, query: str, limit: int = 100) -> list[CodeMatch]:
        """Files whose source contains the substring, with their owning plugin.

        Case-sensitive substring match. Common identifiers match thousands of
        files, so results are capped by `limit`.
        """
        return [
            CodeMatch(HubPlugin(*r[:4]), cls(*r[4:]))
            for r in conn.execute(
                f"""SELECT {_prefixed(_PLUGIN_COLUMNS, "p")}, {_prefixed(_FILE_COLUMNS, "f")}
                    FROM hub_plugin_files f
                    JOIN hub_plugins p ON p.id = f.plugin_id
                    WHERE f.content LIKE '%' || ? || '%'
                    ORDER BY p.internal_name, f.file_name
                    LIMIT ?""",
                (query, limit),
            )
        ]


@dataclass
class CodeMatch:
    plugin: HubPlugin
    file: HubPluginFile


def _prefixed(columns: str, alias: str) -> str:
    return ", ".join(f"{alias}.{column.strip()}" for column in columns.split(","))

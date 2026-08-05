"""Import RuneLite Plugin Hub plugin sources from the pluginhub-searcher bundles.

The JZomDev/pluginhub-searcher repository republishes every Plugin Hub plugin's
Java sources as gzipped JSON bundles (plugins_0.json.gz, plugins_1.json.gz, ...),
kept current by automation as hub plugins update. Each bundle holds ~100 plugins:
internal name, source repository URL, the commit the sources were taken from, and
the .java files themselves. Importing them makes the whole hub corpus searchable
locally — "which plugins read this varbit?" becomes a query against
hub_plugin_files instead of a GitHub code search.
"""

import argparse
import gzip
import json
import urllib.request
from pathlib import Path

from ragger.db import create_tables, get_connection

BUNDLE_LIST_URL = "https://api.github.com/repos/JZomDev/pluginhub-searcher/contents/plugins"
BUNDLE_BASE_URL = "https://raw.githubusercontent.com/JZomDev/pluginhub-searcher/main/plugins/"

USER_AGENT = "ragger/0.2 (https://github.com/iamacoffeepot/ragger) OSRS Leagues planner"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return response.read()


def list_bundle_names() -> list[str]:
    """Enumerate the bundle files instead of hardcoding a count, since the split grows over time."""
    listing = json.loads(fetch(BUNDLE_LIST_URL))
    names = [entry["name"] for entry in listing if entry["name"].endswith(".json.gz")]
    return sorted(names)


def ingest(db_path: Path) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    existing = {
        name: (row_id, commit)
        for row_id, name, commit in conn.execute("SELECT id, internal_name, commit_hash FROM hub_plugins")
    }

    bundle_names = list_bundle_names()
    seen: set[str] = set()
    inserted = 0
    updated = 0
    skipped = 0
    file_count = 0

    for index, bundle_name in enumerate(bundle_names, start=1):
        plugins = json.loads(gzip.decompress(fetch(BUNDLE_BASE_URL + bundle_name)))
        print(f"[{index}/{len(bundle_names)}] {bundle_name}: {len(plugins)} plugins")

        for plugin in plugins:
            name = plugin["internalName"]
            commit = plugin["commit"]
            seen.add(name)

            if name in existing and existing[name][1] == commit:
                skipped += 1
                continue

            # Upsert keeps the row id stable so hub_plugin_files rows can cascade
            # from it; INSERT OR REPLACE would delete and re-insert with a new id.
            conn.execute(
                """INSERT INTO hub_plugins (internal_name, repository, commit_hash) VALUES (?, ?, ?)
                   ON CONFLICT(internal_name) DO UPDATE SET
                       repository = excluded.repository,
                       commit_hash = excluded.commit_hash""",
                (name, plugin["repository"], commit),
            )

            plugin_id = conn.execute(
                "SELECT id FROM hub_plugins WHERE internal_name = ?", (name,)
            ).fetchone()[0]

            # Delete-then-insert rather than upsert: a new commit can remove files,
            # and stale rows would otherwise linger.
            conn.execute("DELETE FROM hub_plugin_files WHERE plugin_id = ?", (plugin_id,))
            files = plugin.get("files") or []
            conn.executemany(
                "INSERT OR IGNORE INTO hub_plugin_files (plugin_id, file_name, content) VALUES (?, ?, ?)",
                [(plugin_id, f["fileName"], f.get("content", "")) for f in files],
            )

            file_count += len(files)

            if name in existing:
                updated += 1
            else:
                inserted += 1

    # Plugins gone from every bundle have been delisted from the hub; the cascade
    # removes their files.
    removed = 0
    for name in existing:
        if name not in seen:
            conn.execute("DELETE FROM hub_plugins WHERE internal_name = ?", (name,))
            removed += 1

    conn.commit()

    total_files = conn.execute("SELECT COUNT(*) FROM hub_plugin_files").fetchone()[0]
    print(
        f"Imported {len(seen)} hub plugins into {db_path} — "
        f"{inserted} new, {updated} updated ({file_count} files written), "
        f"{skipped} unchanged, {removed} delisted; {total_files} files total"
    )
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Plugin Hub plugin sources into the database")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    args = parser.parse_args()
    ingest(args.db)

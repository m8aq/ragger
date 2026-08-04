"""Import observed NPC spawn points from mejrs/data_osrs.

`fetch_npc_locations.py` parses coordinates out of Infobox NPC, which only
records the handful of spots an editor thought worth writing down — about 5,600
across the game, all implicitly on the ground floor. This data set is observed
from the live game instead: every spawn point, including the upper floors of
buildings, with the NPC's combat level and menu actions.

Rows are tagged `source = 'data_osrs'` so wiki-stated and observed spawns stay
tellable apart; `fetch_npc_locations.py` writes `source = 'wiki'`. Uniqueness is
on (game_id, x, y, plane), so a spawn both sources agree on is stored once and
keeps whichever ran first.

Source: https://github.com/mejrs/data_osrs (no licence declared upstream — fine
for local use; ask before redistributing inside a published database).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from ragger.db import create_tables, get_connection

# Pinned so a build is reproducible; bump deliberately, not implicitly.
DATA_OSRS_COMMIT = "6a3ca6f19d65"
RAW_URL = "https://raw.githubusercontent.com/mejrs/data_osrs/{commit}/{name}"

NPC_FILE = "NPCList_OSRS.json"
DEFAULT_CACHE_DIR = Path("data/data-osrs")


def download(name: str, cache_dir: Path) -> list[dict]:
    """Fetch one pinned data file, caching it under `cache_dir`."""
    path = cache_dir / name
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Downloading {name} @ {DATA_OSRS_COMMIT}...")
        urllib.request.urlretrieve(RAW_URL.format(commit=DATA_OSRS_COMMIT, name=name), path)
    return json.loads(path.read_text())


def ingest(db_path: Path, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    before = conn.execute("SELECT COUNT(*) FROM npc_locations").fetchone()[0]
    spawns = download(NPC_FILE, cache_dir)
    print(f"{len(spawns)} observed spawn points")

    skipped = 0
    for entry in spawns:
        name = entry.get("name")
        if not name or name == "null":
            skipped += 1
            continue

        conn.execute(
            """INSERT OR IGNORE INTO npc_locations
               (game_id, name, x, y, plane, source, combat_level)
               VALUES (?, ?, ?, ?, ?, 'data_osrs', ?)""",
            (entry["id"], name, entry["x"], entry["y"], entry["p"],
             entry.get("combatLevel") or None),
        )

    conn.execute(
        "INSERT INTO attributions (table_name, wiki_page, authors, fetched_at)"
        " VALUES (?, ?, ?, datetime('now'))",
        ("npc_locations", f"mejrs/data_osrs@{DATA_OSRS_COMMIT}", "mejrs"),
    )
    conn.commit()

    after = conn.execute("SELECT COUNT(*) FROM npc_locations").fetchone()[0]
    by_plane = dict(conn.execute(
        "SELECT plane, COUNT(*) FROM npc_locations WHERE source = 'data_osrs' GROUP BY plane"
    ))
    print(f"Added {after - before} spawns ({before} -> {after} total)")
    print(f"  by plane: {by_plane}")
    if skipped:
        print(f"  skipped {skipped} entries with no name")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import observed NPC spawns from mejrs/data_osrs")
    parser.add_argument("--db", type=Path, default=Path("data/ragger.db"))
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()
    ingest(args.db, args.cache_dir)

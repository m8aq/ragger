"""Import observed game-object transports and item teleports from mejrs/data_osrs.

The wiki describes travel in prose, so `map_links` only carries what a fetch
script could parse out of it — 245 dungeon entrances for the whole game. This
data set is observed instead: each entry records a game object players actually
interacted with, the tile they stood on, and the tiles they ended up at, with an
observation count. That fills the largest gap in our navigation graph.

Two safeguards, because this is third-party data:

* Every transport is cross-checked against our own cache-dumped `object_locations`
  — the object id must exist and have a spawn near the claimed start tile.
  Roughly 18% fail that check and are counted and reported, never silently dropped.
* The download is pinned to an upstream commit, so a force-push cannot change
  what a build ingests.

All four planes are imported. Each link records the plane of both endpoints, so
a staircase from a shop floor to the room above is a single link between two
blobs on different planes — the pathfinder needs no special case for it, because
travel between blobs already goes through map_links.

Source: https://github.com/mejrs/data_osrs (no licence declared upstream — fine
for local use; ask before redistributing inside a published database).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

from ragger.db import create_tables, get_connection
from ragger.enums import MapLinkType

# Pinned so a build is reproducible; bump deliberately, not implicitly.
DATA_OSRS_COMMIT = "6a3ca6f19d65"
RAW_URL = "https://raw.githubusercontent.com/mejrs/data_osrs/{commit}/{name}"

TRANSPORT_FILE = "transports_osrs.json"
TELEPORT_FILES = ("teleports_osrs.json", "osrs_spheres.json")

DEFAULT_CACHE_DIR = Path("data/data-osrs")

# A transport's object must have a spawn within this many tiles of the claimed
# start tile. Object spawns are recorded at their south-west corner while the
# observed start tile is wherever the player stood, so exact equality is wrong.
SPAWN_MATCH_RADIUS = 5

# Destinations closer together than this are landing scatter for one exit and
# collapse to a single link. Beyond it they are genuinely different places: a few
# hub objects lead thousands of tiles apart.
DESTINATION_CLUSTER_RADIUS = 32


def download(name: str, cache_dir: Path) -> list[dict]:
    """Fetch one pinned data file, caching it under `cache_dir`."""
    path = cache_dir / name
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        url = RAW_URL.format(commit=DATA_OSRS_COMMIT, name=name)
        print(f"  Downloading {name} @ {DATA_OSRS_COMMIT}...")
        urllib.request.urlretrieve(url, path)
    return json.loads(path.read_text())


def load_object_spawns(conn) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Spawn tiles for every interactive object, keyed by (game id, plane)."""
    spawns: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for game_id, x, y, plane in conn.execute(
        "SELECT game_id, x, y, plane FROM object_locations"
    ):
        spawns[(game_id, plane)].append((x, y))
    return spawns


def has_nearby_spawn(entry: dict, spawns: dict[tuple[int, int], list[tuple[int, int]]]) -> bool:
    """True if we independently observed this object near the claimed start tile.

    Matched on the start tile's own plane: the same object id appears on several
    floors, and a ladder on the ground floor is not evidence for one upstairs.
    """
    start_x, start_y = entry["start"]["x"], entry["start"]["y"]
    return any(
        abs(x - start_x) <= SPAWN_MATCH_RADIUS and abs(y - start_y) <= SPAWN_MATCH_RADIUS
        for x, y in spawns.get((entry["id"], entry["start"]["p"]), ())
    )


def cluster_destinations(destinations: list[dict]) -> list[tuple[int, int, int]]:
    """Collapse landing scatter into one representative tile per distinct place.

    Single-linkage on Chebyshev distance, within a plane: a destination joins a
    cluster if it is within `DESTINATION_CLUSTER_RADIUS` of any member on the
    same floor. Two tiles at the same x,y on different planes are different
    places. The representative is the first tile seen, which is the most
    frequently observed one upstream.
    """
    clusters: list[list[tuple[int, int, int]]] = []
    for d in destinations:
        tile = (d["x"], d["y"], d["p"])
        for cluster in clusters:
            if any(tile[2] == cp and max(abs(tile[0] - cx), abs(tile[1] - cy)) <= DESTINATION_CLUSTER_RADIUS
                   for cx, cy, cp in cluster):
                cluster.append(tile)
                break
        else:
            clusters.append([tile])
    return [cluster[0] for cluster in clusters]


def ingest(db_path: Path, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    spawns = load_object_spawns(conn)
    if not spawns:
        raise ValueError(
            "No object_locations rows. Run scripts/import/import_object_locations.py first — "
            "transports are validated against them."
        )

    transports = download(TRANSPORT_FILE, cache_dir)
    teleports = [e for name in TELEPORT_FILES for e in download(name, cache_dir)]

    candidates = transports

    unverified = 0
    self_links = 0
    transport_links = 0
    for entry in candidates:
        if not has_nearby_spawn(entry, spawns):
            unverified += 1
            continue

        start_x, start_y = entry["start"]["x"], entry["start"]["y"]
        start_plane = entry["start"]["p"]
        target = entry.get("menuTarget") or "object"
        option = entry.get("menuOption") or "Use"
        description = f"{option}: {target}"

        for dest_x, dest_y, dest_plane in cluster_destinations(entry["destinations"]):
            # A destination equal to the start is an observation artefact — the
            # player was seen standing where they ended up. It carries no travel.
            if (dest_x, dest_y, dest_plane) == (start_x, start_y, start_plane):
                self_links += 1
                continue

            conn.execute(
                """INSERT OR IGNORE INTO map_links
                   (src_location, dst_location, src_x, src_y, dst_x, dst_y,
                    type, description, src_plane, dst_plane)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (target, target, start_x, start_y, dest_x, dest_y,
                 MapLinkType.OBJECT_TRANSPORT.value, description, start_plane, dest_plane),
            )
            transport_links += 1

    teleport_links = 0
    for entry in teleports:
        target = entry.get("menuTarget") or entry.get("menuOption") or "teleport"
        description = f"{entry.get('menuOption', 'Teleport')}: {target}"

        for dest_x, dest_y, dest_plane in cluster_destinations(entry["destinations"]):
            # No source tile: item teleports work from anywhere, which find_path
            # already models for spellbook teleports.
            conn.execute(
                """INSERT OR IGNORE INTO map_links
                   (src_location, dst_location, src_x, src_y, dst_x, dst_y,
                    type, description, src_plane, dst_plane)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Anywhere", target, None, None, dest_x, dest_y,
                 MapLinkType.TELEPORT.value, description, 0, dest_plane),
            )
            teleport_links += 1

    conn.execute(
        "INSERT INTO attributions (table_name, wiki_page, authors, fetched_at)"
        " VALUES (?, ?, ?, datetime('now'))",
        ("map_links", f"mejrs/data_osrs@{DATA_OSRS_COMMIT}", "mejrs"),
    )
    conn.commit()

    print(f"Inserted {transport_links} object transports, {teleport_links} item teleports")
    print(f"  skipped {unverified} transports with no matching object spawn within"
          f" {SPAWN_MATCH_RADIUS} tiles")
    print(f"  skipped {self_links} destinations identical to their start tile")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import observed transports from mejrs/data_osrs")
    parser.add_argument("--db", type=Path, default=Path("data/ragger.db"))
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR,
                        help="Where the pinned JSON files are cached")
    args = parser.parse_args()
    ingest(args.db, args.cache_dir)

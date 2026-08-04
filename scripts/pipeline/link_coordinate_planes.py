"""Resolve the plane of coordinates that were stored without one.

`facilities` and `monster_locations` carry a tile but no floor, so a bank on a
building's first storey and one on the ground are indistinguishable. Two thirds
of facility coordinates land on a tile that is blocked at ground level, which is
the symptom of exactly that.

Each table gets its plane from the best available evidence:

* facilities  -> `object_locations`, dumped from the game cache and already
  plane-aware. A bank is an object, so the objects standing on or beside the
  facility tile say which floor it is on. No third-party data involved.
* monster_locations -> observed NPC spawns in `npc_locations` (which includes
  the mejrs data_osrs import), matched on name *and* proximity. Matching on
  name alone would be wrong for anything appearing on several floors.

Rows that cannot be resolved keep plane 0 and leave `plane_source` NULL, so an
assumption is never recorded as a fact. Query `plane_source IS NOT NULL` when
the distinction matters.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from ragger.db import create_tables, get_connection

# How far from a facility tile to look for an object that identifies its floor.
# Facility coordinates are wiki-stated and land on or beside the object itself.
FACILITY_RADIUS = 3

# How far a recorded monster coordinate may sit from an observed spawn of the
# same name and still be treated as the same place. Wiki coordinates point at
# an area rather than a tile, so this is deliberately loose.
MONSTER_RADIUS = 10


def resolve_facilities(conn) -> tuple[int, int]:
    """Set facility planes from nearby cache-dumped objects."""
    objects: dict[tuple[int, int], set[int]] = defaultdict(set)
    for x, y, plane in conn.execute("SELECT x, y, plane FROM object_locations"):
        objects[(x, y)].add(plane)

    rows = conn.execute("SELECT id, x, y FROM facilities WHERE x IS NOT NULL").fetchall()
    updates: list[tuple[int, str, int]] = []

    for fid, fx, fy in rows:
        planes: set[int] = set()
        for dx in range(-FACILITY_RADIUS, FACILITY_RADIUS + 1):
            for dy in range(-FACILITY_RADIUS, FACILITY_RADIUS + 1):
                planes |= objects.get((fx + dx, fy + dy), set())

        # Only act when the surrounding objects agree. A tile with objects on
        # two floors — a staircase landing, say — cannot be resolved this way,
        # and guessing would be worse than leaving it unmarked.
        if len(planes) == 1:
            updates.append((planes.pop(), "object_locations", fid))

    conn.executemany(
        "UPDATE facilities SET plane = ?, plane_source = ? WHERE id = ?", updates,
    )
    return len(updates), len(rows)


def resolve_monster_locations(conn) -> tuple[int, int]:
    """Set monster planes from observed NPC spawns of the same name nearby."""
    spawns: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for name, x, y, plane in conn.execute(
        "SELECT name, x, y, plane FROM npc_locations"
    ):
        spawns[name].append((x, y, plane))

    rows = conn.execute(
        """SELECT ml.id, ml.x, ml.y, m.name
           FROM monster_locations ml JOIN monsters m ON m.id = ml.monster_id
           WHERE ml.x IS NOT NULL""",
    ).fetchall()

    updates: list[tuple[int, str, int]] = []
    for mid, mx, my, name in rows:
        candidates = spawns.get(name)
        if not candidates:
            continue

        near = [
            (max(abs(x - mx), abs(y - my)), plane)
            for x, y, plane in candidates
            if abs(x - mx) <= MONSTER_RADIUS and abs(y - my) <= MONSTER_RADIUS
        ]
        if not near:
            continue

        # Closest observed spawn wins. Ties on distance across different floors
        # are genuinely ambiguous, so they are left unresolved.
        near.sort()
        best_distance = near[0][0]
        tied = {plane for distance, plane in near if distance == best_distance}
        if len(tied) == 1:
            updates.append((tied.pop(), "npc_locations", mid))

    conn.executemany(
        "UPDATE monster_locations SET plane = ?, plane_source = ? WHERE id = ?", updates,
    )
    return len(updates), len(rows)


def ingest(db_path: Path) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    resolved, total = resolve_facilities(conn)
    print(f"facilities       : resolved {resolved}/{total} planes from object_locations")

    resolved, total = resolve_monster_locations(conn)
    print(f"monster_locations: resolved {resolved}/{total} planes from npc_locations")

    conn.commit()

    for table in ("facilities", "monster_locations"):
        breakdown = dict(conn.execute(
            f"SELECT plane, COUNT(*) FROM {table} WHERE plane_source IS NOT NULL GROUP BY plane"
        ))
        unresolved = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE plane_source IS NULL AND x IS NOT NULL"
        ).fetchone()[0]
        print(f"  {table}: known planes {breakdown}, {unresolved} still assumed plane 0")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resolve planes for coordinates stored without one")
    parser.add_argument("--db", type=Path, default=Path("data/ragger.db"))
    args = parser.parse_args()
    ingest(args.db)

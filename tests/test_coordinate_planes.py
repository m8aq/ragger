"""Plane resolution for coordinates that were stored without one.

`facilities` and `monster_locations` record a tile but no floor. The plane is
recovered from data that does carry one — cache-dumped objects for facilities,
observed NPC spawns for monsters — and `plane_source` stays NULL whenever the
evidence is absent or contradictory, so an assumption is never mistaken for a
fact.
"""

import importlib.util
import sqlite3

import pytest

_spec = importlib.util.spec_from_file_location(
    "link_coordinate_planes", "scripts/pipeline/link_coordinate_planes.py")
planes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(planes)


def _object(conn: sqlite3.Connection, game_id: int, x: int, y: int, plane: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO object_locations (game_id, x, y, plane, type, orientation)"
        " VALUES (?, ?, ?, ?, 10, 0)",
        (game_id, x, y, plane),
    )


def _facility(conn: sqlite3.Connection, x: int, y: int, name: str = "bank") -> int:
    cur = conn.execute(
        "INSERT INTO facilities (type, x, y, name) VALUES (2, ?, ?, ?)", (x, y, name))
    return cur.lastrowid


def _monster(conn: sqlite3.Connection, name: str, x: int, y: int) -> int:
    conn.execute("INSERT OR IGNORE INTO monsters (name) VALUES (?)", (name,))
    mid = conn.execute("SELECT id FROM monsters WHERE name = ?", (name,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO monster_locations (monster_id, x, y) VALUES (?, ?, ?)", (mid, x, y))
    return cur.lastrowid


def _spawn(conn: sqlite3.Connection, game_id: int, name: str, x: int, y: int, plane: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO npc_locations (game_id, name, x, y, plane, source)"
        " VALUES (?, ?, ?, ?, ?, 'data_osrs')",
        (game_id, name, x, y, plane),
    )


def test_facility_takes_the_plane_of_a_nearby_object(conn: sqlite3.Connection) -> None:
    fid = _facility(conn, 3000, 3000)
    _object(conn, 1, 3001, 3000, plane=1)
    conn.commit()

    planes.resolve_facilities(conn)
    row = conn.execute("SELECT plane, plane_source FROM facilities WHERE id = ?", (fid,)).fetchone()
    assert row == (1, "object_locations")


def test_facility_unresolved_when_objects_disagree(conn: sqlite3.Connection) -> None:
    """A staircase landing has objects on two floors — guessing would be worse."""
    fid = _facility(conn, 3000, 3000)
    _object(conn, 1, 3000, 3000, plane=0)
    _object(conn, 2, 3001, 3000, plane=1)
    conn.commit()

    planes.resolve_facilities(conn)
    row = conn.execute("SELECT plane, plane_source FROM facilities WHERE id = ?", (fid,)).fetchone()
    assert row == (0, None), "ambiguous evidence must stay unresolved"


def test_facility_unresolved_when_no_object_is_near(conn: sqlite3.Connection) -> None:
    fid = _facility(conn, 3000, 3000)
    _object(conn, 1, 3050, 3050, plane=2)  # far outside FACILITY_RADIUS
    conn.commit()

    planes.resolve_facilities(conn)
    assert conn.execute(
        "SELECT plane_source FROM facilities WHERE id = ?", (fid,)).fetchone()[0] is None


def test_monster_takes_the_plane_of_the_nearest_spawn(conn: sqlite3.Connection) -> None:
    mid = _monster(conn, "Corporeal Beast", 2990, 4250)
    _spawn(conn, 319, "Corporeal Beast", 2993, 4254, plane=2)
    conn.commit()

    planes.resolve_monster_locations(conn)
    row = conn.execute(
        "SELECT plane, plane_source FROM monster_locations WHERE id = ?", (mid,)).fetchone()
    assert row == (2, "npc_locations")


def test_monster_prefers_the_closer_spawn_over_a_distant_one(conn: sqlite3.Connection) -> None:
    """Name alone is not enough — something on two floors needs proximity."""
    mid = _monster(conn, "Guard", 3200, 3200)
    _spawn(conn, 1, "Guard", 3201, 3200, plane=1)
    _spawn(conn, 1, "Guard", 3208, 3208, plane=0)
    conn.commit()

    planes.resolve_monster_locations(conn)
    assert conn.execute(
        "SELECT plane FROM monster_locations WHERE id = ?", (mid,)).fetchone()[0] == 1


def test_monster_unresolved_when_equidistant_spawns_disagree(conn: sqlite3.Connection) -> None:
    mid = _monster(conn, "Guard", 3200, 3200)
    _spawn(conn, 1, "Guard", 3202, 3200, plane=0)
    _spawn(conn, 2, "Guard", 3198, 3200, plane=1)
    conn.commit()

    planes.resolve_monster_locations(conn)
    row = conn.execute(
        "SELECT plane, plane_source FROM monster_locations WHERE id = ?", (mid,)).fetchone()
    assert row == (0, None)


def test_monster_unresolved_when_spawn_is_too_far(conn: sqlite3.Connection) -> None:
    mid = _monster(conn, "Rat", 3200, 3200)
    _spawn(conn, 1, "Rat", 3300, 3300, plane=1)  # beyond MONSTER_RADIUS
    conn.commit()

    planes.resolve_monster_locations(conn)
    assert conn.execute(
        "SELECT plane_source FROM monster_locations WHERE id = ?", (mid,)).fetchone()[0] is None


def test_unknown_name_is_left_alone(conn: sqlite3.Connection) -> None:
    mid = _monster(conn, "Nonexistent monster", 3200, 3200)
    conn.commit()

    planes.resolve_monster_locations(conn)
    row = conn.execute(
        "SELECT plane, plane_source FROM monster_locations WHERE id = ?", (mid,)).fetchone()
    assert row == (0, None)

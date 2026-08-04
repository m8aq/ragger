"""Locations that share an infobox name must not collapse into one row.

Four separate temples all declare `name = Temple`, and "Bandit Camp" is both a
Kharidian Desert and a Wilderness location. Keying only on the infobox name
silently dropped 32 real places; the page title supplies the disambiguator.
"""

import importlib.util
import sqlite3

import pytest

from ragger.enums import Region
from ragger.location import Location

_spec = importlib.util.spec_from_file_location("fetch_locations", "scripts/pipeline/fetch_locations.py")
fetch_locations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_locations)


@pytest.mark.parametrize("page, name, expected", [
    ("Varrock", "Varrock", None),
    ("Bandit Camp (Wilderness)", "Bandit Camp", "Wilderness"),
    ("Bandit Camp (Kharidian Desert)", "Bandit Camp", "Kharidian Desert"),
    ("Chaos Temple (church)", "Chaos Temple", "church"),
    ("Unnamed island (east of Fossil Island)", "Unnamed", "east of Fossil Island"),
    ("Sea of Souls (Sailing alpha)", "Sea of Souls", "Sailing alpha"),
    # No parenthetical, but the title still differs from the infobox name.
    ("Lletya shrine", "Lletya", "Lletya shrine"),
    ("Fortis temple", "Temple", "Fortis temple"),
])
def test_derive_version(page: str, name: str, expected: str | None) -> None:
    assert fetch_locations.derive_version(page, name) == expected


def _seed_variants(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO locations (name, region, type, members, x, y, version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("Bandit Camp", Region.WILDERNESS.value, "camp", 1, 3037, 3685, "Wilderness"),
            ("Bandit Camp", Region.DESERT.value, "camp", 1, 3171, 2979, "Kharidian Desert"),
            ("Varrock", Region.MISTHALIN.value, "settlement", 0, 3210, 3448, None),
        ],
    )
    conn.commit()


def test_same_name_different_version_both_stored(conn: sqlite3.Connection) -> None:
    _seed_variants(conn)
    assert len(Location.all_by_name(conn, "Bandit Camp")) == 2


def test_variants_keep_their_own_coordinates(conn: sqlite3.Connection) -> None:
    _seed_variants(conn)
    wild = Location.by_name(conn, "Bandit Camp", version="Wilderness")
    desert = Location.by_name(conn, "Bandit Camp", version="Kharidian Desert")
    assert (wild.x, wild.y) == (3037, 3685)
    assert (desert.x, desert.y) == (3171, 2979)
    assert wild.region is Region.WILDERNESS
    assert desert.region is Region.DESERT


def test_identical_name_and_version_still_rejected(conn: sqlite3.Connection) -> None:
    """Uniqueness is on (name, version), so a true duplicate is still dropped."""
    _seed_variants(conn)
    conn.execute(
        "INSERT OR IGNORE INTO locations (name, region, type, members, x, y, version)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Bandit Camp", Region.WILDERNESS.value, "camp", 1, 9999, 9999, "Wilderness"),
    )
    conn.commit()
    variants = Location.all_by_name(conn, "Bandit Camp")
    assert len(variants) == 2
    assert (variants[0].x, variants[0].y) != (9999, 9999)


def test_by_name_without_version_returns_unversioned_first(conn: sqlite3.Connection) -> None:
    _seed_variants(conn)
    assert Location.by_name(conn, "Varrock").version is None


def test_by_name_missing_version_returns_none(conn: sqlite3.Connection) -> None:
    _seed_variants(conn)
    assert Location.by_name(conn, "Bandit Camp", version="Nowhere") is None

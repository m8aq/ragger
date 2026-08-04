"""Import rules for observed transports from mejrs/data_osrs.

Third-party observations, so every transport is validated against our own
cache-dumped object spawns before it becomes a map link, and the destination
scatter that comes with observed data is collapsed per distinct place.
"""

import importlib.util
import sqlite3

import pytest

_spec = importlib.util.spec_from_file_location(
    "fetch_object_transports", "scripts/pipeline/fetch_object_transports.py")
transports = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transports)


def _entry(**kw):
    entry = {
        "id": 1,
        "start": {"x": 3000, "y": 3000, "p": 0},
        "destinations": [{"x": 3010, "y": 3010, "p": 0}],
        "menuOption": "Climb-up",
        "menuTarget": "Ladder",
    }
    entry.update(kw)
    return entry


def test_cluster_collapses_landing_scatter() -> None:
    """Destinations a few tiles apart are one exit, not several."""
    destinations = [
        {"x": 3000, "y": 3000, "p": 0},
        {"x": 3002, "y": 3001, "p": 0},
        {"x": 3005, "y": 3004, "p": 0},
    ]
    assert transports.cluster_destinations(destinations) == [(3000, 3000, 0)]


def test_cluster_keeps_genuinely_distant_places() -> None:
    """Some hub objects lead thousands of tiles apart; those are separate links."""
    destinations = [
        {"x": 3000, "y": 3000, "p": 0},
        {"x": 3500, "y": 3500, "p": 0},
    ]
    assert len(transports.cluster_destinations(destinations)) == 2


def test_cluster_separates_identical_tiles_on_different_planes() -> None:
    """Same x,y on two floors is two places, however close the numbers look."""
    destinations = [
        {"x": 3000, "y": 3000, "p": 0},
        {"x": 3000, "y": 3000, "p": 1},
    ]
    assert len(transports.cluster_destinations(destinations)) == 2


def test_spawn_match_requires_the_same_plane() -> None:
    """The same ladder id exists on several floors; the ground one is not
    evidence for the one upstairs."""
    spawns = {(1, 0): [(3000, 3000)]}
    assert transports.has_nearby_spawn(_entry(), spawns) is True

    upstairs = _entry(start={"x": 3000, "y": 3000, "p": 1})
    assert transports.has_nearby_spawn(upstairs, spawns) is False


def test_spawn_match_tolerates_a_small_offset() -> None:
    """Object spawns sit at their south-west corner; the observed start tile is
    wherever the player stood."""
    spawns = {(1, 0): [(3003, 3002)]}
    assert transports.has_nearby_spawn(_entry(), spawns) is True


def test_spawn_match_rejects_a_distant_object() -> None:
    spawns = {(1, 0): [(3050, 3050)]}
    assert transports.has_nearby_spawn(_entry(), spawns) is False


def test_unknown_object_id_is_rejected() -> None:
    assert transports.has_nearby_spawn(_entry(), {}) is False

"""Attribution recording must be idempotent.

`record_attribution` used to be a plain INSERT into a table with no uniqueness,
so every run appended a fresh copy of every row. Because `fetched_at` differs
each time, the duplicates were invisible even to a full-row comparison — the
v0.5.0 release shipped 607,035 rows for 44,533 real attributions, roughly 175 MB
of the published database.
"""

import sqlite3

import pytest

from ragger.wiki import record_attribution


def _count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM attributions").fetchone()[0]


def test_recording_the_same_page_twice_keeps_one_row(conn: sqlite3.Connection) -> None:
    record_attribution(conn, "items", "Abyssal whip", ["Alice"])
    record_attribution(conn, "items", "Abyssal whip", ["Alice"])
    conn.commit()
    assert _count(conn) == 1


def test_rerun_updates_authors_rather_than_appending(conn: sqlite3.Connection) -> None:
    record_attribution(conn, "items", "Abyssal whip", ["Alice"])
    record_attribution(conn, "items", "Abyssal whip", ["Alice", "Bob"])
    conn.commit()

    rows = conn.execute("SELECT authors FROM attributions").fetchall()
    assert rows == [("Alice, Bob",)]


def test_the_same_page_can_credit_several_tables(conn: sqlite3.Connection) -> None:
    """Uniqueness is per (table, page) — one wiki page often populates several."""
    record_attribution(conn, "items", "Abyssal whip", ["Alice"])
    record_attribution(conn, "equipment", "Abyssal whip", ["Alice"])
    conn.commit()
    assert _count(conn) == 2


def test_different_pages_are_separate_rows(conn: sqlite3.Connection) -> None:
    record_attribution(conn, "items", "Abyssal whip", ["Alice"])
    record_attribution(conn, "items", "Dragon scimitar", ["Bob"])
    conn.commit()
    assert _count(conn) == 2


def test_many_reruns_do_not_grow_the_table(conn: sqlite3.Connection) -> None:
    """The v0.5.0 database had been through roughly thirteen such passes."""
    for _ in range(13):
        for page in ("Abyssal whip", "Dragon scimitar", "Coins"):
            record_attribution(conn, "items", page, ["Alice"])
    conn.commit()
    assert _count(conn) == 3


def test_credits_counts_are_unaffected_by_dedup(conn: sqlite3.Connection) -> None:
    """release.py counts DISTINCT pages, so credits were right despite the bloat.
    They must stay right now that the rows are deduplicated."""
    for _ in range(5):
        record_attribution(conn, "items", "Abyssal whip", ["Alice, Bob"])
        record_attribution(conn, "quests", "Dragon Slayer I", ["Carol"])
    conn.commit()

    pages = conn.execute("SELECT COUNT(DISTINCT wiki_page) FROM attributions").fetchone()[0]
    assert pages == 2

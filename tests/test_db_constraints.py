"""Uniqueness guards on tables that previously accumulated duplicate rows.

Several fetch scripts insert with OR IGNORE but the tables carried no uniqueness
constraint, so the guard never fired and re-runs appended. Where a key column is
nullable the guard is an expression index over COALESCE sentinels, because SQLite
treats NULLs as distinct inside a plain UNIQUE constraint.
"""

import sqlite3


def _insert_three(conn: sqlite3.Connection, sql: str, params: tuple) -> None:
    for _ in range(3):
        conn.execute(sql, params)
    conn.commit()


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_diary_tasks_reject_duplicates(conn: sqlite3.Connection) -> None:
    _insert_three(
        conn,
        "INSERT OR IGNORE INTO diary_tasks (location, tier, description) VALUES (?, ?, ?)",
        ("Ardougne", "Easy", "Steal a cake from the Ardougne market stalls."),
    )
    assert _count(conn, "diary_tasks") == 1


def test_diary_tasks_keep_distinct_tiers(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO diary_tasks (location, tier, description) VALUES (?, ?, ?)",
        [("Ardougne", "Easy", "Same text"), ("Ardougne", "Medium", "Same text")],
    )
    conn.commit()
    assert _count(conn, "diary_tasks") == 2


def test_monster_drops_reject_duplicates_with_null_columns(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO monsters (id, name) VALUES (5778, 'Test monster')")
    _insert_three(
        conn,
        "INSERT OR IGNORE INTO monster_drops (monster_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)",
        (5778, "Coins", None, None),
    )
    assert _count(conn, "monster_drops") == 1


def test_monster_drops_keep_distinct_quantities(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO monsters (id, name) VALUES (5778, 'Test monster')")
    conn.executemany(
        "INSERT OR IGNORE INTO monster_drops (monster_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)",
        [(5778, "Coins", None, None), (5778, "Coins", "1-100", None), (5778, "Coins", None, "rare")],
    )
    conn.commit()
    assert _count(conn, "monster_drops") == 3


def test_action_triggers_reject_duplicates_with_null_source(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO actions (id, name) VALUES (1, 'Test action')")
    _insert_three(
        conn,
        "INSERT OR IGNORE INTO action_triggers (action_id, trigger_type, source_id, target_id, op) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, 0, None, 31561, "Jump-to"),
    )
    assert _count(conn, "action_triggers") == 1


def test_facilities_reject_duplicates_with_null_columns(conn: sqlite3.Connection) -> None:
    _insert_three(
        conn,
        "INSERT OR IGNORE INTO facilities (type, x, y, name, region) VALUES (?, ?, ?, ?, ?)",
        (2, 3188, 3421, None, None),
    )
    assert _count(conn, "facilities") == 1


def test_facilities_keep_distinct_coordinates(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO facilities (type, x, y, name) VALUES (?, ?, ?, ?)",
        [(2, 3188, 3421, "Varrock"), (2, 3188, 3422, "Varrock")],
    )
    conn.commit()
    assert _count(conn, "facilities") == 2


def test_map_links_reject_duplicates_with_null_columns(conn: sqlite3.Connection) -> None:
    _insert_three(
        conn,
        "INSERT OR IGNORE INTO map_links (src_location, dst_location, src_x, src_y, dst_x, dst_y, type, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Varrock", "Falador", None, None, None, None, None, None),
    )
    assert _count(conn, "map_links") == 1


def test_map_links_keep_opposite_directions(conn: sqlite3.Connection) -> None:
    """A->B and B->A are separate links, not duplicates."""
    conn.executemany(
        "INSERT OR IGNORE INTO map_links (src_location, dst_location, src_x, src_y, dst_x, dst_y, type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("Varrock", "Falador", 3212, 3428, 2965, 3380, "walkable"),
            ("Falador", "Varrock", 2965, 3380, 3212, 3428, "walkable"),
        ],
    )
    conn.commit()
    assert _count(conn, "map_links") == 2

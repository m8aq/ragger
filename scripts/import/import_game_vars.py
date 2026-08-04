"""Import game variable constants from JSON files produced by DumpGameVars into the database."""

import argparse
import json
from pathlib import Path

from ragger.db import create_tables, get_connection

GAME_VARS_DIR = Path(__file__).parents[2] / "data/game-vars"


def ingest(db_path: Path, vars_dir: Path) -> None:
    """Import game variable constants, updating rows in place.

    This upserts rather than clearing the table first. `virtual_currencies`,
    `group_varbit_requirements` and `group_varp_requirements` all hold foreign
    keys onto `game_vars.id`, so a `DELETE FROM game_vars` fails outright once
    any of them has rows — which broke the documented "re-run after updating
    RuneLite" workflow. It would also discard the `content_tags` and
    `functional_tags` that `classify_game_vars.py` writes.

    `INSERT OR REPLACE` is not a substitute: it deletes the conflicting row and
    inserts a new one with a fresh id, leaving those foreign keys dangling.
    The upsert keeps the id, so references stay valid and classifications
    survive.

    Variables that disappear from the cache are left in place rather than
    deleted, since removing them could break the same references.
    """
    create_tables(db_path)
    conn = get_connection(db_path)

    before = conn.execute("SELECT COUNT(*) FROM game_vars").fetchone()[0]

    total = 0
    counts: list[str] = []

    for json_file in sorted(vars_dir.glob("*.json")):
        data = json.loads(json_file.read_text())
        var_type = data["var_type"]
        entries = data["entries"]

        conn.executemany(
            """INSERT INTO game_vars (name, var_id, var_type, description) VALUES (?, ?, ?, ?)
               ON CONFLICT(name, var_type) DO UPDATE SET
                   var_id = excluded.var_id,
                   description = excluded.description""",
            [(e["name"], e["id"], var_type, e.get("comment")) for e in entries],
        )

        total += len(entries)
        counts.append(f"{len(entries)} {var_type}")

    conn.commit()
    added = conn.execute("SELECT COUNT(*) FROM game_vars").fetchone()[0] - before
    print(f"Imported {total} game vars ({', '.join(counts)}) — {added} new, {total - added} updated")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import game variable constants into the database")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    parser.add_argument(
        "--vars-dir",
        type=Path,
        default=GAME_VARS_DIR,
        help="Directory containing JSON files from DumpGameVars",
    )
    args = parser.parse_args()
    ingest(args.db, args.vars_dir)

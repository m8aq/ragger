"""Run the whole pipeline against a handful of pages to check every step works.

A full build takes about an hour, and `fetch_all.py` stops at the first failing
script — so a mistake in step 30 is only discovered after 45 minutes of
fetching. This runs the same steps with the page lists capped, skipping the
contributor and redirect lookups (pure network, no parsing to exercise), and
*keeps going* after a failure so one run surfaces every broken step.

    uv run python scripts/smoke_test.py [--pages 15] [--db data/smoke.db]

It is not a correctness check: with 15 pages per category most cross-references
will not resolve, so low row counts are expected. What it proves is that every
script runs, parses, and writes without raising.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_all import SCRIPTS  # noqa: E402

# Table each step is expected to write, used to report what it produced. Steps
# absent from this map still run; they just report no row count.
STEP_TABLES = {
    "fetch_categories": "wiki_categories",
    "fetch_items": "items",
    "fetch_currencies": "physical_currencies",
    "fetch_equipment": "equipment",
    "fetch_quests": "quests",
    "fetch_diary_tasks": "diary_tasks",
    "fetch_shops": "shops",
    "fetch_locations": "locations",
    "fetch_facilities": "facilities",
    "fetch_monsters": "monsters",
    "fetch_fairy_rings": "map_links",
    "fetch_activities": "activities",
    "fetch_npcs": "npcs",
    "fetch_spells": "teleport_spells",
    "fetch_ground_items": "ground_items",
    "fetch_npc_locations": "npc_locations",
    "fetch_actions": "actions",
    "fetch_wiki_vars": "game_vars",
    "fetch_mechanics": "wiki_pages",
    "fetch_dialogues": "dialogue_pages",
    "fetch_page_categories": "page_categories",
    "compute_dialogue_tags": "dialogue_tags",
    "compute_dialogue_instructions": "dialogue_instructions",
    "compute_blobs": "blobs",
    "compute_ports": "ports",
    "compute_port_transits": "port_transits",
    "compute_port_crossings": "port_crossings",
}


# Extra arguments that narrow a step further than RAGGER_MAX_PAGES can.
STEP_ARGS = {
    "fetch_actions": ["--skill", "Cooking"],
}

# Steps that cannot succeed on capped input because they look up specific
# hardcoded entities. Reported as "skip", not "FAIL" — failing here says
# nothing about whether the step works on a full build.
CAP_SENSITIVE = {
    # Needs the NPCs that operate transports (Hajedy and friends) to be among
    # the npc_locations rows, which a 15-page cap will not include.
    "fetch_npc_transports",
}


def row_count(db_path: Path, table: str | None) -> str:
    if not table:
        return ""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        return f"{conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:,} {table}"
    except sqlite3.Error:
        return f"? {table}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test every pipeline step on a few pages")
    parser.add_argument("--db", type=Path, default=Path("data/smoke.db"), help="Scratch database path")
    parser.add_argument("--pages", type=int, default=15, help="Max pages per category (default 15)")
    parser.add_argument("--keep", action="store_true", help="Keep an existing scratch database")
    parser.add_argument(
        "--from-step",
        default=None,
        help="Resume from this step, keeping what earlier steps already wrote (implies --keep)",
    )
    args = parser.parse_args()

    # Resuming into a wiped database is never what anyone means: the skipped
    # steps are exactly the ones that populate the tables the later steps read,
    # so every remaining step fails for reasons unrelated to the code.
    if args.from_step:
        args.keep = True

    if args.db.exists() and not args.keep:
        args.db.unlink()

    env = {
        **os.environ,
        "RAGGER_MAX_PAGES": str(args.pages),
        "RAGGER_SKIP_ATTRIBUTION": "1",
    }
    env.setdefault("RAGGER_WIKI_CACHE", "data/wiki-cache.db")

    # Prerequisites, same as a real build: fetch_quetzal raises without game_vars,
    # compute_gate_links needs object_locations, and the compute chain needs the
    # collision map squares. Always run, including under --from-step: they take
    # about two seconds, they are idempotent, and skipping them makes every
    # downstream compute step fail for reasons that have nothing to do with the
    # code under test.
    prerequisites = [
        "scripts/import/import_map_squares.py",
        "scripts/import/import_game_vars.py",
        "scripts/import/import_object_locations.py",
    ] if Path("data/cache-dump").exists() else []

    if not prerequisites:
        print("Note: data/cache-dump missing — quetzal, gate links and the compute chain will fail\n")

    scripts = list(SCRIPTS)
    if args.from_step:
        matches = [i for i, s in enumerate(scripts) if args.from_step in s]
        scripts = scripts[matches[0]:] if matches else scripts

    scripts = prerequisites + scripts

    print(f"Smoke test: {len(scripts)} steps, {args.pages} pages per category, db={args.db}\n")

    results: list[tuple[str, str, float, str, str]] = []
    for script in scripts:
        name = Path(script).stem
        start = time.time()
        proc = subprocess.run(
            [sys.executable, "-u", script, "--db", str(args.db), *STEP_ARGS.get(name, [])],
            env=env, capture_output=True, text=True,
        )
        elapsed = time.time() - start

        detail = ""
        if proc.returncode == 0:
            status = "ok"
        elif name in CAP_SENSITIVE:
            status = "skip"
            detail = "needs full data, cannot run on a capped sample"
        else:
            status = "FAIL"
            lines = [l for l in proc.stderr.strip().split("\n") if l.strip()]
            detail = lines[-1][:120] if lines else f"exit {proc.returncode}"

        results.append((name, status, elapsed, row_count(args.db, STEP_TABLES.get(name)), detail))
        print(f"  {status:<4} {name:<34} {elapsed:>6.1f}s  {results[-1][3]}")
        if detail:
            print(f"       {detail}")

    failed = [r for r in results if r[1] == "FAIL"]
    total = sum(r[2] for r in results)

    skipped = [r for r in results if r[1] == "skip"]

    print(f"\n{'=' * 78}")
    print(f"{len(results) - len(failed) - len(skipped)}/{len(results)} steps passed"
          f"{f', {len(skipped)} skipped' if skipped else ''} in {total:.0f}s")
    if failed:
        print("\nFailed steps:")
        for name, _, _, _, detail in failed:
            print(f"  {name}: {detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

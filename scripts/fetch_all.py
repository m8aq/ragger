"""Run all fetch scripts in the correct order.

Order matters — items must be populated before quests or diary tasks,
since those scripts reference the items table. Linking scripts run last
since they depend on multiple tables being populated.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from ragger.enums import League

# Per-step durations from the last completed run, used to estimate the finish
# time of the next one. Written on success, read on start; absent on a first
# run, in which case no estimate is shown rather than a made-up one.
TIMINGS_PATH = Path("data/build-timings.json")

# Appended to the run only when --league is given.
LEAGUE_SCRIPT = "scripts/pipeline/fetch_league_tasks.py"

# Live status, rewritten after every step so progress can be read without
# parsing the log: `cat data/build-progress.json`.
PROGRESS_PATH = Path("data/build-progress.json")

SCRIPTS = [
    # Metadata (no dependencies)
    "scripts/pipeline/fetch_categories.py",
    # Core data (order matters)
    "scripts/pipeline/fetch_items.py",
    "scripts/pipeline/fetch_currencies.py",
    "scripts/pipeline/fetch_equipment.py",
    "scripts/pipeline/fetch_quests.py",
    "scripts/pipeline/fetch_quest_regions.py",
    "scripts/pipeline/fetch_diary_tasks.py",
    "scripts/pipeline/fetch_diary_items.py",
    "scripts/pipeline/fetch_shops.py",
    "scripts/pipeline/fetch_locations.py",
    "scripts/pipeline/fetch_facilities.py",
    "scripts/pipeline/fetch_monsters.py",
    "scripts/pipeline/fetch_dungeon_entrances.py",
    "scripts/pipeline/fetch_fairy_rings.py",
    "scripts/pipeline/fetch_quetzal.py",
    "scripts/pipeline/fetch_charter_ships.py",
    "scripts/pipeline/fetch_magic_teleports.py",
    "scripts/pipeline/fetch_activities.py",
    "scripts/pipeline/fetch_npcs.py",
    "scripts/pipeline/fetch_spells.py",
    "scripts/pipeline/fetch_ground_items.py",
    "scripts/pipeline/fetch_npc_locations.py",
    "scripts/pipeline/fetch_npc_transports.py",
    "scripts/pipeline/fetch_actions.py",
    "scripts/pipeline/fetch_wiki_vars.py",
    "scripts/pipeline/fetch_mechanics.py",
    "scripts/pipeline/fetch_dialogues.py",
    # Category mapping (depends on all entity tables + wiki_categories)
    "scripts/pipeline/fetch_page_categories.py",
    # Linking / compute passes (depend on multiple tables)
    "scripts/pipeline/link_shop_locations.py",
    "scripts/pipeline/link_activity_locations.py",
    "scripts/pipeline/link_ground_item_locations.py",
    "scripts/pipeline/link_facilities.py",
    "scripts/pipeline/link_dialogue_entities.py",
    "scripts/pipeline/compute_dialogue_tags.py",
    "scripts/pipeline/compute_dialogue_instructions.py",
    "scripts/pipeline/link_npc_dialogues.py",
    "scripts/pipeline/link_quest_dialogues.py",
    "scripts/pipeline/compute_blobs.py",
    "scripts/pipeline/compute_gate_links.py",
    "scripts/pipeline/compute_ports.py",
    "scripts/pipeline/compute_port_transits.py",
    "scripts/pipeline/compute_port_crossings.py",
    "scripts/pipeline/compute_map_link_blobs.py",
]


def check_full_data() -> None:
    """Refuse to run if the sampling knobs are set.

    `RAGGER_MAX_PAGES` and `RAGGER_SKIP_ATTRIBUTION` exist for `smoke_test.py`.
    Left set in a shell they would silently truncate a real build — every step
    would report success while writing a fraction of the data, and nothing
    downstream would notice. A production build must be all-or-nothing.
    """
    from ragger import wiki

    if not wiki.SAMPLING:
        return

    active = []
    if wiki.MAX_PAGES:
        active.append(f"RAGGER_MAX_PAGES={wiki.MAX_PAGES} (caps every category to {wiki.MAX_PAGES} pages)")
    if wiki.SKIP_ATTRIBUTION:
        active.append("RAGGER_SKIP_ATTRIBUTION (skips contributor and redirect lookups)")

    print("Refusing to run: sampling is enabled, so this build would be incomplete.\n", file=sys.stderr)
    for line in active:
        print(f"  {line}", file=sys.stderr)
    print("\nUnset them for a full build, or use scripts/smoke_test.py to validate the "
          "pipeline on a sample.", file=sys.stderr)
    sys.exit(1)


def format_duration(seconds: float) -> str:
    """Render a duration as 42s, 3m 20s, or 1h 04m."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


def load_timings() -> dict[str, float]:
    if not TIMINGS_PATH.exists():
        return {}
    try:
        return json.loads(TIMINGS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def write_progress(payload: dict) -> None:
    """Write the live status file, ignoring failures so it never breaks a build."""
    try:
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS_PATH.write_text(json.dumps(payload, indent=2))
    except OSError:
        pass


def run(db_path: Path, league: str | None = None) -> None:
    steps = list(SCRIPTS)
    if league:
        steps.append(LEAGUE_SCRIPT)

    baseline = load_timings()
    known = [s for s in steps if s in baseline]
    if known:
        estimate = sum(baseline[s] for s in steps if s in baseline)
        print(f"Estimated total: ~{format_duration(estimate)} "
              f"(from the last run, {len(known)}/{len(steps)} steps timed)", flush=True)

    started = time.time()
    durations: dict[str, float] = {}

    for index, script in enumerate(steps, start=1):
        name = Path(script).stem
        elapsed = time.time() - started

        remaining = [s for s in steps[index - 1:] if s in baseline]
        eta = f"  eta ~{format_duration(sum(baseline[s] for s in remaining))}" if remaining else ""
        print(f"\n=== [{index}/{len(steps)}] {script}  (elapsed {format_duration(elapsed)}{eta}) ===",
              flush=True)

        write_progress({
            "state": "running",
            "step": index,
            "total": len(steps),
            "current": name,
            "elapsed_seconds": round(elapsed),
            "completed": durations,
        })

        # -u matters: without it Python block-buffers a child's stdout whenever
        # it is a pipe rather than a terminal, so a long step can appear frozen
        # for many minutes while it is working normally.
        args = [sys.executable, "-u", script, "--db", str(db_path)]
        if league and script == LEAGUE_SCRIPT:
            args += ["--league", league]

        step_started = time.time()
        try:
            subprocess.run(args, check=True)
        except subprocess.CalledProcessError:
            durations[script] = time.time() - step_started
            write_progress({
                "state": "failed",
                "step": index,
                "total": len(steps),
                "current": name,
                "elapsed_seconds": round(time.time() - started),
                "completed": durations,
            })
            print(f"\nFAILED at [{index}/{len(steps)}] {name} "
                  f"after {format_duration(time.time() - started)}", flush=True)
            raise

        durations[script] = time.time() - step_started
        print(f"--- [{index}/{len(steps)}] {name} done in {format_duration(durations[script])}", flush=True)

    total = time.time() - started
    write_progress({
        "state": "complete",
        "step": len(steps),
        "total": len(steps),
        "current": None,
        "elapsed_seconds": round(total),
        "completed": durations,
    })

    try:
        TIMINGS_PATH.write_text(json.dumps(durations, indent=2))
    except OSError:
        pass

    print(f"\n{'=' * 70}")
    print(f"Build complete in {format_duration(total)} ({len(steps)} steps)")
    print("\nSlowest steps:")
    for script, seconds in sorted(durations.items(), key=lambda kv: -kv[1])[:8]:
        share = seconds / total * 100
        print(f"  {format_duration(seconds):>9}  {share:>4.0f}%  {Path(script).stem}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch all OSRS data into the database")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    parser.add_argument(
        "--league",
        default=None,
        choices=[l.name for l in League],
        help="Which league to ingest tasks for (e.g. DEMONIC_PACTS).",
    )
    args = parser.parse_args()
    check_full_data()
    run(args.db, args.league)

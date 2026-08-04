"""Fetch location data from the OSRS wiki and populate locations/location_adjacencies tables.

Parses {{Infobox Location}} for metadata and {{Relativelocation}} / {{Relative location}}
for adjacency data.
"""

import argparse
import re
from pathlib import Path

from ragger.db import create_tables, get_connection
from ragger.wiki import (
    extract_coords,
    extract_template,
    fetch_category_members,
    fetch_pages_wikitext,
    parse_template_param,
    populate_aliases_table,
    record_attributions_batch,
    resolve_region,
    strip_wiki_links,
)

DIRECTIONS = ("north", "south", "east", "west")

PARENTHETICAL = re.compile(r"\(([^)]+)\)\s*$")

# leagueRegion values that legitimately mean "no region", so resolve_region
# returning None for them is correct rather than an unhandled label.
NO_REGION_LABELS = {"no", "n/a", "none", ""}


def derive_version(page: str, name: str) -> str | None:
    """Disambiguator for locations whose infobox name is not unique.

    Wiki page titles are unique; infobox names frequently are not — four
    separate temples all declare `name = Temple`, and both the Kharidian
    Desert and Wilderness camps declare `name = Bandit Camp`. Keying only on
    the infobox name silently collapses them into one row.

    Prefers the page title's parenthetical ("Bandit Camp (Wilderness)" gives
    "Wilderness"); otherwise falls back to the page title itself when it
    differs from the name ("Lletya shrine" under name "Lletya").
    """
    if page == name:
        return None

    match = PARENTHETICAL.search(page)
    return match.group(1) if match else page


def parse_map_coords(wikitext: str) -> tuple[int | None, int | None]:
    """Extract x,y tile coordinates from the first {{Map}} template."""
    i = 0
    map_text = None
    while i < len(wikitext):
        if wikitext[i:i + 5] == "{{Map":
            depth = 0
            start = i
            while i < len(wikitext):
                if wikitext[i:i + 2] == "{{":
                    depth += 1
                    i += 2
                elif wikitext[i:i + 2] == "}}":
                    depth -= 1
                    i += 2
                    if depth == 0:
                        map_text = wikitext[start:i]
                        break
                else:
                    i += 1
            break
        else:
            i += 1

    if not map_text:
        return None, None

    coords = extract_coords(map_text)
    if coords:
        return coords[0]

    return None, None


def parse_infobox_location(wikitext: str, page: str) -> dict | None:
    block = extract_template(wikitext, "Infobox Location")
    if not block:
        return None

    name = parse_template_param(block, "name")
    if not name:
        print(f"  Warning: no name in Infobox Location for page '{page}'")
        return None

    location_str = parse_template_param(block, "location")
    league_region = parse_template_param(block, "leagueRegion")
    loc_type = parse_template_param(block, "type")
    members_str = parse_template_param(block, "members")

    region = resolve_region(league_region)
    if region is None and league_region and league_region.strip().lower() not in NO_REGION_LABELS:
        print(f"  Warning: unhandled leagueRegion '{league_region}' for '{name}'")

    if loc_type:
        loc_type = strip_wiki_links(loc_type).strip()

    members = 0 if members_str and members_str.strip().lower() == "no" else 1

    x, y = parse_map_coords(wikitext)

    return {
        "name": name,
        "region": region,
        "type": loc_type,
        "members": members,
        "x": x,
        "y": y,
    }


def parse_adjacency(wikitext: str, page: str) -> dict[str, str]:
    adjacency: dict[str, str] = {}

    # Try both template name variants
    block = extract_template(wikitext, "Relativelocation")
    if block is None:
        block = extract_template(wikitext, "Relative location")
    if block is None:
        return adjacency

    for direction in DIRECTIONS:
        value = parse_template_param(block, direction)
        if value:
            cleaned = strip_wiki_links(value).strip()
            if cleaned:
                adjacency[direction] = cleaned
            else:
                print(f"  Warning: empty {direction} adjacency after cleanup for '{page}'")

    return adjacency


def ingest(db_path: Path) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    pages = fetch_category_members("Locations")
    print(f"Found {len(pages)} pages in Category:Locations")

    all_wikitext = fetch_pages_wikitext(pages)

    location_count = 0
    adjacency_count = 0
    skipped = 0
    page_to_id: dict[str, int] = {}

    for page in pages:
        wikitext = all_wikitext.get(page, "")

        infobox = parse_infobox_location(wikitext, page)
        if not infobox:
            skipped += 1
            continue

        version = derive_version(page, infobox["name"])

        conn.execute(
            "INSERT OR IGNORE INTO locations (name, region, type, members, x, y, version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (infobox["name"], infobox["region"], infobox["type"], infobox["members"],
             infobox["x"], infobox["y"], version),
        )
        loc_row = conn.execute(
            "SELECT id FROM locations WHERE name = ? AND version IS ?", (infobox["name"], version),
        ).fetchone()
        if not loc_row:
            continue
        loc_id = loc_row[0]
        page_to_id[page] = loc_id

        adjacency = parse_adjacency(wikitext, page)
        for direction, neighbor in adjacency.items():
            conn.execute(
                "INSERT OR IGNORE INTO location_adjacencies (location_id, direction, neighbor) VALUES (?, ?, ?)",
                (loc_id, direction, neighbor),
            )
            adjacency_count += 1

        location_count += 1

    print("Recording attributions...")
    record_attributions_batch(conn, "locations", pages)

    print("Fetching location aliases from wiki redirects...")
    # Keyed by page title, not location name: `populate_aliases_table` looks up
    # by page, and a disambiguated title ("Bandit Camp (Wilderness)") never
    # matches the infobox name it was stored under.
    alias_count = populate_aliases_table(
        conn,
        pages,
        "INSERT OR IGNORE INTO location_aliases (location_id, alias) VALUES (?, ?)",
        page_to_key=page_to_id.get,
    )
    print(f"Inserted {alias_count} location aliases")

    conn.commit()
    print(
        f"Inserted {location_count} locations with {adjacency_count} adjacency edges"
        f" ({skipped} pages skipped) into {db_path}"
    )
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OSRS location data")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    args = parser.parse_args()
    ingest(args.db)

"""Fetch game variable annotations from the OSRS wiki.

Scrapes RuneScape:Varplayer/* and RuneScape:Varbit/* pages for descriptions,
content links, var class (Enum/Switch/Counter), and value annotations.

Updates existing game_vars rows with wiki metadata and populates a new
game_var_values table with per-value annotations (quest stages, etc.).
"""

import argparse
import re
import sqlite3
import time
from pathlib import Path

from ragger.db import create_tables, get_connection
from ragger.wiki import (
    _cap,
    fetch_pages_wikitext_batch,
    record_attributions_batch,
    strip_markup,
    strip_wiki_links,
    throttle,
)

API = "https://oldschool.runescape.wiki/api.php"

# Map wiki var types to DB var types
WIKI_TYPE_MAP = {
    "Varplayer": "varp",
    "Varbit": "varbit",
}

# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

GAME_VAR_VALUES_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_var_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    var_type TEXT NOT NULL,
    var_id INTEGER NOT NULL,
    value INTEGER NOT NULL,
    label TEXT NOT NULL,
    UNIQUE(var_type, var_id, value)
)
"""


def migrate(conn: sqlite3.Connection) -> None:
    """Add wiki columns to game_vars and create game_var_values table."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(game_vars)").fetchall()}
    if "wiki_name" not in cols:
        conn.execute("ALTER TABLE game_vars ADD COLUMN wiki_name TEXT")
    if "wiki_content" not in cols:
        conn.execute("ALTER TABLE game_vars ADD COLUMN wiki_content TEXT")
    if "var_class" not in cols:
        conn.execute("ALTER TABLE game_vars ADD COLUMN var_class TEXT")
    conn.execute(GAME_VAR_VALUES_SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Page enumeration
# ---------------------------------------------------------------------------

def enumerate_var_pages(session, prefix: str, namespace: int = 4) -> list[str]:
    """List all subpages under a RuneScape: prefix via allpages API."""
    import requests

    pages = []
    params = {
        "action": "query",
        "list": "allpages",
        "apprefix": prefix,
        "apnamespace": namespace,
        "aplimit": 500,
        "format": "json",
    }
    while True:
        resp = session.get(API, params=params)
        data = resp.json()
        for p in data["query"]["allpages"]:
            pages.append(p["title"])
        if "continue" in data:
            params["apcontinue"] = data["continue"]["apcontinue"]
            time.sleep(0.5)
        else:
            break
    return _cap(pages)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_infobox(wikitext: str) -> dict | None:
    """Extract fields from {{Infobox Var}}."""
    match = re.search(r"\{\{Infobox Var\s*\n(.*?)\}\}", wikitext, re.DOTALL)
    if not match:
        return None

    fields = {}
    for line in match.group(1).splitlines():
        m = re.match(r"\|(\w+)\s*=\s*(.*)", line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


VALUES_SECTION = re.compile(r"==\s*Values\s*==\s*\n(.*?)(?=\n==|\n\{\{Similar|\Z)", re.DOTALL)

# A key may be a single number or a range ("5-9"). Ranges are written out one row
# per value, but only when short — a few pages use them for whole 0-255 spans.
KEY = r"-?\d+(?:\s*(?:-|–|to)\s*-?\d+)?"
RANGE_MAX_SPAN = 32

# ; 0 : label   /   ; 0 label   /   ; 0  (label follows on later lines)
DEF_TERM = re.compile(rf"^;\s*({KEY})\s*(?::\s*)?(.*)$")
# *0 - label   /   * 0: label   /   * '''0''': label
BULLET = re.compile(rf"^\*+\s*'*\s*({KEY})\s*'*\s*[-–—:=]\s*(.+)$")
# A cell may carry style attributes: | style="..." | 0
CELL_ATTRS = re.compile(r'^[a-z-]+\s*=\s*"[^"]*"\s*\|(?!\|)')


def clean_label(text: str) -> str:
    """Strip wiki markup and surrounding punctuation from a value label."""
    label = strip_wiki_links(strip_markup(text))
    label = re.sub(r"<q>(.*?)</q>", r'"\1"', label)
    label = label.replace("&nbsp;", " ")
    label = re.sub(r"\s+", " ", label)
    return label.strip().strip(":-–— ").strip()


def expand_key(text: str) -> list[int]:
    """Turn a value key into the values it covers. "7" -> [7]; "5-9" -> [5..9]."""
    parts = re.split(r"\s*(?:-|–|to)\s*", text.strip())
    try:
        numbers = [int(p) for p in parts if p not in ("", "-")]
    except ValueError:
        return []
    if len(numbers) == 1:
        return numbers
    if len(numbers) != 2:
        return []
    low, high = numbers
    if low > high or high - low > RANGE_MAX_SPAN:
        return []
    return list(range(low, high + 1))


def parse_definition_list(section: str) -> list[tuple[int, str]]:
    """Parse ";0" terms whose label is on the same line or the lines below it."""
    values: list[tuple[int, str]] = []
    keys: list[int] = []
    buffer: list[str] = []

    def flush() -> None:
        nonlocal keys, buffer
        label = clean_label(" ".join(buffer))
        if keys and label:
            values.extend((key, label) for key in keys)
        keys, buffer = [], []

    for raw in section.splitlines():
        line = raw.strip()
        term = DEF_TERM.match(line)
        if term:
            flush()
            keys = expand_key(term.group(1))
            if term.group(2).strip():
                buffer.append(term.group(2))
            continue
        # A blank line, a table or a bullet ends the current term — without this
        # the trailing prose of a section gets appended to the last label.
        if not line or line.startswith((";", "*", "{|", "|}", "|", "!", "=")):
            flush()
            continue
        buffer.append(line.lstrip(":").strip() if line.startswith(":") else line)

    flush()
    return values


def parse_bullets(section: str) -> list[tuple[int, str]]:
    """Parse "* 0 - label" bullet lists."""
    values = []
    for raw in section.splitlines():
        bullet = BULLET.match(raw.strip())
        if not bullet:
            continue
        label = clean_label(bullet.group(2))
        if label:
            values.extend((key, label) for key in expand_key(bullet.group(1)))
    return values


def row_cells(row: str) -> list[str]:
    """Split one wikitable row into its cells, ignoring headers and captions."""
    cells = []
    for raw in row.splitlines():
        line = raw.strip()
        if not line or not line.startswith("|"):
            continue
        if line.startswith(("|}", "|+")):
            continue
        for cell in line[1:].split("||"):
            cell = CELL_ATTRS.sub("", cell.strip()).strip()
            if cell:
                cells.append(cell)
    return cells


def parse_tables(section: str) -> list[tuple[int, str]]:
    """Parse "! Value !! Description" wikitables, including multi-line rows."""
    values = []
    for block in re.findall(r"\{\|.*?\n\s*\|\}", section, re.DOTALL):
        for row in re.split(r"\n\s*\|-+", block):
            if re.search(r"^\s*!", row, re.M):
                continue
            cells = row_cells(row)
            if len(cells) < 2:
                continue
            keys = expand_key(cells[0])
            label = clean_label(" ".join(cells[1:]))
            if keys and label:
                values.extend((key, label) for key in keys)
    return values


VAR_CLASSES = {"enum", "switch", "counter", "bitmap", "other"}

# Editors leave the template's placeholder comment in place, mistype the value or
# vary its casing, so the raw field is normalised to one of VAR_CLASSES or dropped.
VAR_CLASS_TYPOS = {"count": "counter", "swotch": "switch"}


def normalise_var_class(raw: str | None) -> str | None:
    """Reduce the infobox class field to Enum/Switch/Counter/Bitmap/Other."""
    if not raw:
        return None
    value = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip().strip("'\" ").strip()
    key = VAR_CLASS_TYPOS.get(value.lower(), value.lower())
    return key.capitalize() if key in VAR_CLASSES else None


def parse_values_section(wikitext: str) -> list[tuple[int, str]]:
    """Parse the ==Values== section into (value, label) pairs.

    The wiki writes this section three different ways — a definition list, a
    bullet list, or a wikitable — so each layout is tried and the results are
    merged. Pages that describe their values only in prose yield nothing here;
    their meaning is captured in the page description instead.
    """
    match = VALUES_SECTION.search(wikitext)
    if not match:
        return []

    # Drop HTML comments first: several pages park unconfirmed values in them.
    section = re.sub(r"<!--.*?-->", "", match.group(1), flags=re.DOTALL)

    # Skip incomplete sections
    if "{{Incomplete" in section:
        return []

    merged: dict[int, str] = {}
    for parser in (parse_definition_list, parse_bullets, parse_tables):
        for value, label in parser(section):
            merged.setdefault(value, label)
    return sorted(merged.items())


def parse_description(wikitext: str) -> str | None:
    """Extract prose description between the infobox and first section."""
    # Remove the infobox
    text = re.sub(r"\{\{Infobox Var\s*\n.*?\}\}", "", wikitext, flags=re.DOTALL).strip()

    # Take everything before the first == section
    match = re.match(r"(.*?)(?=\n==|\Z)", text, re.DOTALL)
    if not match:
        return None

    desc = match.group(1).strip()
    if not desc:
        return None

    desc = strip_wiki_links(strip_markup(desc))
    desc = desc.strip()
    return desc if desc else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch game variable annotations from the OSRS wiki")
    parser.add_argument("--db", type=Path, default=Path("data/ragger.db"))
    args = parser.parse_args()

    import requests

    session = requests.Session()
    session.headers["User-Agent"] = "ragger/1.0 (https://github.com/iamacoffeepot/ragger)"

    create_tables(args.db)
    conn = get_connection(args.db)
    migrate(conn)

    # Enumerate wiki var pages
    print("Enumerating wiki var pages...")
    varplayer_pages = enumerate_var_pages(session, "Varplayer/")
    time.sleep(1)
    varbit_pages = enumerate_var_pages(session, "Varbit/")
    all_pages = varplayer_pages + varbit_pages
    print(f"Found {len(varplayer_pages)} varplayer + {len(varbit_pages)} varbit = {len(all_pages)} pages")

    # Clear existing wiki annotations
    conn.execute("UPDATE game_vars SET wiki_name = NULL, wiki_content = NULL, var_class = NULL")
    conn.execute("DELETE FROM game_var_values")
    conn.commit()

    # Fetch and parse in batches of 50
    updated = 0
    inserted_values = 0
    new_vars = 0

    for i in range(0, len(all_pages), 50):
        batch = all_pages[i : i + 50]
        texts = fetch_pages_wikitext_batch(batch)
        throttle()

        # Record attributions
        fetched_pages = [p for p in batch if texts.get(p)]
        if fetched_pages:
            record_attributions_batch(conn, "game_vars", fetched_pages)

        for page, wikitext in texts.items():
            if not wikitext:
                continue

            infobox = parse_infobox(wikitext)
            if not infobox:
                continue

            wiki_type = infobox.get("type")
            var_type = WIKI_TYPE_MAP.get(wiki_type)
            if not var_type:
                continue

            try:
                var_id = int(infobox.get("index", ""))
            except ValueError:
                continue

            wiki_name = infobox.get("name")
            wiki_content = strip_wiki_links(infobox.get("content", "")) or None
            var_class = normalise_var_class(infobox.get("class"))
            description = parse_description(wikitext)

            # Update existing row or insert new one
            existing = conn.execute(
                "SELECT id FROM game_vars WHERE var_id = ? AND var_type = ?",
                (var_id, var_type),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE game_vars SET wiki_name = ?, wiki_content = ?, var_class = ?,"
                    " description = COALESCE(description, ?) WHERE var_id = ? AND var_type = ?",
                    (wiki_name, wiki_content, var_class, description, var_id, var_type),
                )
                updated += 1
            else:
                conn.execute(
                    "INSERT INTO game_vars (name, var_id, var_type, wiki_name, wiki_content,"
                    " var_class, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        wiki_name or f"UNKNOWN_{var_type.upper()}_{var_id}",
                        var_id, var_type, wiki_name, wiki_content, var_class, description,
                    ),
                )
                new_vars += 1

            # Parse and insert value annotations
            values = parse_values_section(wikitext)
            for value, label in values:
                conn.execute(
                    "INSERT OR REPLACE INTO game_var_values (var_type, var_id, value, label) VALUES (?, ?, ?, ?)",
                    (var_type, var_id, value, label),
                )
                inserted_values += 1

        conn.commit()
        done = min(i + 50, len(all_pages))
        print(
            f"  {done}/{len(all_pages)} pages processed"
            f" ({updated} updated, {new_vars} new, {inserted_values} values)"
        )

    conn.close()
    print(f"\nDone. Updated {updated} vars, inserted {new_vars} new vars, {inserted_values} value annotations.")


if __name__ == "__main__":
    main()

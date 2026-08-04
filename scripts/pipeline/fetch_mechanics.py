"""Fetch game mechanics reference pages into the wiki_pages table.

Mechanics pages (Attack speed, Drop rate, Damage per second/Melee, Dragonfire,
...) have no infobox and no shared structure — roughly a third are tables, a
third are formulas, and a third are pure prose. There is nothing to parse into
typed columns, so each page is stored whole: raw wikitext plus a markup-stripped
plain-text rendering for retrieval.

The default category is Mechanics, but any category of reference prose works
(Calculators, Money making guides). The category name is recorded in
wiki_pages.source so catalogs can coexist and be re-ingested independently.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ragger.db import create_tables, get_connection
from ragger.wiki import (
    fetch_category_members,
    fetch_pages_wikitext_batch,
    record_attributions_batch,
    strip_markup,
)

DEFAULT_CATEGORY = "Mechanics"

# Suffix pages ("(a)", "(broken)", "(attuned)") are disambiguation stubs that carry
# no prose. They live under Category:Suffixes, a subcategory of Mechanics.
EXCLUDE_PREFIXES = ("File:", "Category:", "Template:", "Module:")


def ingest(db_path: Path, category: str = DEFAULT_CATEGORY) -> None:
    create_tables(db_path)
    conn = get_connection(db_path)

    pages = fetch_category_members(category, exclude_prefixes=EXCLUDE_PREFIXES)
    print(f"Found {len(pages)} pages in Category:{category}")

    all_wikitext = fetch_pages_wikitext_batch(pages)

    conn.execute("DELETE FROM wiki_pages WHERE source = ?", (category,))

    stored: list[str] = []
    for title in pages:
        wikitext = all_wikitext.get(title, "")
        if not wikitext.strip():
            continue

        conn.execute(
            "INSERT OR IGNORE INTO wiki_pages (title, source, wikitext, text) VALUES (?, ?, ?, ?)",
            (title, category, wikitext, strip_markup(wikitext)),
        )
        stored.append(title)

    if stored:
        record_attributions_batch(conn, "wiki_pages", stored)

    conn.commit()
    skipped = len(pages) - len(stored)
    print(f"Stored {len(stored)} {category} pages into {db_path}" + (f" ({skipped} empty, skipped)" if skipped else ""))
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch mechanics reference pages from the wiki")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help=f"Wiki category to ingest, without the 'Category:' prefix (default: {DEFAULT_CATEGORY})",
    )
    args = parser.parse_args()
    ingest(args.db, args.category)

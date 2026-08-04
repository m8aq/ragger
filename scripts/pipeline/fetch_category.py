"""Fetch whole wiki pages into the wiki_pages table.

Most of the pipeline parses infoboxes into typed columns and throws the prose
away. This script does the opposite: it stores each page whole, as raw wikitext
plus a markup-stripped plain-text rendering for retrieval. That is the only
place the narrative parts of a page survive — reward explanations, strategy
sections, mechanics write-ups, anything that is not a template parameter.

Two modes:

  Full (default)
    Lists every non-redirect article via list=allpages (~83 requests), then
    drops the pages that belong to categories judged not to be current game
    content. One row per page.

  Single category (--category NAME)
    Ingests just that category's members, stamping the category name into
    wiki_pages.source. Used for narrow top-ups.

Why enumeration is page-driven rather than category-driven: walking all ~1,500
kept categories to collect their members costs roughly 1,500 API requests,
against 83 for allpages. Category membership is only needed to decide what to
drop, and the drop set is much smaller than the keep set.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from ragger.db import create_tables, get_connection
from ragger.wiki import (
    MAX_PAGES,
    fetch_all_article_pages,
    fetch_category_members,
    fetch_pages_wikitext_batch,
    record_attributions_batch,
    strip_markup,
)

# Root of the category graph crawled by fetch_categories.py.
CONTENT_ROOT = "Content"

# Marks rows produced by a full ingest, as opposed to a single --category run.
FULL_SOURCE = "Content"

# Top-level branches of Content whose pages are not current game content.
# Pages reachable only through these are dropped: patch notes and dev blogs
# (Updates), music track pages (Music), removed items and areas (Discontinued
# content), unreleased content (Future content), and wiki/company metadata.
DROPPED_ROOTS = (
    "Updates",
    "Music",
    "Discontinued content",
    "Future content",
    "Community",
    "Jagex",
    "Clans",
    "Languages",
    "Nonexistent content",
    "Glitches",
)

# Branches that tag real content pages rather than collecting a subject.
# "Content released in 2006" holds 3,480 ordinary items and monsters, so
# treating it like DROPPED_ROOTS would delete most of the wiki. These are
# neither walked nor used to drop anything.
TAG_ROOTS = ("Content by release date",)

EXCLUDE_PREFIXES = ("File:", "Category:", "Template:", "Module:")


def _dropped_categories(conn: sqlite3.Connection) -> list[str]:
    """Categories whose member pages should not be ingested.

    The graph is a DAG, not a tree, so a plain descendant walk over
    DROPPED_ROOTS over-captures: "Money making guides" sits under both
    "Guides" and "Economy", and "Economy" happens to hang off an excluded
    branch. Dropping every descendant would take 632 money making guides with
    it.

    The rule that holds is reachability. Delete the excluded roots from the
    graph, walk what is still reachable from Content, and drop only the
    categories that walk can no longer see — a category with any surviving
    path to Content is kept.
    """
    blocked = DROPPED_ROOTS + TAG_ROOTS
    placeholders = ",".join("?" * len(blocked))
    rows = conn.execute(
        f"""
        WITH RECURSIVE keep(cid) AS (
            SELECT c.id
            FROM wiki_category_parents p
            JOIN wiki_categories c ON c.id = p.category_id
            WHERE p.parent_id = (SELECT id FROM wiki_categories WHERE name = ?)
              AND c.name NOT IN ({placeholders})
            UNION
            SELECT p.category_id
            FROM keep k
            JOIN wiki_category_parents p ON p.parent_id = k.cid
            WHERE p.category_id NOT IN (
                SELECT id FROM wiki_categories WHERE name IN ({placeholders})
            )
        ),
        tagged(cid) AS (
            SELECT id FROM wiki_categories WHERE name IN ({",".join("?" * len(TAG_ROOTS))})
            UNION
            SELECT p.category_id
            FROM tagged t
            JOIN wiki_category_parents p ON p.parent_id = t.cid
        )
        SELECT c.name
        FROM wiki_categories c
        WHERE c.id NOT IN (SELECT cid FROM keep)
          AND c.id NOT IN (SELECT cid FROM tagged)
          AND c.name <> ?
        ORDER BY c.page_count DESC
        """,
        (CONTENT_ROOT, *blocked, *blocked, *TAG_ROOTS, CONTENT_ROOT),
    ).fetchall()
    return [name for (name,) in rows]


def _excluded_pages(conn: sqlite3.Connection) -> set[str]:
    """Page titles belonging to any dropped category."""
    categories = _dropped_categories(conn)
    if not categories:
        raise RuntimeError(
            "No categories to drop. wiki_categories looks unpopulated — "
            "run fetch_categories.py first, or the full ingest would pull in "
            "every patch note and music track on the wiki."
        )

    # RAGGER_MAX_PAGES caps page enumerations elsewhere; here the cost is one
    # request per dropped category, so the cap has to apply to the category
    # list or a smoke run would spend ~500 requests building an exclusion set
    # it is about to apply to 15 pages.
    if MAX_PAGES and len(categories) > MAX_PAGES:
        print(f"  RAGGER_MAX_PAGES={MAX_PAGES}: using {MAX_PAGES} of {len(categories)} dropped categories")
        categories = categories[:MAX_PAGES]

    print(f"Collecting members of {len(categories)} dropped categories")
    excluded: set[str] = set()
    for i, category in enumerate(categories, start=1):
        excluded.update(fetch_category_members(category, exclude_prefixes=EXCLUDE_PREFIXES))
        if i % 50 == 0:
            print(f"  {i}/{len(categories)} categories, {len(excluded)} pages excluded so far")

    print(f"Excluding {len(excluded)} pages")
    return excluded


def _store(conn: sqlite3.Connection, pages: list[str], source: str, db_path: Path) -> None:
    all_wikitext = fetch_pages_wikitext_batch(pages)

    stored: list[str] = []
    for title in pages:
        wikitext = all_wikitext.get(title, "")
        if not wikitext.strip():
            continue

        conn.execute(
            "INSERT OR IGNORE INTO wiki_pages (title, source, wikitext, text) VALUES (?, ?, ?, ?)",
            (title, source, wikitext, strip_markup(wikitext)),
        )
        stored.append(title)

    if stored:
        record_attributions_batch(conn, "wiki_pages", stored)

    conn.commit()
    skipped = len(pages) - len(stored)
    print(f"Stored {len(stored)} pages into {db_path}" + (f" ({skipped} empty, skipped)" if skipped else ""))


def ingest_category(db_path: Path, category: str) -> None:
    """Ingest one category's members, stamped with the category as source."""
    create_tables(db_path)
    conn = get_connection(db_path)

    pages = fetch_category_members(category, exclude_prefixes=EXCLUDE_PREFIXES)
    print(f"Found {len(pages)} pages in Category:{category}")

    conn.execute("DELETE FROM wiki_pages WHERE source = ?", (category,))
    _store(conn, pages, category, db_path)
    conn.close()


def ingest_all(db_path: Path) -> None:
    """Ingest every article that is not filtered out as non-content."""
    create_tables(db_path)
    conn = get_connection(db_path)

    excluded = _excluded_pages(conn)

    articles = fetch_all_article_pages()
    print(f"Found {len(articles)} articles in the main namespace")

    pages = [title for title in articles if title not in excluded]
    print(f"Ingesting {len(pages)} pages after exclusions")

    # A full ingest is a superset of every single-category run, and
    # wiki_pages.title is UNIQUE — leaving old rows behind would make
    # INSERT OR IGNORE silently keep the stale copy under its old source.
    conn.execute("DELETE FROM wiki_pages")
    _store(conn, pages, FULL_SOURCE, db_path)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch whole wiki pages into wiki_pages")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ragger.db"),
        help="Path to the SQLite database",
    )
    parser.add_argument(
        "--category",
        help="Ingest only this category, without the 'Category:' prefix "
             "(default: every article that is not filtered out)",
    )
    args = parser.parse_args()

    if args.category:
        ingest_category(args.db, args.category)
    else:
        ingest_all(args.db)

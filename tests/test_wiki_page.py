import sqlite3

from ragger.wiki_page import WikiPage


def _seed_pages(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO wiki_pages (title, source, wikitext, text) VALUES (?, ?, ?, ?)",
        [
            ("Attack speed", "Mechanics", "{{Infobox}} '''Attack speed''' is measured in ticks.",
             "Attack speed is measured in ticks."),
            ("Damage per second/Melee", "Mechanics", "Multiply by 1.23 for [[Piety]].",
             "Multiply by 1.23 for Piety."),
            ("Dragonfire", "Mechanics", "Reduced by an [[antifire potion]].",
             "Reduced by an antifire potion."),
            ("Zulrah/Strategies", "Money making guides", "Bring an [[antifire potion]].",
             "Bring an antifire potion."),
        ],
    )
    conn.commit()


def test_by_title(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    page = WikiPage.by_title(conn, "Dragonfire")
    assert page is not None
    assert page.source == "Mechanics"
    assert "antifire" in page.text


def test_by_title_missing(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    assert WikiPage.by_title(conn, "Nonexistent page") is None


def test_search_partial_title(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    assert [p.title for p in WikiPage.search(conn, "Attack")] == ["Attack speed"]


def test_search_filters_by_source(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    assert WikiPage.search(conn, "Zulrah", source="Mechanics") == []
    assert len(WikiPage.search(conn, "Zulrah", source="Money making guides")) == 1


def test_search_text_matches_body_not_title(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    titles = [p.title for p in WikiPage.search_text(conn, "antifire")]
    assert titles == ["Dragonfire", "Zulrah/Strategies"]


def test_search_text_searches_stripped_text(conn: sqlite3.Connection) -> None:
    """Markup lives in wikitext only, so a search for it finds nothing."""
    _seed_pages(conn)
    assert WikiPage.search_text(conn, "[[Piety]]") == []
    assert len(WikiPage.search_text(conn, "Piety")) == 1


def test_all_and_source_filter(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    assert len(WikiPage.all(conn)) == 4
    assert len(WikiPage.all(conn, source="Mechanics")) == 3


def test_titles_are_ordered(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    titles = WikiPage.titles(conn, source="Mechanics")
    assert titles == sorted(titles)
    assert "Dragonfire" in titles


def test_sources(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    assert WikiPage.sources(conn) == ["Mechanics", "Money making guides"]


def test_title_is_unique(conn: sqlite3.Connection) -> None:
    _seed_pages(conn)
    conn.execute(
        "INSERT OR IGNORE INTO wiki_pages (title, source, wikitext, text) VALUES (?, ?, ?, ?)",
        ("Dragonfire", "Mechanics", "different", "different"),
    )
    conn.commit()
    assert len(WikiPage.search(conn, "Dragonfire")) == 1

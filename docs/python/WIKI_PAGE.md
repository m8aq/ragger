### WikiPage (`src/ragger/wiki_page.py`)

Whole wiki pages stored as prose, for reference content that has no schema to parse into.

Entity pages (items, monsters, quests) become typed columns because they carry an infobox. Mechanics and guide pages do not — roughly a third are tables, a third are formulas, a third are pure prose — so each page is kept intact. `wikitext` is the raw source; `text` is the same content with links, templates and emphasis stripped, which is what `search_text` matches against.

`source` is the wiki category the page was ingested from (`"Mechanics"`), so several catalogs can coexist in one table and be re-ingested independently.

```python
from ragger.wiki_page import WikiPage

WikiPage.by_title(conn, title) -> WikiPage | None
WikiPage.search(conn, title, source?) -> list[WikiPage]        # partial match on title
WikiPage.search_text(conn, query, source?) -> list[WikiPage]   # partial match on body
WikiPage.all(conn, source?) -> list[WikiPage]
WikiPage.titles(conn, source?) -> list[str]                    # enumerate without loading bodies
WikiPage.sources(conn) -> list[str]

page.title -> str
page.source -> str
page.wikitext -> str                                           # raw wiki source
page.text -> str                                               # markup stripped
```

Populated by `scripts/pipeline/fetch_mechanics.py`, which defaults to `Category:Mechanics` and accepts `--category` for any other category of reference prose.

```sh
uv run python scripts/pipeline/fetch_mechanics.py [--db data/ragger.db] [--category Mechanics]
```

Note that `all()` loads every page body. Use `titles()` to enumerate.

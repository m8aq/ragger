# Hub Plugin API

### HubPlugin (`src/ragger/hub_plugin.py`)

RuneLite Plugin Hub plugin sources stored whole for local code search. Hub plugins are working examples of reading live game state — varbits, object IDs, animations — that neither the wiki nor the cache documents. The Vale Totems varbit encodings were reverse-engineered this way: the answer lived in another plugin's source. `repository` and `commit_hash` record where each snapshot came from.

```python
HubPlugin.by_name(conn, internal_name) -> HubPlugin | None
HubPlugin.search(conn, name) -> list[HubPlugin]      # LIKE %name% on internal_name
HubPlugin.all(conn) -> list[HubPlugin]
HubPlugin.names(conn) -> list[str]                   # enumerate without loading rows

plugin.id -> int
plugin.internal_name -> str                          # hub identifier, e.g. "totem-fletching"
plugin.repository -> str                             # source GitHub URL
plugin.commit_hash -> str                            # commit the sources were taken from
plugin.files(conn) -> list[HubPluginFile]

HubPluginFile.by_file(conn, internal_name, file_name) -> HubPluginFile | None
HubPluginFile.search_code(conn, query, limit=100) -> list[CodeMatch]

file.file_name -> str                                # bare name, no directory path
file.content -> str                                  # full Java source

match.plugin -> HubPlugin
match.file -> HubPluginFile
```

`search_code` is the point of this module: a case-sensitive substring match over every file's source, joined to the owning plugin. Common identifiers match thousands of files, so results are capped by `limit` (default 100).

Populated by `scripts/import/import_hub_plugins.py`, which downloads the gzipped source bundles republished by the JZomDev/pluginhub-searcher repository (~35 MB over 22 requests) and upserts by `internal_name`, skipping plugins whose `commit_hash` is unchanged and deleting plugins delisted from the hub:

```sh
uv run python scripts/import/import_hub_plugins.py [--db data/ragger.db]
```

Only `.java` files are bundled, with flat file names — two files with the same name in different directories collide, and the first wins. Roughly 2,000 plugins and 29,000 files, adding ~180 MB to the database.

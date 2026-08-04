# Incremental Wiki Sync — Design

Status: **designed, not implemented.** This documents how to make rebuilds pull only
differences from the wiki instead of re-fetching all ~29,000 pages. Written 2026-08-04;
verified against the code as of that date. Nothing here is built yet.

## The question this answers

Is it structurally possible to diff-pull instead of fetching everything each build?

**Yes — and the wiki gives us something better than a hash check.** MediaWiki assigns
every page revision a monotonically increasing revision ID (revid), and exposes a
`recentchanges` feed answering "what changed since T" in about one request per day of
wiki activity (verified live: 500 entries per request, ~372 distinct titles per day).
The existing `WikiCache` (`src/ragger/wiki.py`) already stores wikitext keyed by revid;
what is missing is asking "what changed" — O(changes) — instead of "is each of my 29k
pages current" — O(pages held) — plus caching for the contributor and redirect lookups
that are refetched from scratch every build (~17 min and ~10 min of throttled requests
respectively).

## The core decision: incremental fetch, full materialize

`ragger.db` is always built from scratch. Only the **network layer** becomes
incremental — the wiki cache is synced by diff, then the ordinary build reads almost
everything from cache.

Mutating `ragger.db` in place was considered and rejected as structurally hostile
(verified in the code): `attributions` has no UNIQUE constraint and duplicates on
re-run; `fetch_actions` and `monster_locations` plain-INSERT duplicates; ~17 scripts
insert with OR IGNORE, so changed values never update and orphaned rows survive
renames; and there is no migration system. The local compute phase is only ~7 minutes,
so incrementalizing the database build would buy almost nothing anyway.

Expected result: warm rebuild ≈ rc sync (seconds) + live category enumeration
(~6–8 min) + near-100% cache hits on text/redirects/contributors + ~7 min compute ≈
**13–16 minutes**, versus ~60 today. Cold builds are unchanged.

## Phase 1 — sync engine (60 → ~35 min warm builds)

### Cache schema addition

In `WikiCache.__init__` (additive `CREATE TABLE IF NOT EXISTS`; the cache file is
droppable, so no migration concerns):

```sql
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

Meta key `last_sync` holds an ISO-8601 **server** timestamp — taken from a
`curtimestamp=1` response captured *before* the rc query, never the local clock.

### New module `src/ragger/wiki_sync.py`

Kept out of the ~1,200-line `wiki.py`; imports `api_get`, `throttle`,
`WIKI_BATCH_SIZE`, `API_MAX_CONTINUATIONS` from `ragger.wiki`.

- `collect_changed_titles(since)` — `list=recentchanges`, `rctype=edit|new|log`,
  `rcprop=title|ids|timestamp|loginfo`, `rcnamespace=0|4|120` (main; RuneScape ns 4
  for var pages; Transcript ns 120 for dialogues), with `rcend = since − 5 min`
  overlap — evictions are idempotent, so overlap is free insurance against clock skew
  and same-second boundary edits. For `logtype=move`, also collect
  `logparams.target_title` (the log entry lives on the *old* title). Returns `None`
  — never a truncated set — if `API_MAX_CONTINUATIONS` is exhausted.
- `sync_cache(cache) -> bool` — returns False (fall back to full revalidate) when:
  no `last_sync` but the cache is non-empty (legacy cache); `last_sync` older than
  ~25 days; the retention probe (`rcdir=newer&rclimit=1`, i.e. the oldest rc entry the
  wiki still holds) is newer than `last_sync`; or continuation exhaustion. On success,
  in one transaction: evict changed titles from `wiki_pages`, **bump `fetched_at` on
  every surviving row to the sync watermark**, store the new `last_sync`.
- `full_revalidate(cache)` — existing `WikiCache.validate()` + drop the phase-2
  derived caches + store the watermark.
- `sync_or_revalidate(cache)` — the entry point.

**The `fetched_at` bump is not optional.** Without it, surviving entries age past the
24-hour TTL and the build spends ~580 throttled requests (~10 minutes) revid-checking
pages the sync already proved current. The bump is what converts "sync ran" into
"zero revalidation work".

### CLI and orchestration

- Thin CLI `scripts/sync_wiki_cache.py`, mirroring `scripts/validate_wiki_cache.py`
  (`--cache` argument only). It lives in `scripts/`, **not** `scripts/pipeline/` —
  `fetch_all.run()` passes `--db` to every pipeline script.
- `scripts/fetch_all.py` calls `sync_or_revalidate` in-process as step 0 whenever a
  cache is configured, with a `--no-sync` escape hatch. No cache configured → behavior
  identical to today.

## Phase 2 — derived caches (~35 → ~15 min warm builds)

### Cache schema additions

```sql
CREATE TABLE IF NOT EXISTS contributors (
    title        TEXT PRIMARY KEY,
    revid        INTEGER NOT NULL,
    authors_json TEXT NOT NULL,
    fetched_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
-- presence row: "I know target's alias list, and it may legitimately be empty".
-- Without negative caching, the majority of pages (which have no redirects)
-- would miss every build and the cache would save almost nothing.
CREATE TABLE IF NOT EXISTS redirect_targets (
    target     TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS redirect_aliases (
    target TEXT NOT NULL,
    alias  TEXT NOT NULL,
    PRIMARY KEY (target, alias)
);
CREATE INDEX IF NOT EXISTS idx_redirect_aliases_alias ON redirect_aliases(alias);
```

### Contributors: revid-keyed, with three rules

- Validity is checked by SQL join against `wiki_pages.revid` (current post-sync) —
  zero extra network requests at lookup time.
- One row per title, replace-on-write — never accumulate generations.
- **Never cache a batch that hit the pagination-truncation warning** in
  `fetch_contributors_batch`. Today a truncated contributor list damages one build;
  cached, the damage would be permanent.
- Rows older than ~30 days are treated as misses. Reason: revision-deletion can hide a
  contributor's name retroactively *without* bumping the page revid, and suppression
  logs are not publicly visible in rc. This is the one genuine correctness regression
  versus always-refetching, and the 30-day refresh bounds it — this matters for
  CC BY-SA attribution hygiene.

### Redirects: NOT revid-keyed — this is the subtle part

A target's inbound-redirect list changes when *other* pages (the redirects) are
created, deleted, or retargeted — none of which bumps the target's own revid. So the
redirect cache's validity token is **the sync watermark**, maintained by two eviction
rules over the set C of rc-changed titles:

- **R-a (reverse rule):** evict every cached target whose alias list contains any
  member of C — this is why aliases are normalized rows with an index, not JSON.
  Covers redirect deletion, blanking, and the old-target half of retargeting, with no
  content inspection (the deleted page's content is no longer readable anyway).
- **R-b (forward rule):** batch-resolve C via `action=query&titles=...&redirects=1`
  (one request per 50 titles, ~1–8/day of drift); evict every `to` target the API
  reports. Covers creation, the new-target half of retargeting, and
  move-leaves-a-redirect. **Never parse `#REDIRECT` from wikitext** — case variants,
  localized keywords, and leading templates make that fragile; the API resolves it
  authoritatively.

R-a ∪ R-b is airtight against everything rc can express: any event changing some
target's inbound list either changes a page that *was* an alias (R-a) or *is now* a
redirect (R-b), or both. Test invariant: a page redirects to at most one target, so
each alias appears in at most one cached list.

### Wiring: two chokepoints, zero call-site changes

All ~26 pipeline call sites already funnel through exactly two functions:
`fetch_redirects_batch` (sole caller: `populate_aliases_table`) and
`fetch_contributors_batch` (callers: `record_attributions_batch`,
`fetch_page_contributors`). Cache consultation goes *inside those two fetchers*, using
the same `cache: WikiCache | None = ...` sentinel-default convention as
`fetch_page_wikitext`. No pipeline script changes; `RAGGER_SKIP_ATTRIBUTION` guards
sit above the chokepoints and are untouched.

## Known limitations (accepted, documented)

- Suppression logs and global user renames are invisible to rc; the 30-day contributor
  refresh bounds that staleness.
- Transclusion: a page's rendered content can change via an edited template without
  its own revid moving. Pre-existing property of the revid cache, not a regression;
  ragger parses raw wikitext, so exposure is minimal.
- Category membership and `fetch_page_categories` stay live-fetched (~6–8 min of the
  warm-build floor). `categorize` rc events could patch cached member lists later, but
  they are a large fraction of rc volume, and revid-keying page-categories is unsound
  — template-added categories change membership without a revid bump.
- Cross-namespace moves into a covered namespace from an uncovered one are filtered
  out by `rcnamespace`, but benignly: the covered title could only be cache-stale if
  it previously existed, which requires a prior covered delete log that rc does catch.
- A title cached under a non-canonical spelling can never be evicted by rc. Only the
  single-page fetch path can create such rows; nearly all titles come from API
  enumeration, which returns canonical forms.

## Small fix to fold in

`record_attributions_batch` prints nothing across ~250 throttled batches — about seven
minutes of total silence in the build log. Add a per-batch progress line matching the
existing `"  Fetching aliases N-M..."` style. This silence has already caused one
false hang diagnosis and one needlessly killed build.

## Verification plan (when implemented)

- **Unit** (mock `api_get` per `tests/test_wiki_api_get.py` conventions; in-memory
  `WikiCache(":memory:")`): the eviction matrix — plain edit, new page, delete log,
  move evicting both titles, retarget evicting both targets, redirect deletion evicted
  via the alias index alone, empty alias list surviving as a cached negative;
  `collect_changed_titles` returning None on exhaustion; the watermark written only on
  success; contributor hits requiring an exact revid join; truncated batches never
  cached; and `cache=None` behaving byte-identically to today.
- **Integration** (live wiki, cheap): seed `last_sync` 24 hours back on a copy of the
  real cache — expect ~300–800 rc entries and a sub-minute sync. Seed 60 days back —
  expect the retention probe or age short-circuit to force the full-revalidate path
  and drop the derived caches.
- **End-to-end equivalence:** build `ragger.db` twice from the same synced cache state
  — once warm, once with `RAGGER_WIKI_CACHE` unset — and diff table-by-table,
  excluding timestamp and autoincrement columns. Scrutinize `attributions` and the
  `*_aliases` tables: they are the data this design newly caches.
- **Timing:** compare `data/build-timings.json` across runs; target ≤16 minutes warm.

## Sequencing

Four commits, each independently testable: (1) cache schema + methods + tests;
(2) sync engine + CLI + tests; (3) cached fetchers + tests; (4) `fetch_all` wiring +
docs. Phase 1 is shippable on its own and already removes the revalidation tax.

**Do not start implementation while a build is running.** Pipeline steps import
`ragger.wiki` in fresh interpreters as they spawn, so editing it mid-build changes the
code under a running pipeline.

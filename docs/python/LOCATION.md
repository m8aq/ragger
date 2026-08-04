### Location (`src/ragger/location.py`)

```python
from ragger.location import Location, DistanceMetric

Location.all(conn, region?) -> list[Location]
Location.by_name(conn, name, version?) -> Location | None
Location.all_by_name(conn, name) -> list[Location]  # every variant sharing a name
Location.search(conn, name) -> list[Location]      # partial name match
Location.nearest(conn, x, y, metric?) -> Location | None
Location.with_facilities(conn, [Facility, ...], region?) -> list[Location]
Location.for_shop(conn, shop_id) -> Location | None
location.adjacencies(conn) -> list[Adjacency]          # raw edges
location.neighbors(conn) -> dict[str, Location | None] # resolved by direction
location.within(conn, hops) -> list[tuple[Location, int]]  # BFS graph distance
location.nearby(conn, max_distance, metric?) -> list[tuple[Location, float]]  # tile distance
location.shops(conn) -> list[Shop]
location.has_facility(facility) -> bool
location.facility_list() -> list[Facility]
location.name -> str                                   # infobox name, NOT unique
location.version -> str | None                         # disambiguator from the page title
location.x -> int | None                               # map coordinates
location.y -> int | None
location.facilities -> int                             # bitmask
location.game_vars(conn) -> list[GameVariable]          # associated game variables
```

Distance metrics for `nearby()` and `nearest()`: `DistanceMetric.CHEBYSHEV` (default, matches OSRS diagonal movement), `DistanceMetric.MANHATTAN`, `DistanceMetric.EUCLIDEAN`. Distance computation is on the enum: `metric.compute(dx, dy)`.

### Names are not unique — use `version`

Uniqueness is on `(name, version)`, matching `monsters` and `npcs`. The wiki's infobox `name` field is frequently generic while page titles are not: four separate temples all declare `name = Temple`, and both a Kharidian Desert and a Wilderness location declare `name = Bandit Camp`. The version is derived from the page title — its parenthetical where there is one (`Bandit Camp (Wilderness)` gives `Wilderness`), otherwise the whole title when it differs from the name (`Lletya shrine` under name `Lletya`).

`by_name` without a version returns the unversioned row first, then versions alphabetically. Pass `version` to select a specific one, or use `all_by_name` to see every variant:

```python
Location.all_by_name(conn, "Chaos Temple")
# -> versions ['Asgarnia', 'Wilderness', 'church']

Location.by_name(conn, "Bandit Camp", version="Wilderness").x   # 3037
Location.by_name(conn, "Bandit Camp", version="Kharidian Desert").x   # 3171
```

Note that the linking scripts (`link_shop_locations.py`, `link_activity_locations.py`, and similar) match on location *name* text taken from other wiki pages, which usually carries no disambiguator. Where a name has several versions those links resolve to one of them arbitrarily.

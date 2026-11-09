# Boulder Bean Search

a project by **Lily Holmes**, Fall 2026

*inspired by a weekend where i went camping in wyoming and only ate canned baked beans and chef boyardee*


### Regularized breadth first search applied to finding canned beans

Bean Search turns Boulder County's road network into a graph and asks one question: **how many
beans can you get within N moves?** Grocery, convenience and dollar stores are goal nodes
(canned beans), along with two honorary beans: Cloud Gate ("The Bean") in Chicago and Boston
Common in Beantown. A beam search finds a route, and a cartoon map game lets you watch a little
bean buddy run it.

The game is not hosted anywhere. You run it on your own computer by following the steps below.


## Requirements

- Python **3.11+** (developed on 3.13)
- An internet connection. The first build downloads map data, and the game loads map tiles,
  fonts and Leaflet from the web.
- About 5 minutes for the first build


## Run the game on your computer

Run every command from the repo folder. The `data/` and `cache/` folders are created there.

```bash
# 1. get the code
git clone https://github.com/lily-harper/bean_search.git
cd bean_search

# 2. create a virtual environment and install
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# 3. build the bean graph (downloads OpenStreetMap data, ~4 min the first time)
.venv/bin/bean-search build --region boulder

# 4. start the game
.venv/bin/bean-search serve
```

Then open **http://127.0.0.1:8000** in your browser. Stop the server with `Ctrl+C`.

- **Port 8000 already in use?** Pick any free port: `.venv/bin/bean-search serve --port 9000`,
  then open `http://127.0.0.1:9000`.
- **Windows:** use `.venv\Scripts\pip` and `.venv\Scripts\bean-search` in place of
  `.venv/bin/...`.
- The server only listens on your own machine (`127.0.0.1`). It is not reachable from other
  computers.
- Rebuilds are faster, because OSMnx caches its downloads in `cache/`. OpenStreetMap changes over
  time, so your store count may differ slightly from someone else's.

### How to play

1. Click anywhere on the map (or on a can) to drop your bean buddy.
2. Pick a move budget with the slider.
3. Hit **GO!** and watch the buddy collect as many beans as it can.

A **move** is one road edge, about one block (~170 m on average in Boulder County). Chicago and
Boston are listed under "Far-away beans" with the number of moves they would really take.


## Command line

| Command | What it does |
|---|---|
| `bean-search build [--region boulder\|colorado]` | Download data and build the graph. `colorado` is much larger and slower. |
| `bean-search info data/boulder_bean_graph.pkl` | Print node, edge and bean counts |
| `bean-search search --lat 40.015 --lon -105.2705 --moves 150` | Run the search and print the beans as text |
| `bean-search serve [--port 8000] [--graph PATH]` | Start the map game |

`search` also takes `--width` (beam width, default 8) and `--branch` (beans tried per state,
default 4).


## How it works

**Graph.** A networkx `MultiDiGraph` built from:
- **Roads:** the OSMnx drive network for the region. Nodes are intersections, and edge `length`
  is in meters. Only the largest strongly connected part is kept, so every node can reach every
  other node.
- **Stores:** OpenStreetMap shops tagged `supermarket`, `convenience`, `grocery` or
  `variety_store`, fetched from the Overpass API. Same-name stores within 150 m are merged.
- **Goal nodes:** each bean location has `goal=True` and a `bean_type` of `canned`,
  `sculpture` or `city`. A short `connector=True` edge links it to its nearest intersection.
- **Far-away landmarks:** Cloud Gate and Boston Common each get a small local road network,
  joined to the region by `virtual=True` edges. A virtual edge's length is the straight-line
  distance × 1.25.

**Search.** A beam search over the number of beans collected. At each step, from every state in
the beam:
1. A move-limited Dijkstra, ordered by (moves, meters), finds every uncollected bean still in
   range. This works like a depth-limited BFS that breaks ties by road distance.
2. The state branches to its closest few beans.
3. All new states are ranked by `moves used + straight-line distance to the nearest uncollected
   bean`, converted to moves. The best `width` states are kept.

Virtual edges cost their length in moves, so Chicago (~10,800 moves) and Boston (~20,600 moves)
are only reachable with a huge budget.


## Tests

```bash
.venv/bin/pytest
```

The tests use small hand-made graphs and do not need the internet.


## Project layout

```
src/bean_search/
  config.py   regions, store tags, landmarks
  stores.py   Overpass API store fetch + dedupe
  roads.py    OSMnx road networks
  graph.py    assemble roads + bean goal nodes
  search.py   move-limited beam search
  server.py   local web server for the game
  cli.py      `bean-search` command
  web/        the map game (HTML, CSS, JS)
tests/
```


## Credits

**Map data and tiles**
- Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available
  under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
- Map tiles © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), served by
  the OpenStreetMap Foundation's tile servers. The game shows this credit on the map. Please
  follow the [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/): it
  is fine for personal, light use, but switch to another tile provider if you build on this for
  heavy or public use.
- Store locations are queried through the [Overpass API](https://overpass-api.de/), and place
  names are geocoded with [Nominatim](https://nominatim.org/) (both via OpenStreetMap).

**Libraries**
- [OSMnx](https://github.com/gboeing/osmnx) by Geoff Boeing, for downloading road networks
- [NetworkX](https://networkx.org/), [GeoPandas](https://geopandas.org/),
  [Shapely](https://shapely.readthedocs.io/), [NumPy](https://numpy.org/),
  [scikit-learn](https://scikit-learn.org/) and [Requests](https://requests.readthedocs.io/)
- [Leaflet](https://leafletjs.com/), for the interactive map
- [Luckiest Guy](https://fonts.google.com/specimen/Luckiest+Guy) and
  [Fredoka](https://fonts.google.com/specimen/Fredoka) fonts, via Google Fonts (SIL Open Font
  License)

**Bean landmarks**
- *Cloud Gate* ("The Bean"), Millennium Park, Chicago, by Anish Kapoor
- Boston Common, Boston ("Beantown")


## License

Copyright 2026 Lily Holmes

The code in this repository is licensed under the [Apache License, Version 2.0](LICENSE).

The OpenStreetMap data that `bean-search build` downloads into `data/` and `cache/` is **not**
covered by that license. It is © OpenStreetMap contributors under the ODbL. Those folders are
git-ignored. If you share a built graph, you must credit OpenStreetMap and follow the ODbL.

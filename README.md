# Boulder Bean Search

a project by **Lily Holmes**, Fall 2026

*inspired by a weekend where i went camping in wyoming and only ate canned baked beans and chef boyardee*


### Regularized breadth first search applied to finding canned beans


## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## Build the bean graph

```bash
.venv/bin/bean-search build --region boulder     # or --region colorado (much larger)
.venv/bin/bean-search info data/boulder_bean_graph.pkl
```

The graph is a networkx `MultiDiGraph`: road intersections from OSMnx, plus goal nodes
(`goal=True`, `bean_type` = `canned` | `sculpture` | `city`) for stores from the Overpass API,
Cloud Gate (Chicago), and Boston Common. Edge `length` is meters. The far-away landmarks are
reached through `virtual=True` long-haul edges (straight-line distance × 1.25).

## Play: most beans in N moves

```bash
.venv/bin/bean-search serve          # then open http://127.0.0.1:8000
.venv/bin/bean-search search --lat 40.015 --lon -105.2705 --moves 150   # same thing, text output
```

Click the map to drop your bean buddy, pick a move budget, and hit **GO!**. A move is one road
edge (about one block, ~170 m in Boulder County). The search is a beam search: each step runs a
move-limited Dijkstra (depth-limited BFS, ties broken by meters) from every state, branches to the
closest uncollected beans, and keeps the states with the lowest `moves used + straight-line
distance to the next bean`. Chicago and Boston cost their real distance in moves (~10k–20k).

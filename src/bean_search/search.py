"""Beam search: collect as many beans as possible within a move budget.

A *move* is one edge traversal (intersection -> intersection, or the short
connector into/out of a bean). Virtual long-haul edges cost
round(length / mean_road_edge_length) moves, so Chicago and Boston are
"as many blocks away as they really are".

Each beam step:
  1. Bounded Dijkstra from the state's node, ordered lexicographically by
     (moves, meters) and pruned at the move budget -- i.e. a depth-limited
     BFS that breaks ties by road distance. Results are cached per source.
  2. Branch to the `branch` closest uncollected beans that still fit.
  3. Rank states by  moves_used + h,  where h is the straight-line distance
     to the nearest uncollected bean, expressed in moves. Keep `width` best.
All states at depth d have d beans, so the deepest non-empty beam wins.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from .graph import goal_nodes

EARTH_RADIUS_M = 6_371_008.8


def _haversine_vec(lat, lon, lats, lons) -> np.ndarray:
    p1, p2 = np.radians(lat), np.radians(lats)
    dp, dl = p2 - p1, np.radians(lons - lon)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


@dataclass
class _Exploration:
    dist: dict  # node -> (moves, meters)
    prev: dict  # node -> predecessor node


@dataclass(frozen=True)
class _State:
    node: object
    collected: frozenset
    moves: int
    meters: float
    score: float
    parent: _State | None = field(default=None, compare=False)


@dataclass
class SearchResult:
    start_node: object
    budget: int
    moves: int
    meters: float
    goals: list  # collected goal nodes, in order
    route: list  # full node path, start -> last goal
    goal_route_index: list  # index into `route` where each goal is collected
    goal_moves: list  # cumulative moves used when each goal is collected


class BeanSearcher:
    def __init__(self, G: nx.MultiDiGraph):
        self.G = G
        self.goals = goal_nodes(G)
        self._goal_index = {g: i for i, g in enumerate(self.goals)}
        self._goal_lat = np.array([G.nodes[g]["y"] for g in self.goals])
        self._goal_lon = np.array([G.nodes[g]["x"] for g in self.goals])

        goal_set = set(self.goals)
        self._road_nodes = [n for n in G.nodes if n not in goal_set]
        self._road_lat = np.array([G.nodes[n]["y"] for n in self._road_nodes])
        self._road_lon = np.array([G.nodes[n]["x"] for n in self._road_nodes])

        road_lengths = [
            d["length"] for *_, d in G.edges(data=True) if not d.get("virtual") and not d.get("connector")
        ]
        self.mean_edge_m = float(np.mean(road_lengths)) if road_lengths else 100.0

        # Collapse multi-edges to the cheapest (moves, meters) per (u, v).
        best: dict[tuple, tuple[int, float]] = {}
        for u, v, d in G.edges(data=True):
            cost = (self.move_cost(d), d["length"])
            if (u, v) not in best or cost < best[(u, v)]:
                best[(u, v)] = cost
        self.adj: dict = {n: [] for n in G.nodes}
        for (u, v), (c, length) in best.items():
            self.adj[u].append((v, c, length))

        self._cache: dict[tuple, _Exploration] = {}

    # ---- costs & geometry -------------------------------------------------

    def move_cost(self, edge_data: dict) -> int:
        if edge_data.get("virtual"):
            return max(1, round(edge_data["length"] / self.mean_edge_m))
        return 1

    def nearest_road_node(self, lat: float, lon: float):
        i = int(np.argmin(_haversine_vec(lat, lon, self._road_lat, self._road_lon)))
        return self._road_nodes[i]

    def _heuristic_moves(self, node, collected: frozenset) -> float:
        mask = np.ones(len(self.goals), dtype=bool)
        for g in collected:
            mask[self._goal_index[g]] = False
        if not mask.any():
            return 0.0
        nd = self.G.nodes[node]
        d = _haversine_vec(nd["y"], nd["x"], self._goal_lat[mask], self._goal_lon[mask])
        return float(d.min()) / self.mean_edge_m

    # ---- bounded Dijkstra (depth-limited BFS ordered by meters) -----------

    def explore(self, source, max_moves: int) -> _Exploration:
        key = (source, max_moves)
        if key in self._cache:
            return self._cache[key]
        dist = {source: (0, 0.0)}
        prev = {source: None}
        tie = itertools.count()
        heap = [(0, 0.0, next(tie), source)]
        while heap:
            h, m, _, u = heapq.heappop(heap)
            if (h, m) > dist[u]:
                continue
            for v, c, length in self.adj[u]:
                nh = h + c
                if nh > max_moves:
                    continue
                nm = m + length
                if v not in dist or (nh, nm) < dist[v]:
                    dist[v] = (nh, nm)
                    prev[v] = u
                    heapq.heappush(heap, (nh, nm, next(tie), v))
        exp = _Exploration(dist, prev)
        self._cache[key] = exp
        return exp

    @staticmethod
    def _path(exp: _Exploration, target) -> list:
        path = [target]
        while exp.prev[path[-1]] is not None:
            path.append(exp.prev[path[-1]])
        return path[::-1]

    # ---- beam search -------------------------------------------------------

    def search(
        self,
        start_node,
        budget: int,
        width: int = 8,
        branch: int = 4,
    ) -> SearchResult:
        root = _State(start_node, frozenset(), 0, 0.0, 0.0)
        beam = [root]
        best = root
        while beam:
            children: dict[tuple, _State] = {}
            for s in beam:
                remaining = budget - s.moves
                exp = self.explore(s.node, budget)
                cands = sorted(
                    (hm[0], hm[1], self._goal_index[g], g)
                    for g in self.goals
                    if g not in s.collected
                    and (hm := exp.dist.get(g)) is not None
                    and hm[0] <= remaining
                )[:branch]
                for h, m, _, g in cands:
                    collected = s.collected | {g}
                    moves = s.moves + h
                    score = moves + self._heuristic_moves(g, collected)
                    child = _State(g, collected, moves, s.meters + m, score, s)
                    key = (g, collected)
                    if key not in children or child.moves < children[key].moves:
                        children[key] = child
            beam = sorted(children.values(), key=lambda st: (st.score, st.meters))[:width]
            if beam:
                best = min(beam, key=lambda st: (st.moves, st.meters))
        return self._result(best, start_node, budget)

    def _result(self, state: _State, start_node, budget: int) -> SearchResult:
        chain = []
        while state is not None:
            chain.append(state)
            state = state.parent
        chain.reverse()

        route = [start_node]
        goals, idx = [], []
        for prev_s, s in zip(chain, chain[1:]):
            leg = self._path(self.explore(prev_s.node, budget), s.node)
            route.extend(leg[1:])
            goals.append(s.node)
            idx.append(len(route) - 1)
        last = chain[-1]
        goal_moves = [s.moves for s in chain[1:]]
        return SearchResult(start_node, budget, last.moves, last.meters, goals, route, idx, goal_moves)


def route_coords(G: nx.MultiDiGraph, route: list) -> tuple[list[list[float]], list[int]]:
    """Expand a node route into [lat, lon] points using edge geometry.

    Returns (coords, node_to_coord_index) so callers can map route indices
    (e.g. where a bean is collected) onto the polyline.
    """
    if not route:
        return [], []
    n0 = G.nodes[route[0]]
    coords = [[n0["y"], n0["x"]]]
    node_idx = [0]
    for u, v in zip(route, route[1:]):
        data = min(G[u][v].values(), key=lambda d: d["length"])
        geom = data.get("geometry")
        if geom is not None:
            pts = [[lat, lon] for lon, lat in geom.coords][1:]
        else:
            nv = G.nodes[v]
            pts = [[nv["y"], nv["x"]]]
        coords.extend(pts)
        node_idx.append(len(coords) - 1)
    return coords, node_idx


def result_to_json(G: nx.MultiDiGraph, res: SearchResult) -> dict:
    coords, node_idx = route_coords(G, res.route)
    sn = G.nodes[res.start_node]
    return {
        "start": {"lat": sn["y"], "lon": sn["x"]},
        "budget": res.budget,
        "moves": res.moves,
        "meters": round(res.meters, 1),
        "path": coords,
        "collected": [
            {
                "id": str(g),
                "name": G.nodes[g].get("name"),
                "bean_type": G.nodes[g]["bean_type"],
                "lat": G.nodes[g]["y"],
                "lon": G.nodes[g]["x"],
                "path_index": node_idx[i],
                "moves": mv,
            }
            for g, i, mv in zip(res.goals, res.goal_route_index, res.goal_moves)
        ],
    }

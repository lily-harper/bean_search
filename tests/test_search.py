import networkx as nx

from bean_search import graph
from bean_search.geo import haversine_m
from bean_search.search import BeanSearcher, result_to_json
from bean_search.stores import BeanSite


def line_graph(n=10, step=0.002) -> nx.MultiDiGraph:
    """n intersections on an east-west street (~170 m apart)."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    for i in range(n):
        G.add_node(i, x=-105.27 + i * step, y=40.01)
    for i in range(n - 1):
        d = haversine_m(40.01, G.nodes[i]["x"], 40.01, G.nodes[i + 1]["x"])
        G.add_edge(i, i + 1, length=d)
        G.add_edge(i + 1, i, length=d)
    return G


def beans_at(G, idxs):
    sites = [BeanSite(f"node/{i}", f"store{i}", 40.0101, G.nodes[i]["x"], "canned") for i in idxs]
    graph.attach_sites(G, sites)
    return G


def test_budget_limits_collection():
    G = beans_at(line_graph(), [2, 4, 9])
    s = BeanSearcher(G)
    # start at 0: bean@2 costs 3 moves (2 road + connector)
    assert len(s.search(0, budget=2).goals) == 0
    assert len(s.search(0, budget=3).goals) == 1
    # 2 -> 4: out(1) + 2 road + in(1) = 4 more => 7 total
    assert len(s.search(0, budget=7).goals) == 2
    # 4 -> 9: 1 + 5 + 1 = 7 more => 14 total
    res = s.search(0, budget=14)
    assert [str(g) for g in res.goals] == ["bean:node/2", "bean:node/4", "bean:node/9"]
    assert res.moves == 14


def test_prefers_dense_cluster_over_nearest_single():
    # one bean 2 blocks west of start, three beans close together east
    G = line_graph(n=12)
    G = beans_at(G, [3, 9, 10, 11])
    s = BeanSearcher(G)
    res = s.search(5, budget=14, width=8, branch=4)
    assert len(res.goals) == 3
    assert {str(g) for g in res.goals} == {"bean:node/9", "bean:node/10", "bean:node/11"}


def test_route_is_connected_and_json_indexes_goals():
    G = beans_at(line_graph(), [2, 4])
    s = BeanSearcher(G)
    res = s.search(0, budget=20)
    for u, v in zip(res.route, res.route[1:]):
        assert G.has_edge(u, v)
    out = result_to_json(G, res)
    for c in out["collected"]:
        assert out["path"][c["path_index"]] == [c["lat"], c["lon"]]


def test_virtual_edges_cost_many_moves():
    G = beans_at(line_graph(), [2])
    G.add_node(99, x=-87.6233, y=41.8827)
    graph.connect_virtual(G, 9, 99)
    s = BeanSearcher(G)
    far = s.adj[9]
    cost = next(c for v, c, _ in far if v == 99)
    assert cost > 1000


def test_nearest_road_node_skips_goals():
    G = beans_at(line_graph(), [2])
    s = BeanSearcher(G)
    assert s.nearest_road_node(40.0101, G.nodes[2]["x"]) == 2

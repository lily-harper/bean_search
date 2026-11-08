import networkx as nx
import pytest

from bean_search import graph
from bean_search.geo import haversine_m
from bean_search.stores import BeanSite


def tiny_road_graph() -> nx.MultiDiGraph:
    """Three intersections in a line near Boulder, ~850 m apart."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    coords = {1: (-105.27, 40.01), 2: (-105.26, 40.01), 3: (-105.25, 40.01)}
    for n, (x, y) in coords.items():
        G.add_node(n, x=x, y=y)
    for a, b in [(1, 2), (2, 3)]:
        d = haversine_m(coords[a][1], coords[a][0], coords[b][1], coords[b][0])
        G.add_edge(a, b, length=d)
        G.add_edge(b, a, length=d)
    return G


def test_haversine_known_distance():
    # Cloud Gate -> Boston Common is roughly 1,370 km
    d = haversine_m(41.8827, -87.6233, 42.3550, -71.0660)
    assert 1_340_000 < d < 1_400_000


def test_attach_sites_adds_goal_nodes_with_connectors():
    G = tiny_road_graph()
    sites = [
        BeanSite("node/10", "Store A", 40.0102, -105.2501, "canned"),
        BeanSite("landmark/x", "Landmark", 40.0101, -105.2699, "sculpture"),
    ]
    graph.attach_sites(G, sites)

    a, lm = "bean:node/10", "bean:landmark/x"
    assert G.nodes[a]["goal"] and G.nodes[a]["bean_type"] == "canned"
    assert G.has_edge(3, a) and G.has_edge(a, 3)  # nearest road node is 3
    assert G.has_edge(1, lm) and G.has_edge(lm, 1)
    assert all(d["connector"] for _, _, d in G.edges(a, data=True))
    assert set(graph.goal_nodes(G)) == {a, lm}
    assert graph.goal_nodes(G, "sculpture") == [lm]

    # Goal is reachable by road from the far end.
    assert nx.has_path(G, 1, a)


def test_attach_sites_refuses_second_call():
    G = tiny_road_graph()
    graph.attach_sites(G, [BeanSite("node/10", None, 40.01, -105.25, "canned")])
    with pytest.raises(ValueError):
        graph.attach_sites(G, [BeanSite("node/11", None, 40.01, -105.27, "canned")])


def test_connect_virtual_uses_circuity():
    G = tiny_road_graph()
    G.add_node(99, x=-87.6233, y=41.8827)  # Chicago
    length = graph.connect_virtual(G, 3, 99, circuity=1.5)
    straight = haversine_m(40.01, -105.25, 41.8827, -87.6233)
    assert length == pytest.approx(straight * 1.5)
    assert G[3][99][0]["virtual"] and G[99][3][0]["virtual"]


def test_summarize_counts():
    G = tiny_road_graph()
    graph.attach_sites(G, [BeanSite("node/10", None, 40.01, -105.25, "canned")])
    s = graph.summarize(G)
    assert s["road_nodes"] == 3
    assert s["goals"] == 1
    assert s["goals_by_type"]["canned"] == 1

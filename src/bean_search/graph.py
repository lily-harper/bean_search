"""Assemble the bean graph: road intersections plus goal nodes with beans.

Graph conventions (networkx MultiDiGraph, EPSG:4326):
  * Road nodes: osmnx intersection ids (int), attrs `x` (lon), `y` (lat).
  * Goal nodes: id "bean:<site id>", attrs `x`, `y`, `goal=True`,
    `bean_type` in {canned, sculpture, city}, `name`, `site_id`.
  * Every edge has `length` in meters. Edges added here are tagged:
      - `connector=True`: goal node <-> nearest road node (both directions)
      - `virtual=True`:  long-haul link from the region network to a far
        landmark's local network (straight-line * CIRCUITY_FACTOR)
"""

import logging
from collections.abc import Sequence

import networkx as nx
import osmnx as ox

from . import config, roads, stores
from .config import Landmark
from .geo import haversine_m
from .stores import BeanSite

log = logging.getLogger(__name__)


def goal_id(site: BeanSite) -> str:
    return f"bean:{site.id}"


def is_goal(G: nx.MultiDiGraph, node) -> bool:
    return bool(G.nodes[node].get("goal"))


def goal_nodes(G: nx.MultiDiGraph, bean_type: str | None = None) -> list:
    return [
        n
        for n, d in G.nodes(data=True)
        if d.get("goal") and (bean_type is None or d.get("bean_type") == bean_type)
    ]


def attach_sites(G: nx.MultiDiGraph, sites: Sequence[BeanSite]) -> nx.MultiDiGraph:
    """Add a goal node per site, linked both ways to its nearest road node.

    Nearest-node lookup is done in one batch against road nodes only, so call
    this once with every site.
    """
    if not sites:
        return G
    if goal_nodes(G):
        raise ValueError("attach_sites must run before any goal nodes exist")

    road_ids = ox.distance.nearest_nodes(
        G, X=[s.lon for s in sites], Y=[s.lat for s in sites]
    )
    for site, road in zip(sites, road_ids):
        gid = goal_id(site)
        G.add_node(
            gid,
            x=site.lon,
            y=site.lat,
            goal=True,
            bean_type=site.bean_type,
            name=site.name,
            site_id=site.id,
        )
        rd = G.nodes[road]
        d = haversine_m(site.lat, site.lon, rd["y"], rd["x"])
        G.add_edge(road, gid, length=d, connector=True)
        G.add_edge(gid, road, length=d, connector=True)
    return G


def connect_virtual(
    G: nx.MultiDiGraph,
    region_node,
    landmark_node,
    circuity: float = config.CIRCUITY_FACTOR,
) -> float:
    """Link two road nodes with a bidirectional virtual long-haul edge. Returns length."""
    a, b = G.nodes[region_node], G.nodes[landmark_node]
    length = haversine_m(a["y"], a["x"], b["y"], b["x"]) * circuity
    G.add_edge(region_node, landmark_node, length=length, virtual=True)
    G.add_edge(landmark_node, region_node, length=length, virtual=True)
    return length


def build_bean_graph(
    region: str = config.DEFAULT_REGION,
    landmarks: Sequence[Landmark] = config.LANDMARKS,
    connect_landmarks: bool = True,
) -> nx.MultiDiGraph:
    """Download everything and return the combined bean graph."""
    place = config.REGIONS[region]
    log.info("Geocoding %s", place)
    boundary = roads.region_boundary(place)

    log.info("Downloading %s road network", region)
    G_region = roads.region_graph(boundary)

    log.info("Fetching stores from Overpass")
    store_sites = stores.fetch_stores(boundary)
    log.info("  %d stores", len(store_sites))

    G = G_region.copy()
    links: list[tuple] = []  # (region_node, landmark_road_node)
    for lm in landmarks:
        log.info("Downloading local road network around %s", lm.name)
        G_lm = roads.landmark_graph(lm)
        if connect_landmarks:
            region_node = ox.distance.nearest_nodes(G_region, X=lm.lon, Y=lm.lat)
            rn = G_region.nodes[region_node]
            lm_node = ox.distance.nearest_nodes(G_lm, X=rn["x"], Y=rn["y"])
            links.append((region_node, lm_node))
        G = nx.compose(G, G_lm)

    for region_node, lm_node in links:
        connect_virtual(G, region_node, lm_node)

    landmark_sites = [
        BeanSite(id=f"landmark/{lm.key}", name=lm.name, lat=lm.lat, lon=lm.lon, bean_type=lm.bean_type)
        for lm in landmarks
    ]
    attach_sites(G, [*store_sites, *landmark_sites])
    G.graph["region"] = region
    return G


def summarize(G: nx.MultiDiGraph) -> dict:
    goals = goal_nodes(G)
    by_type = {t: 0 for t in config.BEAN_TYPES}
    for n in goals:
        by_type[G.nodes[n]["bean_type"]] = by_type.get(G.nodes[n]["bean_type"], 0) + 1
    return {
        "region": G.graph.get("region"),
        "nodes": G.number_of_nodes(),
        "road_nodes": G.number_of_nodes() - len(goals),
        "edges": G.number_of_edges(),
        "virtual_edges": sum(1 for *_, d in G.edges(data=True) if d.get("virtual")),
        "goals": len(goals),
        "goals_by_type": by_type,
    }

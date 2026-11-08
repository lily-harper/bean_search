"""Download road networks with osmnx. Nodes are intersections, edge `length` is meters."""

import networkx as nx
import osmnx as ox
from shapely.geometry.base import BaseGeometry

from . import config
from .config import Landmark


def region_boundary(place: str) -> BaseGeometry:
    """Geocode a place name to its boundary polygon (lon/lat, EPSG:4326)."""
    gdf = ox.geocode_to_gdf(place)
    return gdf.geometry.union_all()


def _routable(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Keep the largest strongly connected component.

    Clipping a directed road network leaves one-way fragments you can enter
    but not leave (or vice versa); goals attached there would be unreachable.
    """
    return ox.truncate.largest_component(G, strongly=True)


def region_graph(boundary: BaseGeometry) -> nx.MultiDiGraph:
    return _routable(ox.graph_from_polygon(boundary, network_type=config.NETWORK_TYPE))


def landmark_graph(landmark: Landmark, radius_m: int = config.LANDMARK_RADIUS_M) -> nx.MultiDiGraph:
    return _routable(
        ox.graph_from_point((landmark.lat, landmark.lon), dist=radius_m, network_type=config.NETWORK_TYPE)
    )

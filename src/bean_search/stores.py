"""Fetch grocery-type stores (canned-bean sources) from the Overpass API."""

from collections.abc import Iterable
from dataclasses import dataclass, field

import requests
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from . import config
from .geo import haversine_m

DEDUPE_RADIUS_M = 150


@dataclass(frozen=True)
class BeanSite:
    """A place that has beans, before it is attached to the road graph."""

    id: str  # e.g. "node/123", "way/456", "landmark/the_bean"
    name: str | None
    lat: float
    lon: float
    bean_type: str
    tags: dict = field(default_factory=dict, compare=False, hash=False)


def build_query(
    bbox: tuple[float, float, float, float],
    shop_tags: Iterable[str] = config.STORE_SHOP_TAGS,
    timeout: int = config.OVERPASS_TIMEOUT_S,
) -> str:
    """Overpass QL for shops in a (south, west, north, east) bounding box.

    `nwr` + `out center` returns nodes with lat/lon and ways/relations with a
    computed center point, so building-outline stores are included.
    """
    south, west, north, east = bbox
    pattern = "|".join(shop_tags)
    return (
        f"[out:json][timeout:{timeout}];\n"
        f'nwr["shop"~"^({pattern})$"]({south},{west},{north},{east});\n'
        "out center tags;"
    )


def parse_elements(data: dict, bean_type: str = config.CANNED) -> list[BeanSite]:
    """Convert an Overpass JSON response into BeanSites."""
    sites: list[BeanSite] = []
    for el in data.get("elements", []):
        if "lat" in el and "lon" in el:
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue  # no usable coordinate
        tags = el.get("tags", {})
        sites.append(
            BeanSite(
                id=f"{el['type']}/{el['id']}",
                name=tags.get("name") or tags.get("brand"),
                lat=float(lat),
                lon=float(lon),
                bean_type=bean_type,
                tags=tags,
            )
        )
    return sites


def fetch_stores(
    boundary: BaseGeometry,
    shop_tags: Iterable[str] = config.STORE_SHOP_TAGS,
    url: str = config.OVERPASS_URL,
    session: requests.Session | None = None,
) -> list[BeanSite]:
    """Query Overpass for stores inside `boundary` (a lon/lat polygon)."""
    west, south, east, north = boundary.bounds
    query = build_query((south, west, north, east), shop_tags)
    http = session or requests
    resp = http.post(
        url,
        data={"data": query},
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.OVERPASS_TIMEOUT_S + 30,
    )
    resp.raise_for_status()
    sites = parse_elements(resp.json())
    # The query is a bbox; trim to the actual region polygon.
    sites = [s for s in sites if boundary.contains(Point(s.lon, s.lat))]
    return dedupe_sites(sites)


def dedupe_sites(sites: list[BeanSite], radius_m: float = DEDUPE_RADIUS_M) -> list[BeanSite]:
    """Drop same-named stores within `radius_m` of one already kept.

    OSM often has a store twice (an old POI node plus a building outline).
    Unnamed stores are never merged.
    """
    kept: list[BeanSite] = []
    by_name: dict[str, list[BeanSite]] = {}
    for s in sites:
        key = (s.name or "").strip().lower()
        if key and any(haversine_m(s.lat, s.lon, k.lat, k.lon) <= radius_m for k in by_name.get(key, [])):
            continue
        kept.append(s)
        if key:
            by_name.setdefault(key, []).append(s)
    return kept

"""Static configuration: regions, store tags, and bean landmarks."""

from dataclasses import dataclass

# Region key -> place query understood by Nominatim / osmnx.
REGIONS: dict[str, str] = {
    "boulder": "Boulder County, Colorado, USA",
    "colorado": "Colorado, USA",
}
DEFAULT_REGION = "boulder"

# OSM `shop=*` values treated as places that sell canned beans.
# variety_store covers dollar stores, which matter in rural areas.
STORE_SHOP_TAGS: tuple[str, ...] = ("supermarket", "convenience", "grocery", "variety_store")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_S = 180
USER_AGENT = "bean_search/0.1 (educational project)"

# osmnx road network type for every graph we download.
NETWORK_TYPE = "drive"

# Radius of the small local road graph downloaded around each landmark.
LANDMARK_RADIUS_M = 1500

# Landmarks far outside the region get a single "virtual" long-haul edge whose
# length is the straight-line distance times this factor (typical road
# circuity is ~1.2-1.4).
CIRCUITY_FACTOR = 1.25

# bean_type values
CANNED = "canned"
SCULPTURE = "sculpture"
CITY = "city"
BEAN_TYPES = (CANNED, SCULPTURE, CITY)


@dataclass(frozen=True)
class Landmark:
    key: str
    name: str
    lat: float
    lon: float
    bean_type: str


LANDMARKS: tuple[Landmark, ...] = (
    Landmark("the_bean", "Cloud Gate (The Bean), Chicago", 41.8827, -87.6233, SCULPTURE),
    Landmark("beantown", "Boston Common (Beantown), Boston", 42.3550, -71.0660, CITY),
)

from shapely.geometry import box

from bean_search import stores

OVERPASS_RESPONSE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.01, "lon": -105.27, "tags": {"shop": "supermarket", "name": "King Soopers"}},
        {"type": "way", "id": 2, "center": {"lat": 40.02, "lon": -105.25}, "tags": {"shop": "variety_store", "brand": "Dollar General"}},
        {"type": "way", "id": 3, "tags": {"shop": "grocery"}},  # no coordinate -> skipped
        {"type": "node", "id": 4, "lat": 45.0, "lon": -100.0, "tags": {"shop": "convenience"}},  # outside region
    ]
}


def test_build_query_uses_bbox_and_tags():
    q = stores.build_query((39.9, -105.7, 40.3, -105.0), ["supermarket", "grocery"], timeout=60)
    assert "[timeout:60]" in q
    assert '"^(supermarket|grocery)$"' in q
    assert "(39.9,-105.7,40.3,-105.0)" in q
    assert "out center" in q


def test_parse_elements_handles_nodes_and_ways():
    sites = stores.parse_elements(OVERPASS_RESPONSE)
    assert [s.id for s in sites] == ["node/1", "way/2", "node/4"]
    assert sites[0].name == "King Soopers"
    assert sites[1].name == "Dollar General"  # falls back to brand
    assert (sites[1].lat, sites[1].lon) == (40.02, -105.25)
    assert all(s.bean_type == "canned" for s in sites)


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return OVERPASS_RESPONSE


class _FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return _FakeResp()


def test_dedupe_merges_same_name_nearby_only():
    S = stores.BeanSite
    sites = [
        S("node/1", "Sprouts", 40.01581, -105.26166, "canned"),
        S("node/2", "sprouts ", 40.01589, -105.26097, "canned"),  # ~60 m away, same store
        S("node/3", "Sprouts", 40.05, -105.26, "canned"),  # different store across town
        S("node/4", None, 40.01581, -105.26166, "canned"),  # unnamed: kept
        S("node/5", None, 40.01582, -105.26166, "canned"),
    ]
    assert [s.id for s in stores.dedupe_sites(sites)] == ["node/1", "node/3", "node/4", "node/5"]


def test_fetch_stores_filters_to_boundary():
    session = _FakeSession()
    boundary = box(-105.7, 39.9, -105.0, 40.3)  # rough Boulder County box
    sites = stores.fetch_stores(boundary, session=session)
    assert [s.id for s in sites] == ["node/1", "way/2"]
    assert "data" in session.calls[0][1]["data"]

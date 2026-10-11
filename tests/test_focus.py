"""The product covers Punjab, Haryana, Delhi, Rajasthan, UP and Chandigarh. The domain reaches
past the international border on purpose (fires there reach the NCR), so everything that is
named or published must be filtered; the fires themselves must not be."""
from common import domain
from ingest_cpcb import openaq_live
from zones import burning, zones

# (name, lat, lon, inside the focus states?)
PLACES = [
    ("Amritsar", 31.63, 74.87, True), ("Gurdaspur", 32.04, 75.40, True),
    ("Pathankot", 32.27, 75.65, True), ("Batala", 31.82, 75.20, True),
    ("Firozpur", 30.93, 74.61, True), ("Fazilka", 30.40, 74.03, True),
    ("Abohar", 30.14, 74.20, True), ("Sri Ganganagar", 29.92, 73.88, True),
    ("Bikaner", 28.02, 73.31, True), ("Delhi", 28.61, 77.21, True),
    ("Ludhiana", 30.90, 75.86, True), ("Chandigarh", 30.73, 76.78, True),
    ("Lahore", 31.55, 74.34, False), ("Kasur", 31.12, 74.45, False),
    ("Sheikhupura", 31.71, 73.98, False), ("Muridke", 31.80, 74.26, False),
    ("Narowal", 32.10, 74.87, False), ("Sialkot", 32.49, 74.53, False),
    ("Faisalabad", 31.42, 73.08, False), ("Gujranwala", 32.16, 74.19, False),
]


def test_border_separates_towns_only_tens_of_km_apart():
    for name, lat, lon, want in PLACES:
        assert domain.in_focus_states(lat, lon) is want, name


def test_border_longitude_increases_northwards_and_is_clamped():
    assert domain.border_lon(26.0) == domain.border_lon(27.0)       # clamped south
    assert domain.border_lon(33.0) == domain.border_lon(32.5)       # clamped north
    lons = [domain.border_lon(la) for la in (29.0, 30.0, 31.0, 32.0, 32.5)]
    assert lons == sorted(lons)


def test_focus_is_a_subset_of_the_domain():
    assert domain.in_focus_states(31.63, 74.87) is True
    assert domain.in_focus_states(19.0, 72.8) is False             # Mumbai: outside the domain
    assert domain.in_focus_states(31.63, 95.0) is False            # east of the domain


def test_no_pakistani_places_remain_in_the_published_lists():
    pk = {"lahore", "kasur", "sheikhupura", "gujranwala", "sialkot", "faisalabad", "okara",
          "sahiwal", "bahawalnagar", "pakpattan", "depalpur", "chunian", "nankana sahib",
          "hafizabad", "pattoki", "renala khurd", "arifwala", "jaranwala", "narowal",
          "muridke", "raiwind"}
    assert not {t[0].lower() for t in burning.TOWNS} & pk
    assert not {z["name"].lower() for z in zones.ZONES} & pk
    # and every gazetteer town and exposure zone is itself inside the focus states
    for name, lat, lon in burning.TOWNS:
        assert domain.in_focus_states(lat, lon), f"gazetteer town outside focus: {name}"
    for z in zones.ZONES:
        assert domain.in_focus_states(z["lat"], z["lon"]), f"zone outside focus: {z['name']}"


def test_stations_are_filtered_to_india_by_country_code():
    def loc(lid, cc, lat=31.6, lon=74.9):
        return {"id": lid, "name": "x", "country": {"code": cc},
                "coordinates": {"latitude": lat, "longitude": lon},
                "datetimeLast": {"utc": "2026-10-07T11:30:00Z"}, "sensors": []}

    import datetime
    now = datetime.datetime(2026, 10, 7, 12, 0, tzinfo=datetime.timezone.utc)
    out = openaq_live.fresh_locations([loc(1, "IN"), loc(2, "PK", 31.55, 74.34), loc(3, "pk")], now)
    assert [lg["id"] for lg in out] == [1]
    assert {"IN"} == openaq_live.FOCUS_COUNTRIES


def test_fires_are_not_restricted_to_the_focus_states():
    """Pakistani Punjab burning is a real source for Delhi: it must stay in the physics."""
    assert bool(domain.in_domain(31.55, 74.34))          # Lahore is inside the model domain
    assert domain.in_focus_states(31.55, 74.34) is False  # but is never named or published

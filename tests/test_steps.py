from datetime import datetime, timedelta, timezone

from common import domain
from common.storage import LocalStorage
from forecast import steps
from forecast.run import Params
from ingest_firms import firms
from sample.schools import in_school_window
from tests.conftest import wind_json
from tests.test_firms import HEADER, ROWS

NOW = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)  # 11:30 IST


def aq_json(hours=80, t0=datetime(2026, 9, 25, 0, tzinfo=timezone.utc), value=80.0):
    times = [(t0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(hours)]
    layer = [[value] * domain.WIND_NLON for _ in range(domain.WIND_NLAT)]
    return {"lats": domain.wind_lats().tolist(), "lons": domain.wind_lons().tolist(), "times": times,
            "pm25": [layer for _ in times], "pm10": [layer for _ in times], "source": "synthetic"}


SCHOOLS = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [77.11, 28.71]},
     "properties": {"id": "osm-node-1", "name": "Govt Boys SSS Rohini", "named": True}},
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [75.5, 30.5]},
     "properties": {"id": "osm-node-2", "name": "Near the fires", "named": True}},
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [77.2, 28.6]},
     "properties": {"id": "osm-node-3", "name": None, "named": False}},
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [72.0, 19.0]},
     "properties": {"id": "osm-node-4", "name": "Mumbai school", "named": True}},
]}


def _stores(tmp_path):
    sin, sout = LocalStorage(tmp_path / "in"), LocalStorage(tmp_path / "out")
    sin.put_text(firms.raw_key("VIIRS_NOAA20_NRT", NOW), HEADER + ROWS, "text/csv")
    sin.put_json("raw/openmeteo/x/wind.json", wind_json(u=3.0, v=-1.0, blh=400.0))
    sin.put_json("raw/openmeteo/x/aq.json", aq_json())
    sin.put_json("raw/openmeteo/latest.json", {"id": "x", "windKey": "raw/openmeteo/x/wind.json", "aqKey": "raw/openmeteo/x/aq.json"})
    sin.put_json("static/schools.geojson", SCHOOLS)
    return sin, sout


def test_in_school_window():
    from common.timeutil import IST

    assert in_school_window(datetime(2026, 9, 26, 8, 0, tzinfo=IST))
    assert in_school_window(datetime(2026, 9, 26, 13, 59, tzinfo=IST))
    assert not in_school_window(datetime(2026, 9, 26, 14, 0, tzinfo=IST))
    assert in_school_window(datetime(2026, 9, 26, 15, 30, tzinfo=IST))
    assert not in_school_window(datetime(2026, 9, 26, 16, 0, tzinfo=IST))


def test_run_all_uncalibrated_then_calibrated(tmp_path):
    sin, sout = _stores(tmp_path)
    ctx = steps.run_all(sin, sout, now=NOW, hours=3, params=Params(seed=1, spinup_h=6))
    rid = ctx["runId"]
    assert rid == "20260926T0600Z"
    m = sout.get_json(f"runs/{rid}/manifest.json")
    assert m["calibration"]["status"] == "uncalibrated" and m["overlay"]["mode"] == "relative"
    assert len(m["hours"]) == 4 and sout.get_json("runs/latest.json")["runId"] == rid
    assert sout.exists(f"runs/{rid}/overlay/03.png") and sout.exists(f"runs/{rid}/grid/03.json")
    assert sout.exists(f"runs/{rid}/background.json") and sout.exists(f"runs/{rid}/fires.geojson")
    assert sout.exists(f"work/{rid}/raw.npz") and sout.exists(f"work/{rid}/inputs.json")
    layer = sout.get_json(f"runs/{rid}/schools.json")
    assert layer["calibrated"] is False and len(layer["features"]) == 2   # named + in-domain only
    assert all(f["properties"]["dayTier"] is None for f in layer["features"])
    bg = sout.get_json(f"runs/{rid}/background.json")
    assert len(bg["pm25"]) == 4 and bg["pm25"][0][0][0] == 80.0

    # now with a fitted k: tiers appear and the overlay is in CPCB units
    sin.put_json("validation/latest/calibration.json", {"k": 5.0e10, "r2": 0.5, "mae": 30.0,
                                                        "window": "2024-11-01..2024-11-20", "stations": 12})
    ctx = steps.run_all(sin, sout, now=NOW, hours=3, params=Params(seed=1, spinup_h=6))
    m = sout.get_json(f"runs/{rid}/manifest.json")
    assert m["calibration"]["status"] == "calibrated" and m["calibration"]["k"] == 5.0e10
    assert m["overlay"]["mode"] == "cpcb" and m["calibration"]["r2"] == 0.5
    layer = sout.get_json(f"runs/{rid}/schools.json")
    assert layer["calibrated"] is True
    tiers = {f["properties"]["id"]: f["properties"]["dayTier"] for f in layer["features"]}
    assert set(tiers.values()) <= {"T0", "T1", "T2", "T3", "T4"}
    grid = sout.get_json(f"runs/{rid}/grid/01.json")
    assert grid["units"] == "ug/m3"
    assert ctx["schools"]["named"] == 2 and ctx["schools"]["count"] == 3


def test_calibrated_run_puts_intervals_and_dose_on_the_card(tmp_path):
    """The bands are computed per hour and must survive into the DynamoDB item, the public
    card and the hourly rows - every hand-picked key list on the way out has to carry them."""
    sin, sout = _stores(tmp_path)
    sin.put_json("validation/latest/calibration.json", {
        "k": 5.0e10, "r2": 0.5, "mae": 30.0, "window": "x", "stations": 2,
        "conformal": {"q80": 40.0, "q90": 60.0, "n": 100},
        "conformalByLead": {"lead01_24": {"q90": 55.0}, "lead25_48": {"q90": 70.0}},
    })
    sin.put_json("static/schools.geojson", {"type": "FeatureCollection", "features": [
        {**SCHOOLS["features"][0], "properties": {**SCHOOLS["features"][0]["properties"], "demo": True}}]})
    ctx = steps.run_all(sin, sout, now=NOW, hours=30, params=Params(seed=1, spinup_h=6))
    rid = ctx["runId"]
    card = sout.get_json(f"runs/{rid}/protocol/osm-node-1.json")
    assert card, "demo school card not published"
    rows = [h for h in card["hourly"] if h.get("tier")]
    assert rows and all("pm25Lo" in h and "aqiHi" in h for h in rows)
    assert rows[0]["halfWidth"] == 55.0              # lead 1-24 bucket
    assert rows[-1]["halfWidth"] == 70.0             # lead 25-48 bucket (hour 30)
    assert all(h["pm25Lo"] <= h["pm25Total"] <= h["pm25Hi"] for h in rows)
    assert card["interval"] is not None and card["interval"]["aqiLo"] <= card["interval"]["aqi"] <= card["interval"]["aqiHi"]
    assert card["dose"] is not None and card["dose"]["totalUg"] > 0 and card["dose"]["worstHour"]["hourIst"]
    assert card["calibration"]["conformal"]["q90"] == 60.0
    # and the private copy the principal's API reads is the same object
    assert sout.get_json(f"work/{rid}/cards/osm-node-1.json")["dose"] == card["dose"]


def test_entity_card_that_overwrites_a_school_card_keeps_intervals_and_dose(tmp_path):
    """osm-way-388242027 is both a schools.geojson demo feature and an actors.json entity; the
    entity card is written last to the same S3 keys. It must carry the same extras, or the
    served card silently loses them (the 2026-10-07 production bug)."""
    sin, sout = _stores(tmp_path)
    sin.put_json("validation/latest/calibration.json", {
        "k": 5.0e10, "r2": 0.5, "mae": 30.0, "window": "x", "stations": 2,
        "conformal": {"q90": 60.0, "n": 100},
        "conformalByLead": {"lead01_24": {"q90": 55.0}, "lead25_48": {"q90": 70.0}},
    })
    feat = SCHOOLS["features"][0]
    sin.put_json("static/schools.geojson", {"type": "FeatureCollection", "features": [
        {**feat, "properties": {**feat["properties"], "demo": True}}]})
    lon, lat = feat["geometry"]["coordinates"]
    sin.put_json("static/actors.json", {"entities": [
        {"id": "osm-node-1", "type": "school", "name": "Govt Boys SSS Rohini", "lat": lat, "lon": lon,
         "demo": True, "students": 900}]})
    ctx = steps.run_all(sin, sout, now=NOW, hours=30, params=Params(seed=1, spinup_h=6))
    rid = ctx["runId"]
    card = sout.get_json(f"runs/{rid}/protocol/osm-node-1.json")
    assert card["entityId"] == "osm-node-1", "entity card should be the one that is served"
    rows = [h for h in card["hourly"] if h.get("tier")]
    assert rows and all("pm25Lo" in h for h in rows), "entity path dropped the bands"
    assert rows[0]["halfWidth"] == 55.0 and rows[-1]["halfWidth"] == 70.0
    assert card["interval"] and card["dose"], "entity path dropped interval/dose"
    assert card["calibration"]["conformalByLead"]["lead25_48"]["q90"] == 70.0

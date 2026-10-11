from datetime import datetime, timedelta, timezone

import numpy as np

from common import domain
from forecast.run import Params, run_forecast
from forecast.wind import WindField
from tests.conftest import wind_json
from tests.test_steps import aq_json
from zones import burning, ndvi
from zones.zones import ZONES, zone_summaries

T0 = datetime(2026, 10, 5, 6, tzinfo=timezone.utc)


def _fire(lat, lon, hours_ago, frp=10.0):
    return {"lat": lat, "lon": lon, "frp": frp, "acqUtc": (T0 - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "satellite": "N", "source": "s", "confidence": "n", "brightness": 1}


def test_zone_summaries_rank_and_fields():
    w = WindField(wind_json(u=2.0, v=-1.0, blh=400.0, hours=90, t0=datetime(2026, 10, 4, 0, tzinfo=timezone.utc)))
    aq = aq_json(hours=90, t0=datetime(2026, 10, 4, 0, tzinfo=timezone.utc), value=90.0)
    aq["no2"] = [[[50.0] * domain.WIND_NLON for _ in range(domain.WIND_NLAT)] for _ in aq["times"]]
    fires = [_fire(30.9, 75.8, 3.0, frp=50.0) for _ in range(20)]   # on top of Ludhiana
    res = run_forecast(T0, fires, w, Params(seed=1, spinup_h=6), hours=6)
    z = zone_summaries(res, aq, k=5.0e11)
    assert len(z["zones"]) >= 8 and z["calibrated"]
    lud = next(r for r in z["zones"] if r["id"] == "ludhiana")
    assert lud["peak"]["pm25Fire"] > 0 and lud["now"]["no2"] == 50.0 and lud["now"]["no2Band"] == "moderate"
    assert z["rankingNow"][0] == "ludhiana" and lud["peak"]["stubbleShare"] > 0
    assert all(r["now"]["pm25Background"] == 90.0 for r in z["zones"])
    assert ZONES[0]["id"] == "delhi"


def test_burn_risk_scores_and_categories():
    fires = [_fire(30.5, 75.5, h) for h in (1, 2, 3, 30, 31)] + [_fire(29.0, 76.0, 40)]
    risk = burning.burn_risk(fires, T0, clim=None, ndvi_change=None, rain48=None)
    top = risk["topBurning"][0]
    assert top["fires24"] == 3 and top["fires48"] == 5 and top["category"] in ("Low", "Moderate", "High", "Extreme")
    cell = next(f["properties"] for f in risk["features"] if f["properties"]["fires24"] == 3)
    assert cell["score"] >= 35 and cell["components"]["recent"] == 35
    assert burning.category(10) == "Low" and burning.category(80) == "Extreme"
    assert risk["inputs"] == {"fires48": 6, "climatology": False, "ndvi": False, "rain": False}


def test_rain_and_ndvi_move_the_score():
    fires = [_fire(30.5, 75.5, h) for h in (1, 2, 3)]
    i, j = burning.cell_of(30.5, 75.5)
    base = burning.burn_risk(fires, T0, None, None, None)["features"][0]["properties"]["score"]
    rain = np.zeros((burning.NLAT, burning.NLON))
    rain[i, j] = 10.0
    wet = burning.burn_risk(fires, T0, None, None, rain)["features"][0]["properties"]["score"]
    nd = np.full((burning.NLAT, burning.NLON), np.nan)
    nd[i, j] = -0.2
    harvested = burning.burn_risk(fires, T0, None, nd, None)["features"][0]["properties"]["score"]
    assert wet == base - 10 and harvested == base + 15


def test_climatology_window_from_table():
    days = [f"2024-10-{d:02d}" for d in range(1, 31)]
    counts = np.zeros((30, burning.NLAT, burning.NLON))
    counts[:, 3, 4] = 2.0
    table = {"days": days, "counts": counts.tolist()}
    clim = burning.climatology(table, datetime(2026, 10, 15, tzinfo=timezone.utc))
    assert clim[3, 4] == 2.0 and clim.sum() == 2.0
    assert burning.climatology(None, T0) is None


def test_ndvi_colormap_parse_and_tile_geometry():
    xml = '''<ColorMap><Entries>
      <ColorMapEntry rgb="0,0,0" transparent="true" value="[0,0]"/>
      <ColorMapEntry rgb="191,222,120" value="[0.40,0.42)" label="0.41"/>
      <ColorMapEntry rgb="10,80,10" sourceValue="[0.80,0.82)"/>
    </Entries></ColorMap>'''
    cm = ndvi.parse_colormap(xml)
    assert cm == {(191, 222, 120): 0.41, (10, 80, 10): 0.81}
    x, y = ndvi._tile_xy(32.5, 73.0, 7)
    lats, lons = ndvi._pixel_latlon(x, y, 7)
    assert lons[0] <= 73.0 < lons[-1] + 3 and lats[0] >= 32.5 >= lats[-1] - 3

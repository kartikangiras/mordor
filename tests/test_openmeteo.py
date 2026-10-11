import math

from common import domain
from ingest_weather import openmeteo as om


def _point(lat, lon, n=3):
    return {"latitude": lat, "longitude": lon, "hourly": {
        "time": [f"2026-09-26T0{i}:00" for i in range(n)],
        "wind_speed_925hPa": [10.0] * n, "wind_direction_925hPa": [270.0] * n,   # from the west -> u=+10
        "wind_speed_10m": [2.0] * n, "wind_direction_10m": [180.0] * n,           # from the south -> v=+2
        "boundary_layer_height": [500.0, None, 300.0][:n], "precipitation": [0.0] * n,
    }}


def test_to_uv_meteorological_convention():
    u, v = om.to_uv(10, 270)
    assert math.isclose(u, 10, abs_tol=1e-6) and math.isclose(v, 0, abs_tol=1e-6)
    u, v = om.to_uv(5, 0)   # northerly wind blows southward
    assert math.isclose(u, 0, abs_tol=1e-6) and math.isclose(v, -5, abs_tol=1e-6)
    assert om.to_uv(None, 90) == (None, None)


def test_pack_wind_shapes_and_time_suffix():
    pts = [_point(la, lo) for la, lo in om.grid_points()]
    w = om.pack_wind(pts)
    assert len(w["times"]) == 3 and w["times"][0] == "2026-09-26T00:00:00Z"
    assert len(w["u925"]) == 3 and len(w["u925"][0]) == domain.WIND_NLAT and len(w["u925"][0][0]) == domain.WIND_NLON
    assert w["u925"][0][0][0] == 10.0 and w["v10"][0][5][5] == 2.0
    assert w["blh"][1][0][0] is None and w["blhAvailable"] is True


def test_pack_rejects_wrong_point_count():
    import pytest

    with pytest.raises(ValueError):
        om.pack_wind([_point(27, 73)])

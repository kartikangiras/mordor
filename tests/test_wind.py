from datetime import datetime, timezone

import numpy as np
import pytest

from common import domain
from forecast.wind import WindField, bilinear, blh_fallback
from tests.conftest import wind_json


def test_bilinear_reproduces_a_linear_field_exactly():
    lats = np.array([27.0, 28.0, 29.0])
    lons = np.array([73.0, 74.0])
    field = np.array([[la * 10 + lo for lo in lons] for la in lats])
    out = bilinear(field, lats, lons, [27.5, 28.25], [73.5, 73.9])
    assert np.allclose(out, [27.5 * 10 + 73.5, 28.25 * 10 + 73.9])


def test_bilinear_clamps_outside_grid():
    lats = np.array([27.0, 28.0])
    lons = np.array([73.0, 74.0])
    field = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert bilinear(field, lats, lons, [0.0], [0.0])[0] == 1.0
    assert bilinear(field, lats, lons, [99.0], [99.0])[0] == pytest.approx(4.0)


def test_windfield_blends_925_and_10m_and_interpolates_in_time():
    w = WindField(wind_json(u=0.0, u925=10.0))
    u, v = w.sample_uv([28.6], [77.2], datetime(2026, 9, 25, 3, 30, tzinfo=timezone.utc))
    assert u[0] == pytest.approx(0.7 * 10.0) and v[0] == pytest.approx(0.0)


def test_blh_grid_shape_and_fallback():
    w = WindField(wind_json(blh=750.0))
    g = w.blh_grid(datetime(2026, 9, 25, 6, tzinfo=timezone.utc))
    assert g.shape == (domain.NLAT, domain.NLON) and np.allclose(g, 750.0)
    # 06:00 IST -> 200 m ; 12:00 IST -> 1800 m
    assert blh_fallback(datetime(2026, 9, 25, 0, 30, tzinfo=timezone.utc)) == pytest.approx(200.0)
    assert blh_fallback(datetime(2026, 9, 25, 6, 30, tzinfo=timezone.utc)) == pytest.approx(1800.0)
    wj = wind_json()
    wj["blh"] = [[[None] * domain.WIND_NLON for _ in range(domain.WIND_NLAT)] for _ in wj["times"]]
    w2 = WindField(wj)
    assert not w2.blh_available
    assert np.allclose(w2.blh_grid(datetime(2026, 9, 25, 0, 30, tzinfo=timezone.utc)), 200.0)

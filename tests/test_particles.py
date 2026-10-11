from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from common import domain
from forecast import grid, particles
from forecast.run import Params, run_forecast
from forecast.wind import WindField
from tests.conftest import wind_json

T0 = datetime(2026, 9, 26, 6, tzinfo=timezone.utc)


def _fire(lat=30.5, lon=75.5, frp=12.0, hours_ago=2.0):
    return {"lat": lat, "lon": lon, "frp": frp, "acqUtc": (T0 - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_emit_particle_count_mass_and_release_spread():
    p, st = particles.emit([_fire(), _fire(lat=31.0)], T0 - timedelta(hours=24))
    assert len(p) == 120 and st["perFire"] == 60 and not st["thinned"]
    assert p.mass.sum() == pytest.approx(24.0)
    rel = p.t_release[:60]
    assert rel.min() >= 22 * 3600 and rel.max() <= 25 * 3600 and np.all(np.diff(rel) > 0)


def test_emit_thins_to_cap_and_logs():
    fires = [_fire(lat=30 + i * 0.01) for i in range(100)]
    p, st = particles.emit(fires, T0, max_particles=1000)
    assert st["thinned"] and len(p) <= 1000 and st["perFire"] == 10


def test_step_moves_east_in_a_westerly_with_no_diffusion():
    w = WindField(wind_json(u=5.0, v=0.0))
    p, _ = particles.emit([_fire(hours_ago=24)], T0 - timedelta(hours=24))
    lat0, lon0 = p.lat.copy(), p.lon.copy()
    rng = np.random.default_rng(0)
    particles.step(p, w, T0, 24 * 3600, 1800.0, rng, k_h=0.0, tau_h=1e9)
    expected_dlon = 5.0 * 1800 / (domain.M_PER_DEG_LAT * np.cos(np.radians(30.5)))
    assert np.allclose(p.lon - lon0, expected_dlon) and np.allclose(p.lat, lat0)
    assert p.mass.sum() == pytest.approx(12.0)


def test_step_kills_particles_that_leave_the_domain():
    w = WindField(wind_json(u=-50.0, v=0.0))  # strong easterly -> flies out of the west edge
    p, _ = particles.emit([_fire(lon=73.01, hours_ago=24)], T0 - timedelta(hours=24))
    rng = np.random.default_rng(0)
    n = particles.step(p, w, T0, 24 * 3600, 1800.0, rng, k_h=0.0)
    assert n == 0 and not p.alive.any()


def test_bin_mass_and_raw_surface():
    g = grid.bin_mass([28.61, 28.61, 10.0], [77.21, 77.21, 10.0], [1.0, 2.0, 5.0])
    i_lat, i_lon = domain.cell_index(28.61, 77.21)
    assert g.sum() == 3.0 and g[i_lat, i_lon] == 3.0
    raw = grid.raw_surface(g, np.full(g.shape, 50.0))  # below the 100 m floor
    assert raw[i_lat, i_lon] == pytest.approx(3.0 / (domain.cell_area_m2(domain.grid_lats()[i_lat]) * 100.0))


def test_run_forecast_is_deterministic_and_moves_smoke_downwind():
    w = WindField(wind_json(u=5.0, v=0.0, blh=500.0))
    fires = [_fire(lat=30.0, lon=75.0, frp=10.0, hours_ago=3.0)]
    a = run_forecast(T0, fires, w, Params(seed=7, spinup_h=6), hours=2)
    b = run_forecast(T0, fires, w, Params(seed=7, spinup_h=6), hours=2)
    assert a.raw.shape == (3, domain.NLAT, domain.NLON) and np.array_equal(a.raw, b.raw)
    assert a.run_id == "20260926T0600Z" and len(a.hours) == 3
    # centre of mass at hour 2 is east of the fire and has not moved north/south much
    m = a.raw[2]
    i_lat, i_lon = np.unravel_index(np.argmax(m), m.shape)
    assert domain.grid_lons()[i_lon] > 75.0 and abs(domain.grid_lats()[i_lat] - 30.0) < 0.3
    assert a.stats["particles"] == 60 and a.stats["liveAtEnd"] > 0

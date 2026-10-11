import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from common import domain


@pytest.fixture(scope="session")
def hindcast():
    """`tools/` is not a package, so load hindcast.py by path to test its pure functions."""
    spec = importlib.util.spec_from_file_location(
        "_hindcast_mod", Path(__file__).resolve().parents[1] / "tools" / "hindcast.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wind_json(u=5.0, v=0.0, blh=1000.0, hours=80, t0=datetime(2026, 9, 25, 0, tzinfo=timezone.utc), u925=None, v925=None):
    """Uniform synthetic wind field in the packed ingest_weather layout."""
    times = [(t0 + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ") for h in range(hours)]
    layer = lambda val: [[val] * domain.WIND_NLON for _ in range(domain.WIND_NLAT)]  # noqa: E731
    return {
        "lats": domain.wind_lats().tolist(), "lons": domain.wind_lons().tolist(), "times": times,
        "u925": [layer(u if u925 is None else u925) for _ in times], "v925": [layer(v if v925 is None else v925) for _ in times],
        "u10": [layer(u) for _ in times], "v10": [layer(v) for _ in times],
        "blh": [layer(blh) for _ in times], "source": "synthetic",
    }


@pytest.fixture
def uniform_wind():
    return wind_json()

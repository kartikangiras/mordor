import pytest

from common import aqi


@pytest.mark.parametrize("c,expected", [(0, 0), (30, 50), (45, 76), (60, 100), (90, 200), (120, 300),
                                        (250, 400), (380, 500), (600, 500)])
def test_pm25_subindex_breakpoints(c, expected):
    assert aqi.pm25_subindex(c) == expected


def test_subindex_is_monotonic():
    vals = [aqi.pm25_subindex(c) for c in range(0, 400)]
    assert vals == sorted(vals)


@pytest.mark.parametrize("a,tier", [(150, "T0"), (200, "T0"), (201, "T1"), (300, "T1"), (301, "T2"),
                                    (400, "T2"), (401, "T3"), (450, "T3"), (451, "T4"), (500, "T4")])
def test_tiers(a, tier):
    assert aqi.tier_for_aqi(a).id == tier


def test_tier_for_pm25():
    assert aqi.tier_for_pm25(50).id == "T0"
    assert aqi.tier_for_pm25(130).id == "T2"
    assert aqi.tier_for_pm25(300).id == "T3"

import numpy as np

from common import domain as d


def test_grid_dimensions_match_design():
    assert (d.NLON, d.NLAT) == (120, 110)
    assert (d.WIND_NLON, d.WIND_NLAT) == (13, 12)
    assert d.grid_lats().shape == (110,)
    assert d.grid_lons().shape == (120,)
    assert np.isclose(d.grid_lats()[0], 27.025) and np.isclose(d.grid_lats()[-1], 32.475)
    assert np.isclose(d.wind_lons()[-1], 79.0) and np.isclose(d.wind_lats()[-1], 32.5)


def test_image_corners_order_is_maplibre_clockwise_from_top_left():
    tl, tr, br, bl = d.IMAGE_CORNERS
    assert tl == [73.0, 32.5] and tr == [79.0, 32.5] and br == [79.0, 27.0] and bl == [73.0, 27.0]


def test_in_domain_and_cell_index():
    lat = np.array([28.61, 26.99, 32.5, 27.0])
    lon = np.array([77.21, 75.0, 75.0, 73.0])
    m = d.in_domain(lat, lon)
    assert m.tolist() == [True, False, False, True]
    i_lat, i_lon = d.cell_index(lat[m], lon[m])
    assert i_lat.tolist() == [32, 0] and i_lon.tolist() == [84, 0]


def test_cell_area_is_smaller_at_higher_latitude():
    a = d.cell_area_grid()
    assert a.shape == (d.NLAT, d.NLON)
    assert a[0, 0] > a[-1, 0]
    assert 2.4e7 < a[0, 0] < 3.0e7  # ~5.5 km x ~4.9 km

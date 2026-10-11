import io

import numpy as np
from PIL import Image

from common import domain
from render import ramp


def test_png_size_and_transparency_outside_plume():
    field = np.zeros((domain.NLAT, domain.NLON), dtype=np.float32)
    png = ramp.render_png(field, "relative", vmax=1.0)
    img = Image.open(io.BytesIO(png))
    assert img.size == (domain.NLON * ramp.UPSCALE, domain.NLAT * ramp.UPSCALE) and img.mode == "RGBA"
    assert np.asarray(img)[..., 3].max() == 0


def test_cpcb_ramp_bands():
    conc = np.array([[10.0, 45.0, 100.0, 300.0]])
    rgba = ramp.cpcb_rgba(conc)
    assert rgba[0, 0].tolist() == [0, 0, 0, 0]
    assert tuple(rgba[0, 1, :3]) == ramp.hex_to_rgb("#9ED6A0")
    assert tuple(rgba[0, 2, :3]) == ramp.hex_to_rgb("#F0A35E")
    assert tuple(rgba[0, 3, :3]) == ramp.hex_to_rgb("#7C2B3F")


def test_registration_delhi_lands_on_delhi():
    """Mass in the cell containing Delhi must render at the pixel whose lat/lon is Delhi, after
    the Mercator row resampling and the north-up flip (R5)."""
    lat, lon = 28.6139, 77.2090
    field = np.zeros((domain.NLAT, domain.NLON), dtype=np.float32)
    i_lat, i_lon = domain.cell_index(lat, lon)
    field[i_lat, i_lon] = 100.0
    up = ramp.upscale_to_mercator(field)
    r, c = np.unravel_index(np.argmax(up), up.shape)
    px_lat = ramp.output_pixel_lats(up.shape[0])[r]
    px_lon = domain.LON_MIN + (c + 0.5) / up.shape[1] * (domain.LON_MAX - domain.LON_MIN)
    assert abs(px_lat - lat) < domain.DLAT and abs(px_lon - lon) < domain.DLON
    assert r > up.shape[0] / 2  # Delhi (28.6N) is south of the domain midline -> lower rows, north-up


def test_mercator_rows_span_fewer_degrees_toward_the_north():
    """Equal Mercator-y steps cover fewer degrees of latitude the further north you go."""
    lats = ramp.output_pixel_lats(440)
    assert lats[0] > lats[-1]  # north-up
    north_step, south_step = abs(lats[1] - lats[0]), abs(lats[-1] - lats[-2])
    assert north_step < south_step
    assert abs(lats[220] - (domain.LAT_MIN + domain.LAT_MAX) / 2) < 0.05  # Mercator midline ~ 29.76N

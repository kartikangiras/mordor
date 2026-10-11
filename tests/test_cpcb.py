from datetime import datetime, timezone

from ingest_cpcb import cpcb


def _row(station, pollutant, value, lat="28.6", lon="77.2", city="Delhi", state="Delhi",
         last="26-09-2026 11:00:00", key="avg_value"):
    return {"station": station, "city": city, "state": state, "latitude": lat, "longitude": lon,
            "pollutant_id": pollutant, key: value, "last_update": last}


def test_pivot_handles_na_blank_coords_and_both_value_field_names():
    rows = [
        _row("Anand Vihar", "PM2.5", "180"), _row("Anand Vihar", "PM10", "300"), _row("Anand Vihar", "NO2", "40"),
        _row("Broken", "PM2.5", "NA"),
        _row("NoCoords", "PM2.5", "90", lat="", lon=""),
        _row("Legacy", "PM2.5", "77", key="pollutant_avg"),
        _row("Mumbai", "PM2.5", "50", lat="19.0", lon="72.8", city="Mumbai", state="Maharashtra"),
    ]
    out = cpcb.pivot(rows)
    names = [s["name"] for s in out]
    assert "Broken" not in names and "NoCoords" not in names and "Mumbai" not in names
    av = next(s for s in out if s["name"] == "Anand Vihar")
    assert av["pm25"] == 180 and av["pm10"] == 300
    assert av["observedAt"] == "2026-09-26T05:30:00Z"  # 11:00 IST
    assert next(s for s in out if s["name"] == "Legacy")["pm25"] == 77


def test_station_id_is_stable_and_readable():
    a = cpcb.station_id("Delhi", "Delhi", "Anand Vihar, Delhi - DPCC")
    assert a == cpcb.station_id("Delhi", "Delhi", "Anand Vihar, Delhi - DPCC")
    assert a.startswith("delhi-anand-vihar-delhi-dpcc-")


def test_ddb_items_floor_to_hour():
    out = cpcb.pivot([_row("X", "PM2.5", "10", last="26-09-2026 11:45:00")])
    items = cpcb.to_ddb_items(out, datetime(2026, 9, 26, tzinfo=timezone.utc))
    obs = [i for i in items if i["SK"].startswith("OBS#")][0]
    assert obs["SK"] == "OBS#2026-09-26T06:00:00Z"
    assert any(i["SK"] == "META" for i in items)

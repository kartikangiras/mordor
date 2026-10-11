from datetime import datetime, timezone

from ingest_firms import firms

HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
ROWS = (
    "30.82652,74.12354,367,0.45,0.63,2026-09-25,0726,N20,high,2.0NRT,296.44,14.98,D\n"      # keep
    "31.47302,75.06176,330.12,0.62,0.71,2026-09-25,905,N20,nominal,2.0NRT,292.06,3.97,D\n"  # 3-char time, keep
    "31.0,75.0,330,0.6,0.7,2026-09-25,0905,N20,low,2.0NRT,292,3.0,D\n"                      # low -> drop
    "31.0,75.0,330,0.6,0.7,2026-09-25,0905,N20,l,2.0NRT,292,3.0,D\n"                        # area-API 'l' -> drop
    "31.2,75.2,330,0.6,0.7,2026-09-25,0905,N20,n,2.0NRT,292,,D\n"                           # 'n', missing frp -> keep, fill
    "20.0,100.0,330,0.6,0.7,2026-09-25,0905,N20,high,2.0NRT,292,9.0,D\n"                    # outside domain -> drop
    "28.5,77.0,330,0.6,0.7,2026-09-25,0905,N20,high,2.0NRT,292,0,D\n"                       # frp 0 -> fill
)


def test_parse_normalises_confidence_time_domain_and_frp():
    fires = firms.parse_fires(HEADER + ROWS, "VIIRS_NOAA20_NRT")
    assert len(fires) == 4
    assert [f["confidence"] for f in fires] == ["high", "nominal", "nominal", "high"]
    assert fires[1]["acqUtc"] == "2026-09-25T09:05:00Z"
    assert fires[2]["frp"] is None and fires[3]["frp"] is None
    n = firms.fill_missing_frp(fires)
    assert n == 2
    assert fires[2]["frp"] == fires[3]["frp"] == (14.98 + 3.97) / 2  # median of the known two


def test_modis_integer_confidence():
    assert firms.normalise_confidence("53") == "nominal"
    assert firms.normalise_confidence(85) == "high"
    assert firms.normalise_confidence("12") == "low"
    assert firms.normalise_confidence("??") == "nominal"


def test_dedupe_and_geojson_and_ddb_keys():
    fires = firms.parse_fires(HEADER + ROWS, "VIIRS_NOAA20_NRT")
    fires = firms.dedupe(fires + fires)
    assert len(fires) == 4
    firms.fill_missing_frp(fires)
    gj = firms.to_geojson(fires)
    assert gj["features"][0]["geometry"]["coordinates"] == [74.12354, 30.82652]
    items = firms.to_ddb_items(fires, datetime(2026, 9, 26, tzinfo=timezone.utc))
    assert items[0]["PK"] == "FIRE#2026-09-25"
    assert items[0]["SK"] == "2026-09-25T07:26:00Z#30.82652#74.12354"
    assert items[0]["ttl"] > 0


def test_load_recent_from_local_storage(tmp_path, monkeypatch):
    from common import storage as st

    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TABLE_NAME", raising=False)
    st.reset()
    now = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)
    st.storage().put_text(firms.raw_key("VIIRS_NOAA20_NRT", now), HEADER + ROWS, "text/csv")
    recent = firms.load_recent(hours=24, now=now)
    assert len(recent) == 4 and all(f["frp"] for f in recent)
    assert firms.load_recent(hours=1, now=now) == []
    st.reset()


def test_cross_satellite_dedupe_keeps_max_frp_within_1km_90min():
    a = {"lat": 30.5000, "lon": 75.5000, "frp": 5.0, "acqUtc": "2026-09-25T08:00:00Z", "satellite": "N", "source": "s", "confidence": "n", "brightness": 1}
    b = {**a, "lat": 30.5050, "frp": 9.0, "acqUtc": "2026-09-25T08:50:00Z", "satellite": "N20"}   # ~0.55 km, 50 min -> same fire
    c = {**a, "lat": 30.5200, "frp": 3.0, "acqUtc": "2026-09-25T08:10:00Z"}                        # ~2.2 km -> different
    d = {**a, "acqUtc": "2026-09-25T20:00:00Z", "frp": 4.0}                                        # same place, 12 h later -> different
    out = firms.dedupe_cross_satellite([a, b, c, d])
    assert len(out) == 3
    merged = [f for f in out if f.get("nSat") == 2][0]
    assert merged["frp"] == 9.0 and merged["satellite"] == "N20"

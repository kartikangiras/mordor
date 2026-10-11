from datetime import datetime, timedelta, timezone

from ingest_cpcb import cpcb, openaq_live

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def _loc(lid, lat=28.6, lon=77.2, provider="AirGradient", name="Somewhere",
         last=None, sensors=((91, 2), (92, 1))):
    return {
        "id": lid, "name": name, "locality": "Delhi",
        "country": {"code": "IN"},
        "provider": {"name": provider},
        "coordinates": {"latitude": lat, "longitude": lon},
        "datetimeLast": {"utc": (last or NOW - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "sensors": [{"id": sid, "parameter": {"id": pid}} for sid, pid in sensors],
    }


def _reading(sensor_id, value, when=None):
    return {"sensorsId": sensor_id, "value": value,
            "datetime": {"utc": (when or NOW - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")}}


def test_tier_splits_reference_monitors_from_sensor_networks():
    assert openaq_live.tier_for("CPCB", "DTU, New Delhi - CPCB") == "reference"
    assert openaq_live.tier_for("AirGradient", "R K Puram, New Delhi - DPCC") == "reference"
    assert openaq_live.tier_for("AirGradient", "GK1 (Oberoi Terrace)") == "low_cost"
    assert openaq_live.tier_for("Hawanama", "Model Town") == "low_cost"
    assert openaq_live.tier_for(None, None) == "low_cost"


def test_fresh_locations_drops_out_of_domain_and_sorts_freshest_first():
    outside = _loc(2, lat=19.0, lon=72.8)                     # Mumbai
    nocoords = {**_loc(3), "coordinates": {}}
    recent = _loc(4, last=NOW - timedelta(minutes=10))
    older = _loc(5, last=NOW - timedelta(hours=2))
    out = openaq_live.fresh_locations([outside, nocoords, older, recent], NOW, max_age_hours=3)
    assert [loc["id"] for loc in out] == [4, 5]


def test_window_is_wide_enough_for_the_cpcb_lag_but_still_has_an_edge():
    """The reference network lands ~108 h late and must be published (marked stale by the
    API); something genuinely abandoned must still be dropped."""
    cpcb = _loc(1, provider="CPCB", name="ITO, New Delhi - CPCB", last=NOW - timedelta(hours=108))
    ancient = _loc(6, last=NOW - timedelta(days=400))
    out = openaq_live.fresh_locations([cpcb, ancient], NOW)
    assert [loc["id"] for loc in out] == [1]
    assert openaq_live.FRESH_HOURS >= 108


def test_fresh_locations_respects_the_cap():
    locs = [_loc(i, last=NOW - timedelta(minutes=i)) for i in range(1, 20)]
    assert len(openaq_live.fresh_locations(locs, NOW, limit=5)) == 5


def test_station_from_pairs_pm25_and_pm10_by_sensor_id():
    loc = _loc(7, provider="Hawanama", name="Model Town")
    st = openaq_live.station_from(loc, [_reading(91, 180.0), _reading(92, 300.0)])
    assert st["id"] == "oaq-7" and st["openaqId"] == 7
    assert st["pm25"] == 180.0 and st["pm10"] == 300.0
    assert st["tier"] == "low_cost" and st["provider"] == "Hawanama"
    assert st["source"] == "openaq-v3" and st["observedAt"] == "2026-10-07T11:30:00Z"


def test_station_from_needs_pm25_and_ignores_unknown_sensors_and_bad_values():
    loc = _loc(8)
    assert openaq_live.station_from(loc, [_reading(92, 300.0)]) is None       # pm10 only
    assert openaq_live.station_from(loc, [_reading(999, 50.0)]) is None       # not our sensor
    assert openaq_live.station_from(loc, [_reading(91, -5.0)]) is None        # negative
    assert openaq_live.station_from(loc, [_reading(91, 99999.0)]) is None     # absurd


def test_openaq_stations_feed_the_same_ddb_shape_as_data_gov():
    loc = _loc(9, provider="AirGradient", name="GK1 (Oberoi Terrace)")
    st = openaq_live.station_from(loc, [_reading(91, 55.0)])
    items = cpcb.to_ddb_items([st], NOW)
    obs = [i for i in items if i["SK"].startswith("OBS#")][0]
    assert obs["SK"] == "OBS#2026-10-07T11:00:00Z"      # floored to the hour
    assert obs["PK"].endswith("oaq-9") and obs["pm25"] == 55.0
    assert any(i["SK"] == "META" for i in items)


def test_rate_limiter_paces_calls():
    limiter = openaq_live._RateLimiter(per_minute=6000)   # 10 ms apart
    import time

    start = time.monotonic()
    for _ in range(5):
        limiter.wait()
    assert time.monotonic() - start >= 0.03


def test_run_merges_both_sources_and_prefers_reference_on_a_tie(monkeypatch, tmp_path):
    oaq = openaq_live.station_from(_loc(11, name="Sensor near ITO"), [_reading(91, 120.0)])
    ref = {"id": "oaq-11", "name": "ITO, New Delhi - CPCB", "city": "Delhi", "state": "Delhi",
           "lat": 28.6, "lon": 77.2, "pm25": 210.0, "pm10": None,
           "observedAt": "2026-10-07T11:00:00Z", "provider": "CPCB", "tier": "reference",
           "source": "data.gov.in"}
    monkeypatch.setattr(cpcb, "_from_openaq", lambda k, now: ([oaq], {"ok": True}))
    monkeypatch.setattr(cpcb, "_from_data_gov", lambda k, now: ([ref], {"ok": True}))
    out = cpcb.run(now=NOW, api_key="dg", openaq_key="oa")
    assert out["stations"] == 1
    assert out["byTier"] == {"reference": 1}


def test_run_survives_data_gov_being_unreachable(monkeypatch):
    import requests

    def dead(api_key):
        raise requests.ConnectionError("[Errno 111] Connection refused")

    oaq = openaq_live.station_from(_loc(12), [_reading(91, 44.0)])
    monkeypatch.setattr(cpcb, "fetch_rows", dead)
    monkeypatch.setattr(cpcb, "_from_openaq", lambda k, now: ([oaq], {"ok": True}))
    out = cpcb.run(now=NOW, api_key="dg", openaq_key="oa")
    assert out["stations"] == 1
    assert out["sources"]["dataGovIn"]["ok"] is False
    assert "Connection refused" in out["sources"]["dataGovIn"]["error"]


def test_run_skips_cleanly_with_no_keys():
    out = cpcb.run(now=NOW, api_key=None, openaq_key=None)
    assert out["skipped"] == "no station api key"


def test_errors_never_publish_the_api_key():
    url = ("HTTPSConnectionPool(host='api.data.gov.in', port=443): Max retries exceeded with "
           "url: /resource/a3e7afc6?api-key=TESTKEY-not-a-real-key-redact-me-0000-0000-0000-0000"
           "&format=json&limit=1000 (Caused by NewConnectionError)")
    out = cpcb.redact(url)
    assert "redact-me" not in out
    assert "api-key=***" in out
    assert "format=json" in out            # only the secret is masked
    assert cpcb.redact("X-API-Key header, key=abc123&z=1") == "X-API-Key header, key=***&z=1"


def test_run_redacts_the_key_in_the_public_snapshot(monkeypatch):
    import requests

    def dead(api_key):
        raise requests.ConnectionError(
            "url: /resource/a3e7afc6?api-key=TESTKEY-not-a-real-key-redact-me-0000-0000-0000-0000")

    monkeypatch.setattr(cpcb, "fetch_rows", dead)
    monkeypatch.setattr(cpcb, "_from_openaq", lambda k, now: ([], {"ok": True}))
    out = cpcb.run(now=NOW, api_key="dg", openaq_key="oa")
    assert "redact-me" not in str(out)


class _Resp:
    def __init__(self, status=200, headers=None, body=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body if body is not None else {"results": []}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Client Error")


class _Session:
    """Answers 429 for the first `fail` calls, then 200."""

    def __init__(self, fail=0, headers=None):
        self.fail = fail
        self.calls = 0
        self.headers = headers or {}

    def get(self, url, **kw):
        self.calls += 1
        if self.calls <= self.fail:
            return _Resp(429, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "0",
                               "retry-after": "0"})
        return _Resp(200, self.headers, {"results": [_reading(91, 61.0)]})


def test_fetch_latest_retries_through_a_429_instead_of_losing_the_station():
    sess = _Session(fail=2)
    limiter = openaq_live._RateLimiter(per_minute=60000)
    rows = openaq_live.fetch_latest("k", 1, sess, limiter)
    assert sess.calls == 3                      # two 429s then a success
    assert rows and rows[0]["value"] == 61.0


def test_fetch_latest_gives_up_after_max_retries():
    import pytest

    sess = _Session(fail=99)
    limiter = openaq_live._RateLimiter(per_minute=60000)
    with pytest.raises((RuntimeError, Exception)):
        openaq_live.fetch_latest("k", 1, sess, limiter)
    assert sess.calls == openaq_live.MAX_RETRIES + 1


def test_limiter_parks_when_the_window_is_nearly_spent():
    limiter = openaq_live._RateLimiter(per_minute=60000)
    limiter.observe(_Resp(200, {"x-ratelimit-remaining": "1", "x-ratelimit-reset": "30"}))
    import time

    # _next is pushed ~30 s out, so the next wait() would block; check the deadline directly
    assert limiter._next - time.monotonic() > 25


def test_limiter_ignores_missing_or_junk_headers():
    limiter = openaq_live._RateLimiter(per_minute=60000)
    before = limiter._next
    limiter.observe(_Resp(200, {}))
    limiter.observe(_Resp(200, {"x-ratelimit-remaining": "nope", "x-ratelimit-reset": "x"}))
    assert limiter._next == before


def test_plenty_of_remaining_quota_does_not_park():
    limiter = openaq_live._RateLimiter(per_minute=60000)
    before = limiter._next
    limiter.observe(_Resp(200, {"x-ratelimit-remaining": "40", "x-ratelimit-reset": "30"}))
    assert limiter._next == before

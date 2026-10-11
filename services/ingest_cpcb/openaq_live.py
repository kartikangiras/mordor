"""Live station PM2.5 / PM10 from the OpenAQ v3 API (DESIGN.md §4.3).

Why this exists alongside `cpcb.py`: as of 2026-10-07 there is no working route to live
reference-grade CPCB readings.

  * `api.data.gov.in` (164.100.61.198) refuses TCP 80/443 from both a laptop on an Indian ISP
    and a us-east-1 Lambda (`[Errno 111] Connection refused`), while `www.data.gov.in` is up.
  * OpenAQ carries 140 CPCB stations inside the domain but its CPCB feed runs ~4.5 days behind
    (every one of them last reported 107 h ago when checked), the same lag as the keyless
    `openaq-data-archive` bucket.

What does report hourly here is the sensor networks: AirGradient (96 stations, 63 inside 2 h),
Hawanama (90, 40 inside 2 h) and Clarity. Those are low-cost sensors, not reference monitors,
so every station in the snapshot carries a `tier` — `reference` for a CPCB / DPCC / IMD-class
monitor, `low_cost` for a sensor network — and consumers must label the two differently. The
hindcast and calibration keep using reference-grade hourly history from the archive, where the
~4-day lag does not matter; only the live overlay uses this.

OpenAQ v3 has no spatial filter on `/v3/parameters/{id}/latest` (`bbox` and
`coordinates`+`radius` are both ignored — it returns the same global `found`), so the shape
here is: one bbox call for the station list, then one `/v3/locations/{id}/latest` per station
that is actually fresh, paced by a header-aware rate limiter (see `_RateLimiter`).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

from common import domain
from common.timeutil import utc_now

log = logging.getLogger(__name__)

BASE = "https://api.openaq.org/v3"
PARAM_PM25 = 2
PARAM_PM10 = 1
TIMEOUT = 30
LIST_LIMIT = 1000

#: Only stations in these countries are published. The domain bbox reaches well into Pakistani
#: Punjab (181 of the 382 PM2.5 stations in it were Pakistani), and the product serves Punjab,
#: Haryana, Delhi, Rajasthan and Uttar Pradesh, so observations are filtered to India by the
#: country code OpenAQ reports. Fire detections are deliberately NOT filtered this way: smoke
#: from across the border reaches Delhi and must stay in the model.
FOCUS_COUNTRIES = {"IN"}

#: How far back a station may have reported and still be published. Indian coverage inside the
#: domain is a cliff, not a gradient (measured 2026-10-07): 7 stations within 3 h — the same 7
#: at 48 h, all AirGradient/Clarity sensors in the NCR — and then the entire CPCB / DPCC / IMD
#: reference network appears at once at ~108 h, because that is OpenAQ's CPCB lag. 3 h would
#: therefore publish a 7-dot map of Delhi only. 5 days includes the reference network across
#: all five states; the API marks anything over STALE_AFTER (3 h) `isStale`, and the map draws
#: those hollow and the popup says so, so nothing stale is presented as current.
FRESH_HOURS = 120.0
#: Bound the per-run work so the Lambda cannot run away: at 45 req/min, 200 is ~4.5 min.
MAX_STATIONS = 200
#: `x-ratelimit-limit: 60` is a FIXED window that resets every ~60 s (`x-ratelimit-reset`
#: counts down), and `x-ratelimit-used` is shared across every caller of the key. Pacing at
#: 55/min sat exactly on that ceiling and lost 50 of 110 calls to 429s as soon as the window
#: had been partly spent elsewhere, so: leave real headroom, watch the headers, and retry.
REQUESTS_PER_MINUTE = 45
#: Park until the window resets once the server says this few requests are left.
RESERVE = 6
MAX_RETRIES = 2
WORKERS = 4

#: Providers whose data is reference-grade (regulatory monitors). Everything else is a
#: low-cost sensor network and is labelled as such.
REFERENCE_PROVIDERS = {"cpcb", "caaqm", "airnow", "stateair newdelhi", "stateair lahore"}
#: Station names from the regulatory networks carry these suffixes even via other providers.
REFERENCE_NAME_MARKERS = ("- cpcb", "- dpcc", "- imd", "- hspcb", "- uppcb", "- ppcb", "- rspcb")


class _RateLimiter:
    """Paces a thread pool, and defers to the server's own rate-limit headers.

    Open-loop pacing is not enough on a fixed window shared across callers, so `observe`
    pushes every worker past the window boundary as soon as the server says it is nearly
    spent. That turns a burst of 429s into one quiet pause.
    """

    def __init__(self, per_minute: int):
        self._interval = 60.0 / max(1, per_minute)
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            due = max(now, self._next)
            self._next = due + self._interval
        delay = due - now
        if delay > 0:
            time.sleep(delay)

    def park(self, seconds: float) -> None:
        """Hold every worker until `seconds` from now."""
        with self._lock:
            self._next = max(self._next, time.monotonic() + max(0.0, seconds))

    def observe(self, resp: requests.Response) -> None:
        remaining, reset = _limit_headers(resp)
        if remaining is not None and reset is not None and remaining <= RESERVE:
            log.info("openaq window nearly spent (%s left), parking %.0fs", remaining, reset)
            self.park(reset + 0.5)


def _limit_headers(resp: requests.Response) -> tuple[int | None, float | None]:
    def num(name, cast):
        try:
            return cast(resp.headers.get(name, ""))
        except (TypeError, ValueError):
            return None

    return num("x-ratelimit-remaining", int), num("x-ratelimit-reset", float)


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Accept": "application/json"}


def tier_for(provider: str | None, name: str | None) -> str:
    """'reference' for a regulatory monitor, 'low_cost' for a sensor network."""
    if (provider or "").strip().lower() in REFERENCE_PROVIDERS:
        return "reference"
    low = (name or "").lower()
    return "reference" if any(m in low for m in REFERENCE_NAME_MARKERS) else "low_cost"


def fetch_locations(api_key: str, session: requests.Session | None = None) -> list[dict]:
    """Every PM2.5 station in the domain bbox, with its sensors and last-reported time."""
    sess = session or requests.Session()
    w, s, e, n = domain.DOMAIN_WSEN
    resp = sess.get(f"{BASE}/locations", headers=_headers(api_key), timeout=TIMEOUT,
                    params={"bbox": f"{w},{s},{e},{n}", "parameters_id": PARAM_PM25,
                            "limit": LIST_LIMIT})
    resp.raise_for_status()
    body = resp.json()
    if "results" not in body:
        raise RuntimeError(f"openaq unexpected response: {str(body)[:200]}")
    return body["results"]


def _last_utc(loc: dict) -> datetime | None:
    raw = ((loc.get("datetimeLast") or {}) or {}).get("utc")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def country_of(loc: dict) -> str:
    return (((loc.get("country") or {}) or {}).get("code") or "").upper()


def fresh_locations(locations: list[dict], now: datetime | None = None,
                    max_age_hours: float = FRESH_HOURS, limit: int = MAX_STATIONS) -> list[dict]:
    """In-focus locations that reported inside `max_age_hours`, freshest first, capped."""
    now = now or utc_now()
    cutoff = now - timedelta(hours=max_age_hours)
    fresh = []
    for loc in locations:
        last = _last_utc(loc)
        coords = loc.get("coordinates") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        if last is None or last < cutoff or lat is None or lon is None:
            continue
        if country_of(loc) not in FOCUS_COUNTRIES:
            continue
        if not bool(domain.in_domain(lat, lon)):
            continue
        fresh.append(loc)
    fresh.sort(key=lambda loc: _last_utc(loc) or datetime.min, reverse=True)
    return fresh[:limit]


def _sensor_params(loc: dict) -> dict[int, int]:
    """sensorsId -> parameter id, for the PM sensors on this location."""
    out: dict[int, int] = {}
    for sensor in loc.get("sensors") or []:
        pid = ((sensor.get("parameter") or {}) or {}).get("id")
        sid = sensor.get("id")
        if pid in (PARAM_PM25, PARAM_PM10) and sid is not None:
            out[int(sid)] = int(pid)
    return out


def fetch_latest(api_key: str, location_id: int, session: requests.Session | None = None,
                 limiter: _RateLimiter | None = None) -> list[dict]:
    """Latest value per sensor at one location, retrying through a spent rate-limit window."""
    sess = session or requests.Session()
    for attempt in range(MAX_RETRIES + 1):
        if limiter is not None:
            limiter.wait()
        resp = sess.get(f"{BASE}/locations/{location_id}/latest", headers=_headers(api_key),
                        timeout=TIMEOUT)
        if limiter is not None:
            limiter.observe(resp)
        if resp.status_code == 429 and attempt < MAX_RETRIES:
            _, reset = _limit_headers(resp)
            delay = min(float(resp.headers.get("retry-after") or reset or 10.0) + 0.5, 65.0)
            if limiter is not None:
                limiter.park(delay)
            else:
                time.sleep(delay)
            continue
        resp.raise_for_status()
        return resp.json().get("results") or []
    raise RuntimeError(f"openaq rate limited after {MAX_RETRIES} retries")


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and 0 <= f <= 2000 else None


def station_from(loc: dict, latest: list[dict]) -> dict | None:
    """One snapshot station from a location and its latest readings, or None if no PM2.5."""
    wanted = _sensor_params(loc)
    pm25 = pm10 = None
    observed: str | None = None
    for row in latest:
        pid = wanted.get(int(row.get("sensorsId", -1)))
        if pid is None:
            continue
        value = _num(row.get("value"))
        if value is None:
            continue
        when = ((row.get("datetime") or {}) or {}).get("utc")
        if pid == PARAM_PM25:
            pm25, observed = value, when or observed
        elif pid == PARAM_PM10:
            pm10 = value
    if pm25 is None or not observed:
        return None
    coords = loc.get("coordinates") or {}
    provider = ((loc.get("provider") or {}) or {}).get("name")
    name = loc.get("name") or f"openaq-{loc.get('id')}"
    locality = loc.get("locality") or ""
    country = ((loc.get("country") or {}) or {}).get("code") or ""
    return {"id": f"oaq-{loc.get('id')}", "openaqId": loc.get("id"), "name": name,
            "city": locality, "state": "", "country": country, "lat": coords.get("latitude"),
            "lon": coords.get("longitude"), "pm25": pm25, "pm10": pm10,
            "observedAt": observed, "provider": provider,
            "tier": tier_for(provider, name), "source": "openaq-v3"}


def fetch_stations(api_key: str, now: datetime | None = None,
                   session: requests.Session | None = None) -> tuple[list[dict], dict]:
    """(stations, diagnostics). One bbox call plus one latest call per fresh station."""
    now = now or utc_now()
    sess = session or requests.Session()
    locations = fetch_locations(api_key, sess)
    fresh = fresh_locations(locations, now)
    limiter = _RateLimiter(REQUESTS_PER_MINUTE)

    def one(loc: dict) -> dict | None:
        try:
            return station_from(loc, fetch_latest(api_key, int(loc["id"]), sess, limiter))
        except Exception as exc:  # one dead station must not fail the run
            log.warning("openaq latest failed for %s: %s", loc.get("id"), exc)
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        stations = [s for s in pool.map(one, fresh) if s]
    stations.sort(key=lambda s: s["id"])
    tiers: dict[str, int] = {}
    providers: dict[str, int] = {}
    live = 0
    for s in stations:
        tiers[s["tier"]] = tiers.get(s["tier"], 0) + 1
        providers[s["provider"] or "?"] = providers.get(s["provider"] or "?", 0) + 1
        try:
            observed = datetime.fromisoformat(s["observedAt"].replace("Z", "+00:00"))
            if (now - observed) <= timedelta(hours=3):
                live += 1
        except (KeyError, ValueError):
            pass
    diag = {"inDomain": len(locations), "candidates": len(fresh), "stations": len(stations),
            "liveWithin3h": live, "tiers": tiers, "providers": providers,
            "freshHours": FRESH_HOURS, "focusCountries": sorted(FOCUS_COUNTRIES)}
    log.info("openaq live: %s", diag)
    return stations, diag

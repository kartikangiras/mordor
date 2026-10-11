#!/usr/bin/env python3
"""Hindcast and calibration (DESIGN.md §5.7, §13.1). Runs the model daily at 00 UTC with a 48 h
horizon over a window, pairs every (station, hour) prediction with an observation, fits the
single constant k on the first `fit_days`, evaluates on the rest, and writes

  validation/{experimentId}/report.json      everything the /validation page shows
  validation/latest/report.json
  validation/latest/calibration.json         k, r2, mae, bias, window, stations -> read by every run

Data, all keyless: fires from the FIRMS per-country VIIRS S-NPP archive (or the _SP area API
when FIRMS_MAP_KEY is set), ERA5 100 m winds + BLH and CAMS background via Open-Meteo archives,
observations from the OpenAQ open-data archive on S3 (data/openaq_stations.json index).

    PYTHONPATH=services python tools/hindcast.py --window 2024-11-01 2024-11-20 --fit-days 10
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import logging
import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

from common import aqi, domain
from common.storage import LocalStorage, storage
from common.timeutil import iso_z
from forecast.run import Params, run_forecast
from forecast.wind import WindField
from ingest_firms import firms
from ingest_weather import openmeteo

log = logging.getLogger("hindcast")
UTC = timezone.utc
OPENAQ = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid={id}/year={y}/month={m}/location-{id}-{ymd}.csv.gz"
FIRMS_COUNTRY = "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/{year}/viirs-snpp_{year}_{country}.csv"
COUNTRIES = ("India", "Pakistan")  # the domain straddles the border; Pakistani Punjab burns too
DELHI = (28.6139, 77.2090)


def _d(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)


# ------------------------------------------------------------------------------ stations
def load_stations(index_path: str, month: str, min_days: int, delhi_km: float) -> list[dict]:
    idx = json.loads(Path(index_path).read_text())
    out = []
    for s in idx["stations"]:
        if s.get("daysByMonth", {}).get(month, 0) < min_days:
            continue
        dkm = math.hypot((s["lat"] - DELHI[0]) * 111.32, (s["lon"] - DELHI[1]) * 111.32 * math.cos(math.radians(DELHI[0])))
        out.append({**s, "delhi": dkm <= delhi_km, "distanceToDelhiKm": round(dkm, 1)})
    return out


# ---------------------------------------------------------------------------- observations
def _obs_file(sess: requests.Session, cache: Path, sid: int, day: datetime) -> list[dict]:
    p = cache / f"openaq/{sid}/{day:%Y%m%d}.csv.gz"
    if not p.exists():
        r = sess.get(OPENAQ.format(id=sid, y=day.year, m=f"{day.month:02d}", ymd=day.strftime("%Y%m%d")), timeout=60)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content if r.status_code == 200 else b"")
    raw = p.read_bytes()
    if not raw:
        return []
    return list(csv.DictReader(io.StringIO(gzip.decompress(raw).decode())))


def load_obs(stations: list[dict], start: datetime, end: datetime, cache: Path) -> dict[tuple[int, str], float]:
    sess = requests.Session()
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    jobs = [(s["id"], d) for s in stations for d in days]
    acc: dict[tuple[int, str], list[float]] = defaultdict(list)
    with ThreadPoolExecutor(max_workers=16) as ex:
        for rows in ex.map(lambda j: _obs_file(sess, cache, *j), jobs):
            for r in rows:
                if r.get("parameter") != "pm25":
                    continue
                try:
                    v = float(r["value"])
                    t = datetime.fromisoformat(r["datetime"]).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
                except (ValueError, KeyError):
                    continue
                if 0 <= v <= 1000:
                    acc[(int(r["location_id"]), iso_z(t))].append(v)
    return {k: float(np.mean(v)) for k, v in acc.items()}


# ----------------------------------------------------------------------------------- fires
def load_fires(start: datetime, end: datetime, cache: Path, map_key: str | None) -> tuple[list[dict], str]:
    """Detections from start-1d to end+2d. Returns (fires, provenance)."""
    lo, hi = start - timedelta(days=1), end + timedelta(days=2)
    if map_key:
        fires = []
        day = lo
        while day <= hi:
            # The area API caps day_range at 1..5 (verified 2026-10-07; a 10 returns
            # HTTP 400 "Invalid day range. Expects [1..5]."), so step in 5-day blocks.
            span = min(5, (hi - day).days + 1)
            for src in ("VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"):
                url = firms.area_url(map_key, src, span, day.strftime("%Y-%m-%d"))
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                fires.extend(firms.parse_fires(resp.text, src))
            day += timedelta(days=span)
        prov = "FIRMS area API, VIIRS_SNPP_SP + VIIRS_NOAA20_SP"
    else:
        year = start.year
        fires = []
        for country in COUNTRIES:
            p = cache / f"firms_archive/viirs-snpp_{year}_{country}.csv"
            if not p.exists():
                log.info("downloading FIRMS %d %s archive", year, country)
                r = requests.get(FIRMS_COUNTRY.format(year=year, country=country), timeout=600, stream=True)
                r.raise_for_status()
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            fires.extend(firms.parse_fires(p.read_text(), "VIIRS_SNPP_ARCHIVE"))
        prov = f"FIRMS per-country archives viirs-snpp_{year}_{{India,Pakistan}}.csv (S-NPP only)"
    fires = [f for f in fires if iso_z(lo) <= f["acqUtc"] <= iso_z(hi)]
    fires = firms.dedupe(fires)
    firms.fill_missing_frp(fires)
    fires = firms.dedupe_cross_satellite(fires)
    fires.sort(key=lambda f: f["acqUtc"])
    return fires, prov


# ---------------------------------------------------------------------------- meteorology
def load_wind(start: datetime, end: datetime, cache: Path) -> WindField:
    p = cache / f"era5/{start:%Y%m%d}_{end:%Y%m%d}/wind.json"
    if not p.exists():
        log.info("fetching ERA5 winds %s..%s (4 calls)", start.date(), end.date())
        packed = openmeteo.pack_archive_wind(openmeteo.fetch_archive_wind(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(packed))
    return WindField(json.loads(p.read_text()))


def load_background(stations: list[dict], start: datetime, end: datetime, cache: Path) -> dict[tuple[int, str], float]:
    p = cache / f"cams/{start:%Y%m%d}_{end:%Y%m%d}/{'-'.join(str(s['id']) for s in stations)[:200]}.json"
    if not p.exists():
        pts = [(s["lat"], s["lon"]) for s in stations]
        data = openmeteo.fetch_archive_aq_points(pts, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
    data = json.loads(p.read_text())
    out: dict[tuple[int, str], float] = {}
    for s, d in zip(stations, data, strict=False):
        for t, v in zip(d["hourly"]["time"], d["hourly"]["pm2_5"], strict=False):
            if v is not None:
                out[(s["id"], t + ":00Z" if len(t) == 16 else t)] = float(v)
    return out


# --------------------------------------------------------------------------------- metrics
def metrics(pred: np.ndarray, obs: np.ndarray) -> dict:
    if len(obs) < 3:
        return {"n": int(len(obs)), "r2": None, "mae": None, "bias": None, "corr": None}
    ss_res = float(np.sum((obs - pred) ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    corr = float(np.corrcoef(pred, obs)[0, 1]) if pred.std() > 0 else 0.0
    return {"n": int(len(obs)), "r2": round(1 - ss_res / ss_tot, 3) if ss_tot > 0 else None,
            "mae": round(float(np.mean(np.abs(pred - obs))), 1), "bias": round(float(np.mean(pred - obs)), 1),
            "corr": round(corr, 3)}


def conformal(pred: np.ndarray, obs: np.ndarray, levels=(0.8, 0.9)) -> dict:
    """Split-conformal half-widths, in ug/m3, from held-out absolute residuals.

    Nothing clever: with the model fitted on the first `fit_days` and never refitted, the
    absolute residuals on the remaining days are exchangeable, so their (1-alpha) empirical
    quantile is a distribution-free prediction half-width with finite-sample coverage. The
    small (n+1)/n correction is the usual conformal adjustment. R2 says how much variance the
    model explains; this says how wrong a single number is likely to be, which is what a card
    has to admit (DESIGN.md 13.2a, R4)."""
    if len(obs) < 20:
        return {"n": int(len(obs)), "basis": "insufficient held-out rows"}
    resid = np.abs(np.asarray(obs, float) - np.asarray(pred, float))
    n = len(resid)
    out: dict = {"n": int(n), "basis": "split-conformal on held-out |residual|, ug/m3"}
    for lv in levels:
        q = min(1.0, (lv * (n + 1)) / n)          # conformal correction, capped
        out[f"q{int(round(lv * 100))}"] = round(float(np.quantile(resid, q)), 1)
    return out


def fit_k(rows: list[dict]) -> float:
    """DESIGN.md §5.7: least squares through the origin on (obs - background)."""
    raw = np.array([r["raw"] for r in rows])
    y = np.array([r["obs"] - r["bg"] for r in rows])
    den = float(np.sum(raw * raw))
    return float(np.sum(raw * y) / den) if den > 0 else 0.0


def fit_k_anomaly(rows: list[dict]) -> float:
    """Alternative reported for transparency: per-station de-meaned fit, so a biased background
    cannot be absorbed into the fire term. cov(raw, obs-bg) / var(raw) within stations."""
    by: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["sid"]].append(r)
    num = den = 0.0
    for rs in by.values():
        raw = np.array([r["raw"] for r in rs])
        y = np.array([r["obs"] - r["bg"] for r in rs])
        raw -= raw.mean()
        y -= y.mean()
        num += float(np.sum(raw * y))
        den += float(np.sum(raw * raw))
    return num / den if den > 0 else 0.0


# ------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", nargs=2, default=["2024-11-01", "2024-11-20"])
    ap.add_argument("--fit-days", type=int, default=10)
    ap.add_argument("--min-days", type=int, default=12, help="station must have >= this many days in the archive month")
    ap.add_argument("--delhi-km", type=float, default=40.0)
    ap.add_argument("--fit-on", choices=["delhi", "all"], default="all")
    ap.add_argument("--index", default="data/openaq_stations.json")
    ap.add_argument("--cache", default=".data/raw/hindcast")
    ap.add_argument("--web-out", default="web/public/dev")
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--hours", type=int, default=48)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    started = time.time()
    start, end = _d(a.window[0]), _d(a.window[1])
    cache = Path(a.cache)
    month = start.strftime("%Y-%m")
    exp_id = f"hindcast-{start:%Y%m%d}-{end:%Y%m%d}-fit{a.fit_days}"

    stations = load_stations(a.index, month, a.min_days, a.delhi_km)
    if not stations:
        print(f"no stations with >= {a.min_days} days in {month}; run tools/openaq_index.py", file=sys.stderr)
        return 2
    log.info("%d stations (%d within %.0f km of Delhi)", len(stations), sum(s["delhi"] for s in stations), a.delhi_km)
    obs = load_obs(stations, start, end + timedelta(days=2), cache)
    fires, fire_prov = load_fires(start, end, cache, os.environ.get("FIRMS_MAP_KEY"))
    wind = load_wind(start - timedelta(days=1), end + timedelta(days=3), cache)
    bg = load_background(stations, start - timedelta(days=1), end + timedelta(days=3), cache)
    log.info("%d obs hours, %d fires in window, wind %s..%s", len(obs), len(fires), wind.times[0], wind.times[-1])

    lat = np.array([s["lat"] for s in stations])
    lon = np.array([s["lon"] for s in stations])
    i_lat, i_lon = domain.cell_index(lat, lon)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rows: list[dict] = []
    run_log = []
    for day in days:
        now = day
        cutoff = iso_z(now - timedelta(hours=24))
        f24 = [f for f in fires if cutoff < f["acqUtc"] <= iso_z(now)]
        res = run_forecast(now, f24, wind, Params(seed=a.seed), hours=a.hours)
        raw_s = res.raw[:, i_lat, i_lon]  # (H+1, S)
        run_log.append({"day": day.strftime("%Y-%m-%d"), "fires": len(f24), "particles": res.stats["particles"],
                        "seconds": res.stats["elapsedSeconds"]})
        for h, t in enumerate(res.hours):
            if h == 0:
                continue
            ti = iso_z(t)
            for j, s in enumerate(stations):
                o = obs.get((s["id"], ti))
                b = bg.get((s["id"], ti))
                if o is None or b is None:
                    continue
                rows.append({"day": day.strftime("%Y-%m-%d"), "lead": h, "sid": s["id"], "delhi": s["delhi"],
                             "t": ti, "raw": float(raw_s[h, j]), "bg": b, "obs": o})
        log.info("run %s: %d fires, %d particles, %.1fs, %d rows so far", day.date(), len(f24), res.stats["particles"],
                 res.stats["elapsedSeconds"], len(rows))

    fit_days = {d.strftime("%Y-%m-%d") for d in days[:a.fit_days]}
    fit_rows = [r for r in rows if r["day"] in fit_days and (r["delhi"] or a.fit_on == "all")]
    test_rows = [r for r in rows if r["day"] not in fit_days]
    k = fit_k(fit_rows)
    k_anom = fit_k_anomaly(fit_rows)
    log.info("fitted k = %.4g (through origin) | anomaly k = %.4g on %d rows", k, k_anom, len(fit_rows))

    def evaluate(rs: list[dict]) -> dict:
        if not rs:
            return {"model": metrics(np.zeros(0), np.zeros(0)), "camsOnly": metrics(np.zeros(0), np.zeros(0))}
        obs_a = np.array([r["obs"] for r in rs])
        bg_a = np.array([r["bg"] for r in rs])
        raw_a = np.array([r["raw"] for r in rs])
        return {"model": metrics(k * raw_a + bg_a, obs_a), "camsOnly": metrics(bg_a, obs_a),
                "incrementCorr": round(float(np.corrcoef(raw_a, obs_a - bg_a)[0, 1]), 3) if raw_a.std() > 0 and (obs_a - bg_a).std() > 0 else None}

    by_lead = {"lead01_24": evaluate([r for r in test_rows if r["lead"] <= 24]),
               "lead25_48": evaluate([r for r in test_rows if r["lead"] > 24])}
    per_station = []
    for s in stations:
        rs = [r for r in test_rows if r["sid"] == s["id"]]
        m = evaluate(rs)
        per_station.append({"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"], "delhi": s["delhi"],
                            "distanceToDelhiKm": s["distanceToDelhiKm"], **m["model"],
                            "camsOnlyMae": m["camsOnly"]["mae"], "camsOnlyR2": m["camsOnly"]["r2"]})

    # daily Very Poor+ call, 24 h ahead: per (station, day) max over lead 1..24
    calls = []
    for s in stations:
        for day in days:
            rs = [r for r in test_rows if r["sid"] == s["id"] and r["day"] == day.strftime("%Y-%m-%d") and r["lead"] <= 24]
            if len(rs) < 12:
                continue
            p_aqi = max(aqi.pm25_subindex(k * r["raw"] + r["bg"]) for r in rs)
            o_aqi = max(aqi.pm25_subindex(r["obs"]) for r in rs)
            calls.append({"sid": s["id"], "name": s["name"], "day": day.strftime("%Y-%m-%d"), "predAqi": p_aqi, "obsAqi": o_aqi,
                          "pred": p_aqi >= 301, "obs": o_aqi >= 301})
    hits = sum(c["pred"] and c["obs"] for c in calls)
    misses = sum((not c["pred"]) and c["obs"] for c in calls)
    false_alarms = sum(c["pred"] and not c["obs"] for c in calls)
    correct_neg = sum((not c["pred"]) and (not c["obs"]) for c in calls)
    hit_rate = {"hits": hits, "misses": misses, "falseAlarms": false_alarms, "correctNegatives": correct_neg,
                "observedNegatives": misses + correct_neg, "informative": (misses + correct_neg) > 0 and (hits + false_alarms) > 0,
                "pod": round(hits / (hits + misses), 2) if hits + misses else None,
                "far": round(false_alarms / (hits + false_alarms), 2) if hits + false_alarms else None,
                "accuracy": round((hits + correct_neg) / len(calls), 2) if calls else None, "threshold": "AQI >= 301 (Very Poor) daily max, lead 1-24 h"}

    # peak timing error, events only
    timing = []
    for s in stations:
        for day in days:
            rs = sorted([r for r in test_rows if r["sid"] == s["id"] and r["day"] == day.strftime("%Y-%m-%d")], key=lambda r: r["lead"])
            if len(rs) < 36:
                continue
            o = np.array([r["obs"] for r in rs])
            if aqi.pm25_subindex(float(o.max())) < 301:
                continue
            p = np.array([k * r["raw"] + r["bg"] for r in rs])
            timing.append(abs(int(np.argmax(p)) - int(np.argmax(o))))
    timing_err = {"events": len(timing), "meanAbsHours": round(float(np.mean(timing)), 1) if timing else None,
                  "medianAbsHours": float(np.median(timing)) if timing else None}

    # episodes: stitched lead 1-24 h series over the test window for every station
    episodes = []
    for s in stations:
        rs = sorted([r for r in test_rows if r["sid"] == s["id"] and r["lead"] <= 24], key=lambda r: r["t"])
        if not rs:
            continue
        episodes.append({"id": s["id"], "name": s["name"], "t": [r["t"] for r in rs], "obs": [round(r["obs"], 1) for r in rs],
                         "bg": [round(r["bg"], 1) for r in rs], "pred": [round(k * r["raw"] + r["bg"], 1) for r in rs],
                         "fire": [round(k * r["raw"], 1) for r in rs]})

    right = max((c for c in calls if c["pred"] and c["obs"]), key=lambda c: c["obsAqi"], default=None)
    wrong = max((c for c in calls if c["pred"] != c["obs"]), key=lambda c: abs(c["predAqi"] - c["obsAqi"]), default=None)
    narrative = {
        "right": (f"{right['name']}, {right['day']}: called Very Poor or worse 24 h ahead (predicted daily max AQI {right['predAqi']}, "
                  f"observed {right['obsAqi']})." if right else "No correctly called Very Poor+ day in the test window."),
        "wrong": (f"{wrong['name']}, {wrong['day']}: predicted daily max AQI {wrong['predAqi']} but observed {wrong['obsAqi']} "
                  f"({'missed the episode' if wrong['obs'] else 'false alarm'})." if wrong else "No wrong Very Poor+ call in the test window."),
    }
    scatter = [[round(k * r["raw"] + r["bg"], 1), round(r["obs"], 1)] for r in test_rows]
    if len(scatter) > 3000:
        rng = np.random.default_rng(0)
        scatter = [scatter[i] for i in sorted(rng.choice(len(scatter), 3000, replace=False))]

    test_eval = evaluate(test_rows)
    fit_eval = evaluate(fit_rows)
    conf = conformal(np.array([k * r["raw"] + r["bg"] for r in test_rows]),
                     np.array([r["obs"] for r in test_rows])) if test_rows else {"n": 0}
    conf_lead = {
        "lead01_24": conformal(np.array([k * r["raw"] + r["bg"] for r in test_rows if r["lead"] <= 24]),
                               np.array([r["obs"] for r in test_rows if r["lead"] <= 24])),
        "lead25_48": conformal(np.array([k * r["raw"] + r["bg"] for r in test_rows if r["lead"] > 24]),
                               np.array([r["obs"] for r in test_rows if r["lead"] > 24])),
    }
    log.info("conformal half-widths: %s", conf)
    calibration = {
        "experimentId": exp_id, "k": k, "kAnomaly": k_anom, "estimator": "least squares through origin on obs-bg (DESIGN.md 5.7)",
        "tauHours": domain.TAU_HOURS, "kH": domain.K_H_M2_S, "seed": a.seed,
        "r2": test_eval["model"]["r2"], "mae": test_eval["model"]["mae"], "bias": test_eval["model"]["bias"],
        "camsOnlyR2": test_eval["camsOnly"]["r2"], "camsOnlyMae": test_eval["camsOnly"]["mae"],
        "camsOnlyBias": test_eval["camsOnly"]["bias"], "incrementCorr": test_eval.get("incrementCorr"),
        "window": f"{a.window[0]}..{a.window[1]}", "fitDays": a.fit_days, "testDays": len(days) - a.fit_days,
        "stations": len(stations), "stationsDelhi": sum(s["delhi"] for s in stations), "fitOn": a.fit_on,
        "windLevel": "ERA5 100 m (+10 m blend); live runs use 925 hPa", "fires": fire_prov,
        "conformal": conf, "conformalByLead": conf_lead,
        "fittedAt": iso_z(datetime.now(UTC)),
    }
    report = {
        **calibration,
        "disclaimer": "Out-of-sample metrics on days after the fit window. Observations: OpenAQ open-data archive "
                      "(hourly PM2.5, station timestamps treated as hour labels, +/-1 h ambiguity). "
                      "Background: CAMS global reanalysis/forecast via Open-Meteo (~40 km). Fires: " + fire_prov + ".",
        "metrics": {"fit": fit_eval, "test": test_eval, "byLead": by_lead, "hitRate": hit_rate, "peakTiming": timing_err},
        "perStation": per_station, "scatter": scatter, "episodes": episodes, "narrative": narrative,
        "runs": run_log, "rows": len(rows), "elapsedSeconds": round(time.time() - started, 1),
    }
    store = storage()
    store.put_json(f"validation/{exp_id}/report.json", report)
    store.put_json("validation/latest/report.json", report)
    store.put_json("validation/latest/calibration.json", calibration)
    if a.web_out:
        web = LocalStorage(a.web_out)
        web.put_json("validation/latest/report.json", report)
        web.put_json("validation/latest/calibration.json", calibration)
    print(json.dumps({"k": k, "test": test_eval, "byLead": by_lead, "hitRate": hit_rate, "peakTiming": timing_err,
                      "narrative": narrative, "stations": len(stations), "rows": len(rows),
                      "elapsedSeconds": report["elapsedSeconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

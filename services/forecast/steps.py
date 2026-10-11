"""The five steps of the `forecast-run` state machine (DESIGN.md §5.9), each a Lambda handler
in the container image and each callable locally. State is passed as a small JSON `ctx`
between steps; the heavy intermediates live in storage under work/{runId}/ (not public).

  prepare -> advect -> render -> sample -> publish

publish writes runs/latest.json last, so a failed run never replaces the last good one.
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime

import numpy as np

from common import ddb, domain
from common.calibration import load_calibration
from common.storage import CACHE_IMMUTABLE, CACHE_SHORT, Storage, storage
from common.timeutil import floor_hour, iso_z, run_id, utc_now
from forecast.run import Params, RunResult, run_forecast
from forecast.wind import WindField, background_grid_series, wind_series
from ingest_firms import firms
from ingest_firms.firms import to_geojson
from ingest_weather import openmeteo
from render import ramp

log = logging.getLogger(__name__)

DISCLAIMER = ("Forecast of the stubble-fire increment only. Background from CAMS. A simplified "
              "Lagrangian transport model, not a chemical transport model. Not for medical decisions.")
REGISTRATION_MARKERS = [(28.6139, 77.2090), (30.9010, 75.8573), (30.7333, 76.7794)]


def _now(ctx: dict) -> datetime:
    return datetime.fromisoformat(ctx["now"].replace("Z", "+00:00"))


def _work(rid: str, name: str) -> str:
    return f"work/{rid}/{name}"


# ---------------------------------------------------------------------------------- prepare
def prepare(ctx: dict | None = None, store_in: Storage | None = None, store_out: Storage | None = None) -> dict:
    """Load fires (24 h) and the latest weather pointer; write work/{runId}/inputs.json."""
    ctx = dict(ctx or {})
    store_in = store_in or storage()
    store_out = store_out or store_in
    now = _now(ctx) if ctx.get("now") else utc_now()
    rid = ctx.get("runId") or run_id(floor_hour(now))
    hours = int(ctx.get("hours", domain.FORECAST_HOURS))
    fires = firms.load_recent(24, now=now)
    wind_json, aq_json, pointer = openmeteo.load_latest_from(store_in)
    inputs = {"runId": rid, "now": iso_z(now), "hours": hours, "fires": fires, "weather": pointer}
    store_out.put_json(_work(rid, "inputs.json"), inputs)
    # the weather arrays are copied next to the inputs so advect/render read one place
    store_out.put_json(_work(rid, "wind.json"), wind_json)
    store_out.put_json(_work(rid, "aq.json"), aq_json)
    ddb.put_item({"PK": ddb.RUN_PK, "SK": rid, "status": "prepared", "startedAt": iso_z(now),
                  "fires": len(fires), "weather": pointer["id"], "hours": hours})
    log.info("prepare %s: %d fires, weather %s", rid, len(fires), pointer["id"])
    return {**ctx, "runId": rid, "now": iso_z(now), "hours": hours, "fires": len(fires), "weather": pointer["id"]}


# ----------------------------------------------------------------------------------- advect
def advect(ctx: dict, store_in: Storage | None = None, store_out: Storage | None = None,
           params: Params | None = None) -> dict:
    """Run the particle model; write work/{runId}/raw.npz (raw + blh + hours + meta)."""
    store_in = store_in or storage()
    store_out = store_out or store_in
    rid = ctx["runId"]
    inputs = store_out.get_json(_work(rid, "inputs.json"))
    wind = WindField(store_out.get_json(_work(rid, "wind.json")))
    params = params or Params()
    if ctx.get("seed") is not None:
        params.seed = int(ctx["seed"])
    result = run_forecast(_now(inputs), inputs["fires"], wind, params, hours=int(inputs["hours"]))
    buf = io.BytesIO()
    np.savez_compressed(buf, raw=result.raw, blh=result.blh)
    store_out.put(_work(rid, "raw.npz"), buf.getvalue(), "application/octet-stream")
    store_out.put_json(_work(rid, "meta.json"), result.meta())
    ddb.put_item({"PK": ddb.RUN_PK, "SK": rid, "status": "advected", "stats": result.stats,
                  "seed": params.seed, "tau_h": params.tau_h, "k_h": params.k_h})
    return {**ctx, "stats": result.stats}


def _load_result(store: Storage, rid: str) -> tuple[RunResult, dict]:
    meta = store.get_json(_work(rid, "meta.json"))
    inputs = store.get_json(_work(rid, "inputs.json"))
    arrs = np.load(io.BytesIO(store.get(_work(rid, "raw.npz"))))
    p = meta["params"]
    params = Params(**{k: v for k, v in p.items() if k in Params.__dataclass_fields__})
    hours = [datetime.fromisoformat(h.replace("Z", "+00:00")) for h in meta["hours"]]
    result = RunResult(rid, hours[0], hours, arrs["raw"], arrs["blh"], params, inputs["fires"], meta["stats"])
    return result, inputs


# ----------------------------------------------------------------------------------- render
def render(ctx: dict, store_in: Storage | None = None, store_out: Storage | None = None,
           debug_markers: bool = False) -> dict:
    """Apply k (if calibrated), write overlays, grid JSON, background.json and fires.geojson."""
    store_in = store_in or storage()
    store_out = store_out or store_in
    rid = ctx["runId"]
    result, inputs = _load_result(store_out, rid)
    cal = load_calibration(store_in)
    k = cal["k"]
    mode = "cpcb" if k is not None else "relative"
    positive = result.raw[result.raw > 0]
    vmax = float(np.percentile(positive, 99.5)) if positive.size else 0.0
    markers = REGISTRATION_MARKERS if debug_markers else None
    for h, t in enumerate(result.hours):
        field = result.raw[h] * k if k is not None else result.raw[h]
        png = ramp.render_png(field, mode, vmax=vmax, markers=markers)
        store_out.put(f"runs/{rid}/overlay/{h:02d}.png", png, "image/png", CACHE_IMMUTABLE)
        values = field if k is not None else (field / vmax if vmax > 0 else field)
        store_out.put_json(f"runs/{rid}/grid/{h:02d}.json", {
            "t": iso_z(t), "hour": h,
            "units": "ug/m3" if k is not None else "relative (fraction of run vmax)",
            "shape": [domain.NLAT, domain.NLON],
            "order": "row-major, i_lat from south, i_lon from west",
            "max": round(float(values.max()), 4),
            "values": [round(float(v), 4) for v in values.ravel()],
        }, CACHE_IMMUTABLE)
    aq = store_out.get_json(_work(rid, "aq.json"))
    store_out.put_json(f"runs/{rid}/background.json", background_grid_series(aq, result.hours), CACHE_IMMUTABLE)
    wind_json = store_out.get_json(_work(rid, "wind.json"))
    store_out.put_json(f"runs/{rid}/wind.json", wind_series(wind_json, result.hours), CACHE_IMMUTABLE)
    store_out.put_json(f"runs/{rid}/fires.geojson", to_geojson(result.fires), CACHE_IMMUTABLE)
    overlay = {"mode": mode, "vmax": vmax, **ramp.legend(mode)}
    store_out.put_json(_work(rid, "render.json"), {"overlay": overlay, "calibration": cal})
    return {**ctx, "overlay": mode, "k": k}


# ----------------------------------------------------------------------------------- sample
def sample(ctx: dict, store_in: Storage | None = None, store_out: Storage | None = None) -> dict:
    """Per-school exposure summary for the map layer (runs/{runId}/schools.json) and, when
    DynamoDB is enabled, the per-school hourly series (SCHOOL#id / FC#runId)."""
    from sample.schools import sample_schools  # local import: keeps the image's cold start small

    store_in = store_in or storage()
    store_out = store_out or store_in
    rid = ctx["runId"]
    result, _ = _load_result(store_out, rid)
    cal = load_calibration(store_in)
    schools = store_in.get_json("static/schools.geojson")
    if not schools:
        log.warning("static/schools.geojson missing: sample step writes an empty layer")
        schools = {"type": "FeatureCollection", "features": []}
    aq = store_out.get_json(_work(rid, "aq.json"))
    # per-school overrides (hours, purifiers) for onboarded schools live in DynamoDB META
    meta: dict[str, dict] = {}
    for f in schools.get("features", []):
        pr = f.get("properties", {})
        if pr.get("onboarded") or pr.get("demo"):
            m = ddb.get_item(f"SCHOOL#{pr.get('id')}", "META")
            if m:
                meta[pr["id"]] = m
    layer, items, summary, cards = sample_schools(result, aq, schools, cal["k"], rid, school_meta=meta,
                                                  calibration=cal)
    store_out.put_json(f"runs/{rid}/schools.json", layer, CACHE_IMMUTABLE)
    for sid, card in cards.items():
        card["calibration"] = {k: cal[k] for k in ("k", "status", "r2", "mae", "window", "stations", "conformal")}
        store_out.put_json(_work(rid, f"cards/{sid}.json"), card)                       # private: the principal's card
        store_out.put_json(f"runs/{rid}/protocol/{sid}.json", card, CACHE_IMMUTABLE)   # public: chapter 5 demo / school page
    ddb.put_items(items)
    zones_info = _zones_and_burning(ctx, store_in, store_out, result, aq, cal["k"])
    # cards for every onboarded / demo entity of every actor type + the run's decision records
    from sample.entities import entity_cards, workflow_records

    actors = store_in.get_json("static/actors.json") or {"entities": []}
    burning_doc = store_out.get_json(f"runs/{rid}/burning.json") or {"features": []}
    ecards = entity_cards(result, aq, cal["k"], actors, burning_doc, _now(ctx),
                          calibration={k2: cal[k2] for k2 in ("k", "status", "r2", "mae", "window", "stations",
                                                               "conformal", "conformalByLead")})
    features = []
    for eid, card in ecards.items():
        store_out.put_json(_work(rid, f"cards/{eid}.json"), card)
        store_out.put_json(f"runs/{rid}/protocol/{eid}.json", card, CACHE_IMMUTABLE)
        ent = next((e for e in actors.get("entities", []) if e["id"] == eid), {})
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [ent.get("lon"), ent.get("lat")]},
                         "properties": {"id": eid, "name": card["name"], "name_hi": card.get("name_hi"), "type": card["actorType"], "kind": card["kind"],
                                        "typeLabel": card["actorLabel"], "personTitle": card["personTitle"], "persona": card.get("persona"),
                                        "dayTier": card.get("dayTier"), "date": card.get("date"), "headline": card.get("headline"),
                                        "peakAqi": card.get("peakAqi"), "cells": len(card.get("cells") or []), "burningNow": card.get("burningNow"),
                                        "demo": card.get("demo"), "onboarded": card.get("onboarded"), "radiusKm": ent.get("radiusKm")}})
    store_out.put_json(f"runs/{rid}/entities.json", {"type": "FeatureCollection", "runId": rid, "features": features}, CACHE_IMMUTABLE)
    inputs = store_out.get_json(_work(rid, "inputs.json"))
    n_records = workflow_records(result, ecards, inputs, store_out, cal["k"])   # records/ is published next to runs/
    entities_summary = {"count": len(ecards), "byType": {}, "ids": sorted(ecards)}
    for c in ecards.values():
        entities_summary["byType"][c["actorType"]] = entities_summary["byType"].get(c["actorType"], 0) + 1
    return {**ctx, "schools": {**summary, "cards": sorted(set(summary.get("cards", [])) | set(ecards))}, **zones_info,
            "entities": entities_summary, "recordsWritten": n_records}


def _zones_and_burning(ctx: dict, store_in: Storage, store_out: Storage, result: RunResult, aq: dict, k: float | None) -> dict:
    """Exposure zones, active burning areas and the 48 h burning-risk score (keyless inputs)."""
    from zones import burning, ndvi
    from zones.zones import zone_summaries

    rid = ctx["runId"]
    now = _now(ctx)
    store_out.put_json(f"runs/{rid}/zones.json", zone_summaries(result, aq, k), CACHE_IMMUTABLE)
    fires48 = firms.load_recent(48, now=now)
    clim = burning.climatology(store_in.get_json("static/climatology_2024.json"), now)
    wind_json = store_out.get_json(_work(rid, "wind.json"))
    from datetime import timedelta as _td

    from forecast.wind import precip_sum

    rain_coarse = precip_sum(wind_json, now, now + _td(hours=48))      # 0.5 deg grid
    rain48 = np.repeat(np.repeat(rain_coarse[:-1, :-1], 2, axis=0), 2, axis=1)[: burning.NLAT, : burning.NLON]
    nd = None
    try:
        nd = ndvi.ndvi_change(now, store=store_in)
    except Exception as exc:  # noqa: BLE001 - NDVI is an optional component
        log.warning("NDVI unavailable: %s", exc)
    risk = burning.burn_risk(fires48, now, clim, nd["change"] if nd else None, rain48)
    if nd:
        risk["ndvi"] = {k2: nd[k2] for k2 in ("layer", "date", "prevDate", "tileTemplate", "colormapEntries")}
    store_out.put_json(f"runs/{rid}/burning.json", risk, CACHE_IMMUTABLE)
    return {"burning": {"topBurning": [a["name"] for a in risk["topBurning"][:3]], "cells": len(risk["features"]),
                        "inputs": risk["inputs"]}, "ndvi": risk.get("ndvi")}


# ---------------------------------------------------------------------------------- publish
def publish(ctx: dict, store_in: Storage | None = None, store_out: Storage | None = None,
            write_latest: bool = True) -> dict:
    """manifest.json, then runs/latest.json last, then a CloudFront invalidation."""
    store_in = store_in or storage()
    store_out = store_out or store_in
    rid = ctx["runId"]
    inputs = store_out.get_json(_work(rid, "inputs.json"))
    meta = store_out.get_json(_work(rid, "meta.json"))
    rendered = store_out.get_json(_work(rid, "render.json"))
    generated_at = utc_now()
    cal = rendered["calibration"]
    manifest = {
        "runId": rid,
        "generatedAt": iso_z(generated_at),
        "domain": list(domain.DOMAIN_WSEN),
        "imageCorners": domain.IMAGE_CORNERS,
        "hours": meta["hours"],
        "overlayUrl": f"runs/{rid}/overlay/{{hh}}.png",
        "gridUrl": f"runs/{rid}/grid/{{hh}}.json",
        "backgroundUrl": f"runs/{rid}/background.json",
        "firesUrl": f"runs/{rid}/fires.geojson",
        "schoolsUrl": f"runs/{rid}/schools.json",
        "windUrl": f"runs/{rid}/wind.json",
        "zonesUrl": f"runs/{rid}/zones.json",
        "burningUrl": f"runs/{rid}/burning.json",
        "ndvi": ctx.get("ndvi"),
        "protocolUrl": f"runs/{rid}/protocol/{{schoolId}}.json",
        "demoSchools": (ctx.get("schools") or {}).get("cards", []),
        "entities": ctx.get("entities"),
        "entitiesUrl": f"runs/{rid}/entities.json",
        "records": {"writtenThisRun": ctx.get("recordsWritten"), "recordsUrl": "records/{entityId}/"},
        "overlay": rendered["overlay"],
        "calibration": {"k": cal["k"], "tauHours": meta["params"]["tau_h"], "kH": meta["params"]["k_h"],
                        "seed": meta["params"]["seed"], "status": cal["status"], "r2": cal["r2"],
                        "mae": cal["mae"], "bias": cal.get("bias"), "window": cal["window"],
                        "stations": cal["stations"], "windLevel": cal.get("windLevel")},
        "stats": meta["stats"],
        "fires": {"count": len(inputs["fires"]), "window": "24h", "source": "NASA FIRMS VIIRS NRT"},
        "weather": inputs["weather"],
        "schools": ctx.get("schools"),
        "disclaimer": DISCLAIMER,
    }
    store_out.put_json(f"runs/{rid}/manifest.json", manifest, CACHE_IMMUTABLE)
    if write_latest:
        store_out.put_json("runs/latest.json", {"runId": rid, "generatedAt": iso_z(generated_at)}, CACHE_SHORT)
        ddb.put_item({"PK": ddb.RUN_PK, "SK": ddb.LATEST_SK, "runId": rid, "generatedAt": iso_z(generated_at)})
        _invalidate(["/runs/latest.json", "/api/latest"])
    ddb.put_item({"PK": ddb.RUN_PK, "SK": rid, "status": "published", "finishedAt": iso_z(generated_at),
                  "k": cal["k"], "r2": cal["r2"], "mae": cal["mae"], "hours": len(meta["hours"])})
    log.info("published %s (%d hours, %s)", rid, len(meta["hours"]), rendered["overlay"]["mode"])
    return {**ctx, "generatedAt": iso_z(generated_at), "manifest": f"runs/{rid}/manifest.json"}


def _invalidate(paths: list[str]) -> None:
    dist = os.environ.get("CDN_DISTRIBUTION_ID")
    if not dist:
        return
    from common.aws import client

    client("cloudfront").create_invalidation(
        DistributionId=dist,
        InvalidationBatch={"Paths": {"Quantity": len(paths), "Items": paths},
                           "CallerReference": f"{iso_z(utc_now())}-{paths[0]}"},
    )


# --------------------------------------------------------------------------- local pipeline
def run_all(store_in: Storage, store_out: Storage, now: datetime | None = None, hours: int = domain.FORECAST_HOURS,
            params: Params | None = None, debug_markers: bool = False, write_latest: bool = True) -> dict:
    ctx = prepare({"now": iso_z(now or utc_now()), "hours": hours}, store_in, store_out)
    ctx = advect(ctx, store_in, store_out, params)
    ctx = render(ctx, store_in, store_out, debug_markers)
    ctx = sample(ctx, store_in, store_out)
    return publish(ctx, store_in, store_out, write_latest)


# ---------------------------------------------------------------------------- Lambda entry
def _lambda(step):
    def handler(event, context):
        logging.getLogger().setLevel(logging.INFO)
        return step(event or {})
    return handler


prepare_handler = _lambda(prepare)
advect_handler = _lambda(advect)
render_handler = _lambda(render)
sample_handler = _lambda(sample)
publish_handler = _lambda(publish)

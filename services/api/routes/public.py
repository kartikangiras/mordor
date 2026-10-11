"""Unauthenticated, CloudFront-cacheable GETs (DESIGN.md §8)."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Response

from api.errors import ApiError
from common import domain
from common.storage import storage
from common.timeutil import iso_z, utc_now

router = APIRouter()

DISCLAIMER = (
    "Forecast of the stubble-fire increment only. Background from CAMS. "
    "A simplified Lagrangian transport model, not a chemical transport model. "
    "Not for medical decisions."
)

STALE_AFTER = timedelta(hours=3)


@router.get("/api/health")
def health(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "domain": domain.describe()["wsen"], "time": iso_z(utc_now())}


@router.get("/api/latest")
def latest(response: Response):
    """The manifest of the last *completed* run. runs/latest.json is written last by the
    publish step, so a half-written run is never served (§5.9)."""
    response.headers["Cache-Control"] = "public, max-age=60"
    pointer = storage().get_json("runs/latest.json")
    if not pointer or "runId" not in pointer:
        raise ApiError(404, "no_run", "No forecast run has been published yet.")
    manifest = storage().get_json(f"runs/{pointer['runId']}/manifest.json")
    if not manifest:
        raise ApiError(500, "manifest_missing", f"Manifest for run {pointer['runId']} is missing.")
    manifest.setdefault("disclaimer", DISCLAIMER)
    return manifest


@router.get("/api/stations/latest")
def stations_latest(response: Response):
    """Observed PM2.5 per station for the validation overlay, with an isStale flag.

    Each station carries `tier` ('reference' for a CPCB / DPCC / IMD-class monitor, 'low_cost'
    for a sensor network) and `provider`; the overlay must render the two differently. See
    `ingest_cpcb/openaq_live.py` for why the live layer is mostly low-cost right now."""
    response.headers["Cache-Control"] = "public, max-age=300"
    snap = storage().get_json("live/cpcb/latest.json")
    if not snap:
        return {"fetchedAt": None, "stations": []}
    from datetime import datetime

    now = utc_now()
    for s in snap.get("stations", []):
        try:
            observed = datetime.fromisoformat(s["observedAt"].replace("Z", "+00:00"))
            s["isStale"] = (now - observed) > STALE_AFTER
        except (KeyError, ValueError):
            s["isStale"] = True
    return snap


@router.get("/api/cap/{entity}")
def cap_alert(entity: str):
    """The published advisory for one entity as OASIS CAP 1.2 XML (DESIGN.md §6.5).

    Same content as the public protocol card, projected into the standard so a Directorate of
    Education, the CAQM or any CAP-aware pipeline can ingest it. `status` is `Exercise`: mordor
    is not an authorised alerting authority and must not emit `Actual`."""
    from datetime import datetime

    from protocol import cap

    pointer = storage().get_json("runs/latest.json")
    if not pointer or "runId" not in pointer:
        raise ApiError(404, "no_run", "No forecast run has been published yet.")
    rid = pointer["runId"]
    card = storage().get_json(f"runs/{rid}/protocol/{entity}.json")
    if not card:
        raise ApiError(404, "no_card", f"No published card for {entity!r} in run {rid}.")
    layer = storage().get_json(f"runs/{rid}/schools.json") or {"features": []}
    ent = {"id": entity, "name": (card.get("school") or {}).get("name") or entity}
    for f in layer.get("features", []):
        if (f.get("properties") or {}).get("id") == entity:
            lon, lat = f["geometry"]["coordinates"]
            ent.update({"lat": lat, "lon": lon,
                        "name": (f["properties"].get("name") or ent["name"])})
            break
    sent = datetime.fromisoformat(pointer.get("generatedAt", iso_z(utc_now())).replace("Z", "+00:00"))
    xml = cap.to_xml(card, ent, rid, sent, message=card.get("message"))
    # One media type, set once: PlainTextResponse + a manual header produced a doubled
    # "text/plain...,application/cap+xml" value that a strict CAP consumer could reject.
    return Response(content=xml, media_type="application/cap+xml",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("/api/schools/{school_id}/card")
def school_card(school_id: str, response: Response):
    """Tomorrow's public card for any mapped school (the pipeline writes an FC# item for all of
    them; only onboarded and demo schools get a file on the CDN). Standard message, no contacts;
    the story's chapter 7 uses it for the worst school of the day (PIVOT_PLAN.md task 29)."""
    from api.routes.principal import _card, _latest_run_id, _school_meta
    from notify import fallback

    response.headers["Cache-Control"] = "public, max-age=300"
    rid = _latest_run_id()
    meta = _school_meta(school_id)
    card = _card(school_id, rid)
    public = {k: v for k, v in card.items() if k not in ("PK", "SK", "ttl")}
    public.update({"schoolId": school_id, "name": meta.get("name") or school_id, "name_hi": meta.get("name_hi"),
                   "demo": bool(meta.get("demo")), "onboarded": bool(meta.get("onboarded"))})
    if card.get("dayTier"):
        public["message"] = fallback.render(public["name"], card["date"], card["dayTier"], card.get("windows", []), card.get("peakAqi"),
                                            card.get("dismissalIst") or ["15:00", "16:00"])
    return public


@router.get("/api/guidelines")
def guidelines(response: Response):
    """The public per-tier guidance (PIVOT_PLAN.md D6 b): one source, in services/protocol/actors.py,
    for the map's "What to do" tab and the zones page."""
    from protocol.actors import PUBLIC_GUIDELINES

    response.headers["Cache-Control"] = "public, max-age=3600"
    return {"tiers": PUBLIC_GUIDELINES, "anchor": "CPCB AQI bands and CAQM GRAP stages", "note": "General guidance for anyone. Schools, associations and offices get their role's card instead."}


@router.get("/api/validation")
def validation(response: Response):
    """The hindcast report (DESIGN.md §13.2): out-of-sample metrics, scatter, per-station table,
    one named right case and one named wrong case."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    report = storage().get_json("validation/latest/report.json")
    if not report:
        raise ApiError(404, "no_validation", "No hindcast has been run yet (tools/hindcast.py).")
    return report


@router.get("/api/schools")
def schools(response: Response, bbox: str | None = None):
    """GeoJSON of schools with day tier for the latest run; optional bbox=w,s,e,n. Capped at
    2,000 features: beyond that the highest-tier subset is returned and truncated=true."""
    response.headers["Cache-Control"] = "public, max-age=300"
    pointer = storage().get_json("runs/latest.json")
    if not pointer:
        raise ApiError(404, "no_run", "No forecast run has been published yet.")
    layer = storage().get_json(f"runs/{pointer['runId']}/schools.json")
    if not layer:
        raise ApiError(404, "no_schools", "The latest run has no school layer.")
    feats = layer["features"]
    if bbox:
        try:
            w, s, e, n = (float(x) for x in bbox.split(","))
        except ValueError:
            raise ApiError(400, "bad_bbox", "bbox must be w,s,e,n") from None
        feats = [f for f in feats if w <= f["geometry"]["coordinates"][0] <= e and s <= f["geometry"]["coordinates"][1] <= n]
    truncated = False
    if len(feats) > 2000:
        order = {"T4": 0, "T3": 1, "T2": 2, "T1": 3, "T0": 4, None: 5}
        feats = sorted(feats, key=lambda f: order.get(f["properties"].get("dayTier"), 5))[:2000]
        truncated = True
    return {**layer, "features": feats, "truncated": truncated}


@router.get("/api/impact")
def impact(response: Response, date: str | None = None):
    """Live numbers for the closing frame (DESIGN.md §8): schools that logged a decision today,
    their students, and outdoor hours avoided (school-window hours at T2+ for schools that took
    PT indoors). Reads the GSI1 DATE# partition; zero, not fake, when nothing is logged."""
    from common import ddb
    from common.timeutil import IST, utc_now

    response.headers["Cache-Control"] = "public, max-age=60"
    day = date or utc_now().astimezone(IST).strftime("%Y-%m-%d")
    logs = ddb.query_gsi1(f"DATE#{day}")
    if not logs and not ddb.enabled():
        for key in storage().list("work/logs/"):
            if f"/{day}-" in key:
                item = storage().get_json(key)
                if item:
                    logs.append(item)
    schools = {lg.get("GSI1SK") or lg.get("PK") for lg in logs}
    # lifecycle accounting: impact statements of the date, verified vs provisional
    from records import store as records

    acc = [r for r in records.records_for_date(day) if r["kind"] == "account"]
    verified = [r for r in acc if r["payload"].get("status") == "verified"]
    by_unit: dict[str, float] = {}
    for r in verified:
        by_unit[r["payload"]["unit"]] = by_unit.get(r["payload"]["unit"], 0) + float(r["payload"].get("value") or 0)
    # what the action plans covered: cells chosen by the district offices today (27 km burn-risk cells)
    plans = [r for r in records.records_for_date(day) if r["kind"] == "advise" and r["payload"].get("subject") == "plan"]
    plan_cells = {(r["entity"], c.get("i"), c.get("j")) for r in plans for c in (r["payload"].get("cells") or [])}
    offices = {r["entity"] for r in plans}
    meta_all = {e.get("id"): e for e in (storage().get_json("static/actors.json") or {"entities": []})["entities"]}
    acted = [lg for lg in logs if lg.get("actions")]
    return {
        "date": day, "schools": len(schools), "students": int(sum((lg.get("students") or 0) for lg in logs)),
        "studentsProtected": int(sum((lg.get("students") or 0) for lg in acted if (lg.get("actorType") or "school") == "school")),
        "peopleProtected": int(sum((lg.get("people") or lg.get("students") or 0) for lg in acted)),
        "plan": {"offices": len(offices), "cells": len(plan_cells), "areaKm2": len(plan_cells) * 27 * 27,
                 "radiusKm": max((float((meta_all.get(o) or {}).get("radiusKm") or 0) for o in offices), default=0)},
        "hospitalsAlerted": len({lg.get("GSI1SK") or lg.get("PK") for lg in logs if (lg.get("actorType") == "hospital") and ("alert_wards" in (lg.get("actions") or []))}),
        "bedsReady": int(sum((lg.get("people") or 0) for lg in logs if lg.get("actorType") == "hospital" and "beds_ready" in (lg.get("actions") or []))),
        "people": int(sum((lg.get("people") or lg.get("students") or 0) for lg in logs)),
        "byType": {t: sum(1 for lg in logs if (lg.get("actorType") or "school") == t) for t in {(lg.get("actorType") or "school") for lg in logs}},
        "outdoorHoursAvoided": round(float(sum((lg.get("outdoorHoursCancelled") or 0) for lg in logs)), 1),
        "decisionsLogged": len(logs), "sentVia": {v: sum(1 for lg in logs if lg.get("sentVia") == v) for v in {lg.get("sentVia") for lg in logs} if v},
        "records": {"impactStatements": len(acc), "verified": len(verified), "provisional": sum(1 for r in acc if r["payload"].get("status") == "provisional"),
                   "notCredited": sum(1 for r in acc if r["payload"].get("status") == "not_credited"), "verifiedByUnit": by_unit},
        "method": "schools = distinct entities with an acknowledged card for the date; people from onboarding records; "
                  "studentsProtected / peopleProtected = people of entities that logged at least one action; plan.areaKm2 = distinct 27 km burn-risk cells in today's action plans; "
                  "outdoorHoursAvoided = window hours at tier T2 or worse for entities that acted; "
                  "records.verifiedByUnit counts only impact statements whose day the nearest station confirmed",
    }

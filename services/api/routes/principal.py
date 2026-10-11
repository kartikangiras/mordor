"""Principal routes (Cognito JWT): the protocol card, the acknowledgement log, email delivery.
DESIGN.md §8, §6.5, §7.1."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from api.auth import principal, require_role
from api.errors import ApiError
from common import ddb
from common.aws import secret
from common.storage import storage
from common.timeutil import IST, iso_z, utc_now
from protocol.actors import ACTOR_TYPES, PERSONAS, ROLES, actor_type
from records import store as records

log = logging.getLogger(__name__)
router = APIRouter()


def _latest_run_id() -> str:
    ptr = storage().get_json("runs/latest.json")
    if not ptr:
        raise ApiError(404, "no_run", "No forecast run has been published yet.")
    return ptr["runId"]


def _school_meta(school_id: str) -> dict:
    meta = ddb.get_item(f"SCHOOL#{school_id}", "META")
    if meta:
        return meta
    for e in (storage().get_json("static/actors.json") or {"entities": []})["entities"]:
        if e.get("id") == school_id:
            return {"name": e["name"], "name_hi": e.get("name_hi"), "lat": e["lat"], "lon": e["lon"], "type": e.get("type", "school"),
                    "hours": e.get("hours", ["08:00", "14:00"]), "dismissal": e.get("dismissal", ["15:00", "16:00"]),
                    "hasPurifiers": bool(e.get("hasPurifiers")), "students": e.get("students"), "residents": e.get("residents"),
                    "machines": e.get("machines"), "district": e.get("district"), "email": None, "persona": e.get("persona")}
    layer = storage().get_json("static/schools.geojson") or {"features": []}
    for f in layer["features"]:
        if f["properties"].get("id") == school_id:
            lon, lat = f["geometry"]["coordinates"]
            return {"name": f["properties"].get("name") or school_id, "name_hi": f["properties"].get("name_hi"),
                    "lat": lat, "lon": lon, "hours": ["08:00", "14:00"], "dismissal": ["15:00", "16:00"],
                    "hasPurifiers": False, "students": f["properties"].get("students"), "email": None}
    raise ApiError(404, "unknown_school", f"No school {school_id!r} in the database.")


def _card(school_id: str, run_id: str) -> dict:
    fc = ddb.get_item(f"SCHOOL#{school_id}", f"FC#{run_id}")
    if not fc:
        fc = storage().get_json(f"work/{run_id}/cards/{school_id}.json")
    if not fc:
        raise ApiError(404, "no_card", f"No forecast card for {school_id} in run {run_id}. Is the school onboarded?")
    return fc


def _message(school_id: str, meta: dict, card: dict, actions: list[str]) -> dict:
    inputs = {"schoolId": school_id, "school": meta["name"], "date": card["date"], "tier": card["dayTier"],
              "actorType": card.get("actorType", "school"), "kind": card.get("kind", "exposure"),
              "card": {k: card.get(k) for k in ("cells", "burningNow", "dayTier", "district")} if card.get("kind") == "source" else None,
              "grapAnchor": (card.get("protocol") or {}).get("grapAnchor", ""), "windows": card["windows"],
              "peakAqi": card.get("peakAqi"), "actions": actions, "hasPurifiers": card.get("hasPurifiers", False),
              "schoolHours": card.get("schoolHoursIst"), "dismissal": card.get("dismissalIst")}
    fn = os.environ.get("NOTIFY_FUNCTION")
    out = _invoke_notify(inputs) if fn else None
    if out is not None:
        return out
    from notify.service import generate

    return generate(inputs, use_agent=False if fn else None)


def _invoke_notify(payload: dict) -> dict | None:
    """One bounded call to NotifyFn: the card and the assessment must never wait on a model.
    One attempt, read timeout well inside the API's 30 s, None on any failure (a hung NotifyFn
    killed every card, 2026-10-10)."""
    fn = os.environ.get("NOTIFY_FUNCTION")
    if not fn:
        return None
    import boto3
    from botocore.config import Config as BotoConfig

    from common.aws import REGION

    try:
        lam = boto3.client("lambda", region_name=REGION, config=BotoConfig(connect_timeout=2, read_timeout=15, retries={"max_attempts": 0}))
        resp = lam.invoke(FunctionName=fn, Payload=json.dumps(payload).encode())
        return json.loads(resp["Payload"].read())
    except Exception as exc:  # noqa: BLE001 - any failure means "template"
        logging.getLogger(__name__).warning("notify invoke failed (%s); using the template", type(exc).__name__)
        return None


def _by(who: dict, meta: dict | None = None) -> dict:
    """Who acted, for a record: the login's role, sub and - for a demo login - its persona. A dev
    (header) login may borrow the demo entity's persona; a real login never does (AUTH-9)."""
    persona = who.get("persona") or ((meta or {}).get("persona") if who.get("dev") else None)
    return {"role": who["role"], "sub": who["sub"], "persona": persona}


def _may_act_for(who: dict, entity_id: str) -> bool:
    """The login's own entity, or one this login registered itself: the walkthrough registers any
    mapped school, and the person who registered it may then act for it (PIVOT_PLAN.md D9)."""
    if who.get("entityId") == entity_id:
        return True
    return any(r.get("kind") == "enrol" and (r.get("by") or {}).get("sub") == who.get("sub") for r in records.records_for(entity_id))


def _recent_logs(school_id: str, limit: int = 3) -> list[dict]:
    if ddb.enabled():
        items = ddb.query(f"SCHOOL#{school_id}", "LOG#", scan_forward=False, limit=limit)
    else:  # local dev: the ack handler mirrors log items into storage
        keys = sorted(storage().list(f"work/logs/{school_id}/"), reverse=True)[:limit]
        items = [i for i in (storage().get_json(k) for k in keys) if i]
    return [{k: v for k, v in i.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK")} for i in items]


@router.get("/api/me")
def me(request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    out = {"schoolId": who["schoolId"], "entityId": who["entityId"], "role": who["role"], "roleDescription": ROLES.get(who["role"]),
           "email": who["email"], "dev": who["dev"], "runId": _latest_run_id(), "school": None}
    if who["entityId"]:
        meta = _school_meta(who["entityId"])
        at = actor_type(meta.get("type"))
        out["school"] = {**{k: meta.get(k) for k in ("name", "name_hi", "lat", "lon", "hours", "dismissal", "hasPurifiers", "students",
                                                     "residents", "machines", "district", "email", "principal", "persona")},
                         "type": meta.get("type", "school"), "typeLabel": at["label"], "personTitle": at["personTitle"]}
    return out


@router.get("/api/roles")
def roles(response: Response):
    """Role model and the fictional demo personas (as Hestia's Raj / Maria / Jennifer / Carlos)."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {"roles": ROLES, "actorTypes": {k: {"label": v["label"], "kind": v["kind"], "personTitle": v["personTitle"], "anchor": v["anchor"],
                                               "impactUnit": v["impactUnit"]} for k, v in ACTOR_TYPES.items()},
            "personas": PERSONAS, "note": "Personas are fictional demo users, not real people."}


@router.get("/api/me/forecast")
def my_forecast(request: Request, response: Response, entity: str | None = None):
    """The card for the login's entity, or - `?entity=` - for a school this login registered."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    if entity and not _may_act_for(who, entity):
        raise ApiError(403, "forbidden", "This login belongs to a different entity and did not register this one.")
    sid = entity or who["schoolId"]
    if not sid:
        raise ApiError(400, "no_entity", "This login has no entity attached; pass ?entity= for a school you registered.")
    meta = _school_meta(sid)
    run_id = _latest_run_id()
    card = _card(sid, run_id)
    logs = _recent_logs(sid)
    today_log = next((lg for lg in logs if lg.get("runId") == run_id), None)
    actions = today_log["actions"] if today_log else card.get("defaultActions", [])
    message = _message(sid, meta, card, actions)
    return {
        "school": {"id": sid, "name": meta["name"], "name_hi": meta.get("name_hi"), "lat": meta["lat"], "lon": meta["lon"],
                   "hours": meta.get("hours"), "dismissal": meta.get("dismissal"), "hasPurifiers": meta.get("hasPurifiers", False),
                   "email": meta.get("email"), "students": meta.get("students")},
        "runId": run_id, "date": card["date"], "hourly": card.get("hourly", []), "dayTier": card["dayTier"],
        "actorType": card.get("actorType", "school"), "kind": card.get("kind", "exposure"), "actions": card.get("actions"),
        "anchor": card.get("anchor"), "strip": card.get("strip"), "cells": card.get("cells"), "burningNow": card.get("burningNow"),
        "district": card.get("district"), "impactUnit": card.get("impactUnit"), "people": card.get("people"), "audience": card.get("audience"),
        "windows": card["windows"], "protocol": card.get("protocol"), "headline": card.get("headline"),
        "defaultActions": card.get("defaultActions", []), "peakAqi": card.get("peakAqi"),
        "outdoorHoursCancelled": card.get("outdoorHoursCancelled", 0), "message": message,
        "calibration": card.get("calibration"), "interval": card.get("interval"), "dose": card.get("dose"),
        "log": logs, "acked": today_log,
    }


class AckBody(BaseModel):
    runId: str
    actions: list[str] = Field(default_factory=list)
    sentVia: str | None = None


class AssessBody(BaseModel):
    runId: str
    actions: list[str] = Field(default_factory=list)


@router.post("/api/actors/{school_id}/assess")
def assess_choice(school_id: str, body: AssessBody, request: Request, response: Response):
    """What this choice does (PIVOT_PLAN.md task 38): coverage of the hours at risk, the people-hours
    it protects, what stays exposed, and three sentences from the model (template if it is slow)."""
    from protocol.assess import assess, fallback_text

    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "operator")
    if not _may_act_for(who, school_id):
        raise ApiError(403, "forbidden", "This login belongs to a different entity and did not register this one.")
    meta = _school_meta(school_id)
    card = _card(school_id, body.runId)
    a = assess(card, body.actions, meta)
    name = meta.get("name") or school_id
    narrative = _invoke_notify({"task": "assess", "name": name, "assessment": a}) or {"en": fallback_text(a, name), "source": "template"}
    return {**a, "narrative": narrative}


@router.post("/api/actors/{school_id}/ack")
@router.post("/api/schools/{school_id}/ack")
def ack(school_id: str, body: AckBody, request: Request, response: Response):
    """Idempotent per (entity, date, runId): the decision log the DoE may ask for, and the
    lifecycle's `act` record."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "operator")
    if not _may_act_for(who, school_id):
        raise ApiError(403, "forbidden", "This login belongs to a different entity and did not register this one.")
    meta0 = _school_meta(school_id)
    allowed = [a["id"] for a in actor_type(meta0.get("type"))["actions"]]
    bad = [a for a in body.actions if a not in allowed]
    if bad:
        raise ApiError(400, "bad_action", f"Unknown actions {bad}; allowed {allowed}")
    meta = _school_meta(school_id)
    card = _card(school_id, body.runId)
    now = utc_now()
    date = datetime.fromisoformat(card["date"]).strftime("%Y-%m-%d") if card.get("date") else now.astimezone(IST).strftime("%Y-%m-%d")
    sk = f"LOG#{date}#{body.runId}"
    existing = ddb.get_item(f"SCHOOL#{school_id}", sk) or {}
    message = _message(school_id, meta, card, body.actions)
    item = {"PK": f"SCHOOL#{school_id}", "SK": sk, "GSI1PK": f"DATE#{date}", "GSI1SK": f"SCHOOL#{school_id}",
            "runId": body.runId, "date": date, "dayTier": card["dayTier"], "actions": body.actions,
            "sentVia": body.sentVia or existing.get("sentVia"), "shownAt": existing.get("shownAt") or iso_z(now),
            "ackedAt": iso_z(now), "students": meta.get("students"),
            "people": meta.get("students") or meta.get("residents") or 0, "actorType": card.get("actorType", "school"),
            "outdoorHoursCancelled": card.get("outdoorHoursCancelled", 0) if ({"pt_indoors", "outdoor_off"} & set(body.actions)) else 0,
            "messageSource": message.get("source"), "messageHi": message.get("hi"), "messageEn": message.get("en")}
    ddb.put_item(item)
    if not ddb.enabled():
        storage().put_json(f"work/logs/{school_id}/{date}-{body.runId}.json", item)
    from protocol.assess import assess

    a = assess(card, body.actions, meta)
    act = records.append("act", school_id, {"runId": body.runId, "date": date, "actorType": card.get("actorType", "school"),
                                           "dayTier": card["dayTier"], "actions": body.actions, "sentVia": body.sentVia,
                                           "outdoorHoursCancelled": item["outdoorHoursCancelled"], "messageSource": message.get("source"),
                                           "assessment": {k: a.get(k) for k in ("coverage", "hoursAtRisk", "protectedHours", "exposedHours", "value", "unit", "cellsAtRisk", "cellsActioned") if a.get(k) is not None}},
                        card.get("actorType", "school"), body.runId, by=_by(who, meta))
    log.info("ack %s %s %s via %s", school_id, date, body.actions, body.sentVia)
    return {"ok": True, "log": {k: v for k, v in item.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK")}, "message": message, "record": act}


class EmailBody(BaseModel):
    runId: str


@router.post("/api/me/email")
def email(body: EmailBody, request: Request, response: Response):
    """SES fallback + audit trail (DESIGN.md §6.5). 501 until an SES sender is configured."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    meta = _school_meta(who["schoolId"])
    sender = secret("ses_sender")
    to = meta.get("email") or who.get("email")
    if not sender or not to:
        raise ApiError(501, "email_unavailable", "Email delivery is not configured (SES sender or school email missing).")
    card = _card(who["schoolId"], body.runId)
    message = _message(who["schoolId"], meta, card, card.get("defaultActions", []))
    from common.aws import client

    client("ses").send_email(Source=sender, Destination={"ToAddresses": [to]},
                             Message={"Subject": {"Data": f"{meta['name']}: air quality protocol for {card['date']}"},
                                      "Body": {"Text": {"Data": f"{message['hi']}\n\n{message['en']}\n\nrun {body.runId}"}}})
    return {"ok": True, "to": to}


# ------------------------------------------------------------------ decision records (§13.5)
@router.get("/api/records/{entity}")
def records_entity(entity: str, response: Response):
    """Public, contact-free decision log for one entity: forecast, advice, action, check, impact."""
    response.headers["Cache-Control"] = "public, max-age=60"
    recs = [records.public_view(r) for r in records.records_for(entity)]
    return {"entity": entity, "records": recs, "steps": records.STEPS, "labels": records.STEP_LABELS}


@router.get("/api/records")
def records_index(response: Response, date: str | None = None):
    """Every record of a date (default: today IST)."""
    response.headers["Cache-Control"] = "public, max-age=60"
    day = date or utc_now().astimezone(IST).strftime("%Y-%m-%d")
    recs = [records.public_view(r) for r in records.records_for_date(day)]
    return {"date": day, "records": recs}


@router.get("/api/verifier/pending")
def verifier_pending(request: Request, response: Response):
    """Verifier's queue: entity-days with a forecast and an act but no outcome yet."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "verifier", "auditor", "analyst")
    actors = (storage().get_json("static/actors.json") or {"entities": []})["entities"]
    queue = []
    for e in actors:
        by_date: dict[str, dict] = {}
        for r in records.records_for(e["id"]):
            by_date.setdefault(r.get("payload", {}).get("date") or r["date"], {})[r["kind"]] = r
        for d, kinds in sorted(by_date.items(), reverse=True):
            ver = kinds.get("verify")
            if "forecast" in kinds and (not ver or ver["payload"].get("outcome") == "pending"):
                queue.append({"entityId": e["id"], "name": e["name"], "type": e.get("type"), "date": d,
                              "dayTier": kinds["forecast"]["payload"].get("dayTier"), "acted": "act" in kinds,
                              "actions": (kinds.get("act") or {}).get("payload", {}).get("actions"),
                              "status": (ver or {}).get("payload", {}).get("outcome", "unverified"),
                              "reason": (ver or {}).get("payload", {}).get("reason")})
    return {"role": who["role"], "pending": queue[:200]}


class ConfirmBody(BaseModel):
    entityId: str
    date: str
    outcome: str = Field(pattern="^(confirmed|not_confirmed|missed|moot)$")
    evidence: str = ""
    observedPeakPm25: float | None = None


@router.post("/api/verifier/confirm")
def verifier_confirm(body: ConfirmBody, request: Request, response: Response):
    """A human verifier records an outcome with evidence (station reading, photo reference)."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "verifier")
    meta = _school_meta(body.entityId)
    rec = records.append("verify", body.entityId, {"date": body.date, "outcome": body.outcome, "method": "human verifier with evidence",
                                                  "evidence": body.evidence[:500], "observed": {"peakPm25": body.observedPeakPm25} if body.observedPeakPm25 is not None else None},
                        meta.get("type", "school"), by=_by(who))
    return {"ok": True, "record": rec}


# ------------------------------------------------------------------ the guided experience's decisions
class RegisterBody(BaseModel):
    entityId: str
    students: int | None = None
    residents: int | None = None
    machines: int | None = None
    hours: list[str] | None = None
    dismissal: list[str] | None = None
    hasPurifiers: bool | None = None


@router.post("/api/actors/register")
def register(body: RegisterBody, request: Request, response: Response):
    """Step 2: the operator registers (or confirms) their entity -> EntityRegistration record."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "operator")
    meta = _school_meta(body.entityId)
    existing = next((r for r in records.records_for(body.entityId) if r["kind"] == "enrol"), None)
    if existing:
        return {"ok": True, "record": existing, "existing": True}
    rec = records.append("enrol", body.entityId, {
        "type": meta.get("type", "school"), "name": meta["name"], "lat": meta["lat"], "lon": meta["lon"],
        "hours": body.hours or meta.get("hours"), "dismissal": body.dismissal or meta.get("dismissal"),
        "people": body.students or body.residents or body.machines or meta.get("students") or meta.get("residents") or meta.get("machines"),
        "hasPurifiers": body.hasPurifiers if body.hasPurifiers is not None else meta.get("hasPurifiers"),
        "verifiedBy": "pending verifier approval", "demo": bool(meta.get("demo"))}, meta.get("type", "school"),
        by=_by(who, meta))
    return {"ok": True, "record": rec, "existing": False}


@router.get("/api/verifier/inspect/{entity_id}")
def inspect(entity_id: str, request: Request, response: Response):
    """Step 3 checklist data: nearest station, NDVI change at the entity's cell, windows, registration."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "verifier", "auditor", "analyst")
    from records import verification

    meta = _school_meta(entity_id)
    station = verification.nearest_station(meta["lat"], meta["lon"])
    run_id = _latest_run_id()
    burning = storage().get_json(f"runs/{run_id}/burning.json") or {"features": []}
    import math

    nearest_cell = None
    best = 1e9
    for f in burning["features"]:
        ring = f["geometry"]["coordinates"][0]
        clat = sum(c[1] for c in ring[:4]) / 4
        clon = sum(c[0] for c in ring[:4]) / 4
        d = math.hypot((clat - meta["lat"]) * 111.32, (clon - meta["lon"]) * 111.32 * math.cos(math.radians(meta["lat"])))
        if d < best:
            best, nearest_cell = d, {**f["properties"], "distanceKm": round(d, 1)}
    recs = records.records_for(entity_id)
    enrol = next((r for r in recs if r["kind"] == "enrol"), None)
    approved = next((r for r in recs if r["kind"] == "verify" and r["payload"].get("subject") == "registration"), None)
    return {"entityId": entity_id, "name": meta["name"], "type": meta.get("type", "school"), "station": station,
            "nearestCell": nearest_cell, "hours": meta.get("hours"), "dismissal": meta.get("dismissal"),
            "registration": enrol, "approval": approved}


class ApproveBody(BaseModel):
    entityId: str
    checks: list[str] = Field(default_factory=list)
    note: str = ""


@router.post("/api/verifier/approve")
def approve(body: ApproveBody, request: Request, response: Response):
    """Step 3: the verifier approves a registration -> OutcomeVerification(subject=registration)."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "verifier")
    meta = _school_meta(body.entityId)
    rec = records.append("verify", body.entityId, {"subject": "registration", "outcome": "approved", "checks": body.checks[:10],
                                                  "note": body.note[:300], "method": "verifier checklist"},
                        meta.get("type", "school"), by=_by(who))
    return {"ok": True, "record": rec}


class PlanBody(BaseModel):
    runId: str
    cells: list[dict] = Field(default_factory=list)
    hoursToProtect: list[dict] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    weather: dict | None = None


@router.post("/api/actors/{school_id}/plan")
def plan(school_id: str, body: PlanBody, request: Request, response: Response):
    """Step 4: the plan - treatment cells and hours to protect - as an Advisory(subject=plan)."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "operator")
    if not _may_act_for(who, school_id):
        raise ApiError(403, "forbidden", "This login belongs to a different entity and did not register this one.")
    meta = _school_meta(school_id)
    card = _card(school_id, body.runId)
    rec = records.append("advise", school_id, {"subject": "plan", "runId": body.runId, "date": card.get("date"),
                                              "cells": [{k: c.get(k) for k in ("name", "score", "category", "i", "j")} for c in body.cells[:8]],
                                              "hoursToProtect": body.hoursToProtect[:8], "actions": body.actions[:8], "weather": body.weather,
                                              "dayTier": card.get("dayTier")}, meta.get("type", "school"), body.runId,
                        by=_by(who, meta))
    return {"ok": True, "record": rec}


@router.get("/api/verifier/observe/{entity_id}")
def observe(entity_id: str, request: Request, response: Response, date: str | None = None):
    """Step 6 data: observed hours at the nearest station for the card's date, and the assessment, without writing."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "verifier", "auditor", "analyst")
    from records import verification

    meta = _school_meta(entity_id)
    run_id = _latest_run_id()
    card = _card(entity_id, run_id)
    day = date or card.get("date")
    station = verification.nearest_station(meta["lat"], meta["lon"])
    if not station:
        return {"entityId": entity_id, "date": day, "station": None, "outcome": "no_station", "hoursObserved": 0}
    hours = verification.observed_hours_openaq(station["id"], day) if day else None
    if hours is None:
        return {"entityId": entity_id, "date": day, "station": station, "outcome": "pending", "hoursObserved": 0,
                "reason": "observations not published yet (archive lags ~4 days; next-day with the CPCB key)", "forecast": {"tier": card.get("dayTier"), "peakAqi": card.get("peakAqi")}}
    windows = [card.get("schoolHoursIst") or ["08:00", "14:00"], card.get("dismissalIst") or ["15:00", "16:00"]]
    return {"entityId": entity_id, "date": day, "station": station, "hoursObserved": len(hours), **verification.assess(card, hours, windows)}


class AccountBody(BaseModel):
    entityId: str
    date: str


@router.post("/api/records/account")
def account(body: AccountBody, request: Request, response: Response):
    """Step 7: issue the impact statement for an entity-day now."""
    response.headers["Cache-Control"] = "private, no-store"
    who = principal(request)
    require_role(who, "auditor", "analyst")
    from records.daily import account_entity_day

    rec = account_entity_day(body.entityId, body.date, by=_by(who))
    if not rec:
        raise ApiError(404, "no_forecast", "No forecast record for that entity and date.")
    return {"ok": True, "record": rec}

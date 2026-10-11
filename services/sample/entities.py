"""Cards for every onboarded or demo entity of every actor type (DESIGN.md §6.6), plus the
decision records a run produces: one `forecast` and one `advise` per entity. Schools also keep
their map-layer path in sample/schools.py."""
from __future__ import annotations

import logging
import math
from datetime import datetime

from common import aqi, domain
from common.timeutil import IST, iso_z
from forecast.run import RunResult
from forecast.wind import background_points
from notify import fallback
from protocol import interval, rules
from protocol.actors import actor_type
from records import store as records

log = logging.getLogger(__name__)


def _exposure_card(result: RunResult, aq_json: dict, k: float | None, e: dict,
                   calibration: dict | None = None) -> dict:
    i_lat, i_lon = domain.cell_index(e["lat"], e["lon"])
    raw = result.raw[:, i_lat, i_lon]
    bg = background_points(aq_json, [e["lat"]], [e["lon"]], result.hours)[:, 0]
    hourly = []
    for h, t in enumerate(result.hours):
        row = {"t": iso_z(t), "pm25Background": round(float(bg[h]), 1)}
        if k is not None:
            fire = float(raw[h] * k)
            total = float(bg[h]) + fire
            a = aqi.pm25_subindex(total)
            row.update({"pm25Fire": round(fire, 1), "pm25Total": round(total, 1), "aqi": a, "tier": aqi.tier_for_aqi(a).id})
            interval.attach_band(row, total, calibration, h)
        hourly.append(row)
    hours = tuple(e.get("hours") or domain.SCHOOL_HOURS_IST)
    dismissal = tuple(e.get("dismissal") or domain.DISMISSAL_IST)
    card = rules.build_card(hourly, school_hours=hours, dismissal=dismissal, has_purifiers=bool(e.get("hasPurifiers")),
                            actor=e["type"]) if k is not None else {"actorType": e["type"], "kind": "exposure", "date": None, "dayTier": None,
                                                                      "windows": [], "protocol": None, "headline": "Forecast not yet calibrated.",
                                                                      "defaultActions": [], "actions": actor_type(e["type"])["actions"], "peakAqi": None,
                                                                      "outdoorHoursCancelled": 0.0, "schoolHoursIst": list(hours), "dismissalIst": list(dismissal)}
    card["hourly"] = hourly
    interval.attach_card_extras(card, hourly, hours, dismissal)
    if card.get("dayTier"):
        card["message"] = fallback.render(e["name"], card["date"], card["dayTier"], card["windows"], card["peakAqi"], card["dismissalIst"], e["type"])
    return card


def _source_card(burning: dict, e: dict, now: datetime) -> dict:
    lat, lon, r = e["lat"], e["lon"], float(e.get("radiusKm") or 40)
    cells = []
    for f in burning.get("features", []):
        p = f["properties"]
        ring = f["geometry"]["coordinates"][0]
        clat = sum(c[1] for c in ring[:4]) / 4
        clon = sum(c[0] for c in ring[:4]) / 4
        d = math.hypot((clat - lat) * 111.32, (clon - lon) * 111.32 * math.cos(math.radians(lat)))
        if d <= r:
            cells.append({**{k2: p[k2] for k2 in ("i", "j", "name", "fires24", "fires48", "frp24", "trend", "ndviChange", "rain48mm", "score", "category")},
                          "lat": round(clat, 3), "lon": round(clon, 3), "distanceKm": round(d, 1)})
    date_ist = now.astimezone(IST).strftime("%Y-%m-%d")
    card = rules.build_source_card(cells, date_ist, e.get("district") or e["name"])
    card["hourly"] = []
    card["message"] = fallback.render_source(e["name"], date_ist, card)
    return card


def entity_cards(result: RunResult, aq_json: dict, k: float | None, actors: dict, burning: dict, now: datetime,
                 calibration: dict | None = None) -> dict[str, dict]:
    """entity id -> public card (contact-free) for every entity in static/actors.json."""
    cards: dict[str, dict] = {}
    for e in actors.get("entities", []):
        if not bool(domain.in_domain(e["lat"], e["lon"])):
            continue
        at = actor_type(e.get("type"))
        card = _source_card(burning, e, now) if at["kind"] == "source" else _exposure_card(result, aq_json, k, e, calibration)
        card.update({"schoolId": e["id"], "entityId": e["id"], "name": e["name"], "name_hi": e.get("name_hi"), "runId": result.run_id,
                     "demo": bool(e.get("demo")), "onboarded": bool(e.get("onboarded")), "persona": e.get("persona"),
                     "actorLabel": at["label"], "personTitle": at["personTitle"], "impactUnit": at["impactUnit"], "audience": at["audience"],
                     "people": e.get(at["peopleField"]), "calibration": calibration})
        cards[e["id"]] = card
    return cards


def workflow_records(result: RunResult, cards: dict[str, dict], inputs: dict, store, k: float | None) -> int:
    """forecast + advise per entity. Returns the number of records written."""
    rid = result.run_id
    n = 0
    for eid, c in cards.items():
        records.append("forecast", eid, {
            "runId": rid, "date": c.get("date"), "actorType": c["actorType"], "kind": c["kind"], "dayTier": c.get("dayTier"),
            "peakAqi": c.get("peakAqi"), "windows": c.get("windows"), "headline": c.get("headline"),
            "outdoorHoursCancelled": c.get("outdoorHoursCancelled"), "cells": [{k2: x[k2] for k2 in ("name", "score", "category")} for x in c.get("cells", [])][:8],
            "schoolHoursIst": c.get("schoolHoursIst"), "dismissalIst": c.get("dismissalIst"),
            "inputs": {"fires": len(result.fires), "weather": (inputs.get("weather") or {}).get("id"), "k": k, "seed": result.params.seed},
        }, c["actorType"], rid, store=store)
        n += 1
        if c.get("message"):
            records.append("advise", eid, {"runId": rid, "date": c.get("date"), "actorType": c["actorType"], "source": c["message"]["source"],
                                           "chars": c["message"]["chars"], "audience": actor_type(c["actorType"])["audience"]}, c["actorType"], rid, store=store)
            n += 1
    return n

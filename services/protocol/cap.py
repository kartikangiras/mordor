"""Advisories as OASIS Common Alerting Protocol 1.2 (DESIGN.md §6.5).

CAP is the international standard behind FEMA IPAWS, EPA's air-quality alerts and the UN's
"Early Warnings for All", so emitting it means a Directorate of Education, the CAQM or any
standard alerting pipeline can ingest a mordor advisory without adopting our JSON. Everything
below is already computed for the card; this is a projection, not a new claim.

**`status` defaults to `Exercise`, deliberately.** CAP `Actual` asserts a real public warning
from an authorised body. mordor is not one, and a non-authority emitting `Actual` is exactly
how an unofficial feed gets mistaken for an official one. A real deployment behind a DoE or
CAQM sender sets `status="Actual"` explicitly; nothing here does it by default.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

from common.aqi import TIERS
from common.timeutil import IST

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"

#: Tier -> (CAP severity, CAP urgency, CAP responseType). CAP severity is about the hazard,
#: so it tracks the GRAP stage the tier is anchored to rather than our own label.
TIER_CAP = {
    "T0": ("Minor", "Future", "None"),
    "T1": ("Moderate", "Expected", "Prepare"),
    "T2": ("Severe", "Expected", "Shelter"),
    "T3": ("Severe", "Immediate", "Shelter"),
    "T4": ("Extreme", "Immediate", "Shelter"),
}

#: We forecast rather than observe, so certainty is never `Observed`.
CERTAINTY = "Likely"


def _tier_label(tier: str | None) -> str:
    for t in TIERS:
        if t.id == tier:
            return t.label
    return "Normal"


def _ist(dt: datetime) -> str:
    """CAP 1.2 requires a numeric timezone offset with a colon, and forbids 'Z'."""
    s = dt.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{s[:-2]}:{s[-2:]}"


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, tag)
    if text is not None:
        el.text = str(text)
    return el


def _param(info: ET.Element, name: str, value) -> None:
    if value is None:
        return
    p = _sub(info, "parameter")
    _sub(p, "valueName", name)
    _sub(p, "value", value)


def _window_text(card: dict) -> str:
    bad = [w for w in card.get("windows") or [] if w.get("tier") in ("T2", "T3", "T4")]
    if not bad:
        return "No window above the Caution tier during hours of concern."
    parts = []
    for w in bad:
        peak = f", peak AQI {w['peakAqi']}" if w.get("peakAqi") is not None else ""
        parts.append(f"{w['fromIst']}-{w['toIst']} IST {_tier_label(w['tier'])}{peak}")
    return "; ".join(parts)


def build(card: dict, entity: dict, run_id: str, sent: datetime,
          sender: str = "mordor@localhost", sender_name: str = "mordor (unofficial forecast)",
          status: str = "Exercise", msg_type: str = "Alert",
          message: dict | None = None) -> ET.Element:
    """One CAP 1.2 `<alert>` for one entity's card, with an English and a Hindi `<info>`."""
    tier = card.get("dayTier") or "T0"
    severity, urgency, response = TIER_CAP.get(tier, TIER_CAP["T0"])
    alert = ET.Element("alert", {"xmlns": CAP_NS})
    _sub(alert, "identifier", f"mordor.{entity.get('id', 'unknown')}.{run_id}")
    _sub(alert, "sender", sender)
    _sub(alert, "sent", _ist(sent))
    _sub(alert, "status", status)
    _sub(alert, "msgType", msg_type)
    _sub(alert, "scope", "Public")

    windows = card.get("windows") or []
    onset = windows[0]["fromIst"] if windows else None
    interval = card.get("interval") or {}
    dose = card.get("dose") or {}

    for lang, headline, desc in (
        ("en-IN", card.get("headline") or "", (message or {}).get("en") or ""),
        ("hi-IN", card.get("headline") or "", (message or {}).get("hi") or ""),
    ):
        if lang == "hi-IN" and not desc:
            continue                      # no Hindi text available: omit rather than pad
        info = _sub(alert, "info")
        _sub(info, "language", lang)
        _sub(info, "category", "Health")
        _sub(info, "category", "Env")
        _sub(info, "event", "Air quality advisory (stubble-smoke PM2.5)")
        _sub(info, "responseType", response)
        _sub(info, "urgency", urgency)
        _sub(info, "severity", severity)
        _sub(info, "certainty", CERTAINTY)
        if card.get("date"):
            _sub(info, "onset", _ist(datetime.fromisoformat(
                f"{card['date']}T{onset or '08:00'}:00+05:30")))
            _sub(info, "expires", _ist(datetime.fromisoformat(
                f"{card['date']}T00:00:00+05:30") + timedelta(days=1)))
        _sub(info, "senderName", sender_name)
        _sub(info, "headline", headline[:160])
        _sub(info, "description", desc or headline)
        instruction = "; ".join(card.get("defaultActions") or []) or \
            "No action required beyond normal routine."
        _sub(info, "instruction", instruction)

        _param(info, "mordor:runId", run_id)
        _param(info, "mordor:tier", f"{tier} {_tier_label(tier)}")
        _param(info, "mordor:grapAnchor", (card.get("protocol") or {}).get("grapAnchor"))
        _param(info, "mordor:peakAqi", card.get("peakAqi"))
        if interval:
            _param(info, "mordor:peakAqiRange", f"{interval.get('aqiLo')}-{interval.get('aqiHi')}")
            _param(info, "mordor:intervalBasis", interval.get("basis"))
        if dose:
            _param(info, "mordor:inhaledDoseUg", dose.get("totalUg"))
            _param(info, "mordor:worstHourIst", (dose.get("worstHour") or {}).get("hourIst"))
        _param(info, "mordor:windows", _window_text(card))
        _param(info, "mordor:calibration",
               f"k={(card.get('calibration') or {}).get('k')} "
               f"window={(card.get('calibration') or {}).get('window')}")
        _param(info, "mordor:disclaimer",
               "Forecast from a simplified transport model, not an official government "
               "advisory and not for medical decisions.")

        area = _sub(info, "area")
        _sub(area, "areaDesc", entity.get("name") or entity.get("id") or "unknown")
        lat, lon = entity.get("lat"), entity.get("lon")
        if lat is not None and lon is not None:
            _sub(area, "circle", f"{float(lat):.4f},{float(lon):.4f} 2")
    return alert


def to_xml(card: dict, entity: dict, run_id: str, sent: datetime, **kw) -> str:
    alert = build(card, entity, run_id, sent, **kw)
    ET.indent(alert, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(alert, encoding="unicode")

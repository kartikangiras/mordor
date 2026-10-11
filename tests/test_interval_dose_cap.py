"""Tier-1 card additions: conformal intervals, inhaled dose, CAP 1.2 output."""
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from protocol import cap, interval

CAL = {"conformal": {"q80": 120.0, "q90": 170.0, "n": 42407},
       "conformalByLead": {"lead01_24": {"q90": 150.0}, "lead25_48": {"q90": 190.0}}}


# ---------------------------------------------------------------- intervals
def test_half_width_widens_with_lead_and_falls_back_to_the_pooled_quantile():
    assert interval.half_width(CAL, 1) == 150.0
    assert interval.half_width(CAL, 24) == 150.0
    assert interval.half_width(CAL, 25) == 190.0
    assert interval.half_width({"conformal": {"q90": 170.0}}, 6) == 170.0
    assert interval.half_width(CAL, 6, level="q80") == 120.0   # per-lead lacks q80 -> pooled


def test_no_calibration_means_no_interval_rather_than_a_guess():
    assert interval.half_width(None, 6) is None
    assert interval.half_width({}, 6) is None
    assert interval.pm25_band(200.0, None) is None
    assert interval.aqi_band(200.0, None) is None


def test_band_is_clipped_at_zero_and_maps_to_sub_index():
    assert interval.pm25_band(50.0, 170.0) == (0.0, 220.0)
    lo, hi = interval.aqi_band(200.0, 150.0)
    assert lo < hi and lo >= 0


def test_conformal_quantile_covers_at_the_stated_rate(hindcast):
    """The point of split-conformal: ~90% of held-out residuals inside the half-width."""
    conformal = hindcast.conformal

    rng = np.random.default_rng(7)
    obs = rng.normal(200, 80, 5000)
    pred = obs + rng.normal(0, 60, 5000)
    out = conformal(pred, obs)
    covered = np.mean(np.abs(obs - pred) <= out["q90"])
    assert 0.88 <= covered <= 0.93
    assert out["q80"] < out["q90"]
    assert out["n"] == 5000


def test_conformal_refuses_on_too_few_rows(hindcast):
    out = hindcast.conformal(np.zeros(5), np.zeros(5))
    assert "q90" not in out and "insufficient" in out["basis"]


# ---------------------------------------------------------------- dose
def _day(pm25_by_hour, school=("08:00", "14:00"), dismissal=("15:00", "16:00")):
    rows = []
    for h, pm in pm25_by_hour.items():
        rows.append({"pm25": pm, "hourIst": f"{h:02d}:00",
                     "inSchool": 8 <= h < 14, "inDismissal": 15 <= h < 16})
    return rows


def test_dose_is_concentration_times_breathing_rate_times_hours():
    rows = _day({h: 100.0 for h in range(24)})
    d = interval.dose_for_day(rows)
    # 6 school hours at light (0.60) + 1 dismissal hour at moderate (1.20)
    assert d["schoolHoursUg"] == pytest.approx(6 * 100 * 0.60, rel=1e-6)
    assert d["dismissalUg"] == pytest.approx(1 * 100 * 1.20, rel=1e-6)
    assert d["totalUg"] == pytest.approx(d["schoolHoursUg"] + d["dismissalUg"], rel=1e-6)
    assert d["hours"] == 7


def test_dismissal_hour_can_dominate_despite_being_one_hour():
    """The whole reason to use dose: one moderate-activity hour outweighs two sitting still."""
    rows = _day({h: (100.0 if h != 15 else 400.0) for h in range(24)})
    d = interval.dose_for_day(rows)
    assert d["worstHour"]["hourIst"] == "15:00"
    assert d["worstHour"]["activity"] == "moderate"
    assert d["dismissalShare"] > 0.5


def test_dose_only_counts_hours_the_card_covers():
    rows = [{"pm25": 999.0, "hourIst": "03:00", "inSchool": False, "inDismissal": False}]
    assert interval.dose_for_day(rows) is None          # nothing claimable
    assert interval.dose_for_day([]) is None


def test_dose_publishes_its_own_assumptions():
    d = interval.dose_for_day(_day({h: 50.0 for h in range(24)}))
    assert d["breathingRatesM3PerH"] == interval.ACTIVITY
    assert "no indoor infiltration" in d["basis"]
    assert "not a health outcome" in d["basis"]


# ---------------------------------------------------------------- CAP
CARD = {"dayTier": "T3", "date": "2026-10-08", "headline": "Very Poor from 11:00",
        "windows": [{"fromIst": "11:00", "toIst": "15:00", "tier": "T3", "peakAqi": 412}],
        "protocol": {"grapAnchor": "Stage III (Severe)"}, "peakAqi": 412,
        "defaultActions": ["Move games indoors"],
        "interval": {"aqiLo": 180, "aqiHi": 500, "basis": "split-conformal 90%"},
        "dose": {"totalUg": 1008.0, "worstHour": {"hourIst": "13:00"}},
        "calibration": {"k": 4.79e11, "window": "2025-11-01..2025-11-20"}}
ENT = {"id": "osm-way-1", "name": "Demo School", "lat": 28.61, "lon": 77.21}
SENT = datetime(2026, 10, 7, 2, 30, tzinfo=timezone.utc)


def _parse(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def _t(el, path):
    return el.findtext(f"{{{cap.CAP_NS}}}{path}")


def test_cap_is_well_formed_and_in_the_cap_1_2_namespace():
    root = _parse(cap.to_xml(CARD, ENT, "run1", SENT))
    assert root.tag == f"{{{cap.CAP_NS}}}alert"
    for required in ("identifier", "sender", "sent", "status", "msgType", "scope"):
        assert _t(root, required), required


def test_status_is_exercise_because_we_are_not_an_alerting_authority():
    root = _parse(cap.to_xml(CARD, ENT, "run1", SENT))
    assert _t(root, "status") == "Exercise"
    # and an operator can still opt in explicitly
    root2 = _parse(cap.to_xml(CARD, ENT, "run1", SENT, status="Actual"))
    assert _t(root2, "status") == "Actual"


def test_timestamps_carry_an_offset_and_never_use_z():
    xml = cap.to_xml(CARD, ENT, "run1", SENT)
    assert "+05:30" in xml and "Z<" not in xml
    assert _t(_parse(xml), "sent") == "2026-10-07T08:00:00+05:30"


def test_tier_maps_to_cap_severity_urgency_and_response():
    info_ns = f"{{{cap.CAP_NS}}}"
    for tier, (sev, urg, resp) in cap.TIER_CAP.items():
        root = _parse(cap.to_xml({**CARD, "dayTier": tier}, ENT, "r", SENT))
        info = root.find(f"{info_ns}info")
        assert info.findtext(f"{info_ns}severity") == sev
        assert info.findtext(f"{info_ns}urgency") == urg
        assert info.findtext(f"{info_ns}responseType") == resp


def test_certainty_is_never_observed_because_we_forecast():
    root = _parse(cap.to_xml(CARD, ENT, "r", SENT))
    info = root.find(f"{{{cap.CAP_NS}}}info")
    assert info.findtext(f"{{{cap.CAP_NS}}}certainty") == "Likely"


def test_hindi_info_block_appears_only_when_there_is_hindi_text():
    ns = f"{{{cap.CAP_NS}}}"
    none = _parse(cap.to_xml(CARD, ENT, "r", SENT))
    assert len(none.findall(f"{ns}info")) == 1
    both = _parse(cap.to_xml(CARD, ENT, "r", SENT,
                             message={"en": "English text", "hi": "हिंदी पाठ"}))
    langs = [i.findtext(f"{ns}language") for i in both.findall(f"{ns}info")]
    assert langs == ["en-IN", "hi-IN"]


def test_area_circle_and_the_interval_and_dose_parameters_are_carried():
    ns = f"{{{cap.CAP_NS}}}"
    root = _parse(cap.to_xml(CARD, ENT, "run1", SENT))
    info = root.find(f"{ns}info")
    assert info.find(f"{ns}area/{ns}circle").text.startswith("28.6100,77.2100 ")
    params = {p.findtext(f"{ns}valueName"): p.findtext(f"{ns}value")
              for p in info.findall(f"{ns}parameter")}
    assert params["mordor:peakAqiRange"] == "180-500"
    assert params["mordor:inhaledDoseUg"] == "1008.0"
    assert params["mordor:worstHourIst"] == "13:00"
    assert params["mordor:grapAnchor"] == "Stage III (Severe)"
    assert "not an official government" in params["mordor:disclaimer"]


def test_windows_parameter_lists_each_bad_span_with_its_peak():
    ns = f"{{{cap.CAP_NS}}}"
    card = {**CARD, "windows": [{"fromIst": "11:00", "toIst": "15:00", "tier": "T3", "peakAqi": 412},
                                {"fromIst": "15:00", "toIst": "16:00", "tier": "T2", "peakAqi": 350},
                                {"fromIst": "07:00", "toIst": "08:00", "tier": "T1", "peakAqi": 210}]}
    info = _parse(cap.to_xml(card, ENT, "r", SENT)).find(f"{ns}info")
    params = {p.findtext(f"{ns}valueName"): p.findtext(f"{ns}value")
              for p in info.findall(f"{ns}parameter")}
    w = params["mordor:windows"]
    assert "11:00-15:00 IST Restrict, peak AQI 412" in w
    assert "15:00-16:00 IST Indoors, peak AQI 350" in w
    assert "07:00" not in w                      # T1 is not a window of concern


def test_cap_route_sets_exactly_one_media_type(tmp_path, monkeypatch):
    """CAP consumers sniff Content-Type; a doubled value (text/plain,application/cap+xml) is a bug."""
    from fastapi.testclient import TestClient

    import common.storage as storage_mod
    from api.handler import app
    from common.storage import LocalStorage

    store = LocalStorage(tmp_path)
    store.put_json("runs/latest.json", {"runId": "r1", "generatedAt": "2026-10-07T01:00:00Z"})
    store.put_json("runs/r1/protocol/e1.json", {**CARD, "school": {"name": "Demo"}})
    store.put_json("runs/r1/schools.json", {"features": []})
    monkeypatch.setattr(storage_mod, "storage", lambda: store)
    import api.routes.public as pub
    monkeypatch.setattr(pub, "storage", lambda: store)
    r = TestClient(app).get("/api/cap/e1")
    assert r.status_code == 200
    assert r.headers["content-type"].count("application/cap+xml") == 1
    assert "text/plain" not in r.headers["content-type"]
    assert r.text.startswith('<?xml') and "<alert" in r.text

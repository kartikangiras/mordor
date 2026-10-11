"""PIVOT_PLAN.md D9: the walkthrough registers any mapped school, and the login that registered
it may then act for it; another operator may not."""
from fastapi.testclient import TestClient

CARD = {"date": "2026-10-11", "dayTier": "T2", "actorType": "school", "kind": "exposure", "peakAqi": 320,
        "windows": [{"fromIst": "10:00", "toIst": "16:00", "tier": "T2", "peakAqi": 320}], "defaultActions": ["pt_indoors", "windows_shut"],
        "schoolHoursIst": ["08:00", "14:00"], "dismissalIst": ["15:00", "16:00"], "hasPurifiers": False, "headline": "Very poor from 10", "hourly": []}


def _client(tmp_path, monkeypatch):
    import api.routes.principal as pr
    import common.storage as storage_mod
    import records.store as rs
    from api.handler import app
    from common.storage import LocalStorage

    store = LocalStorage(tmp_path)
    store.put_json("runs/latest.json", {"runId": "r1", "generatedAt": "2026-10-10T01:00:00Z"})
    store.put_json("static/schools.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [77.1, 28.7]}, "properties": {"id": "osm-2", "name": "Some School", "named": True}}]})
    store.put_json("work/r1/cards/osm-2.json", CARD)
    monkeypatch.setattr(storage_mod, "storage", lambda: store)
    monkeypatch.setattr(pr, "storage", lambda: store)
    monkeypatch.setattr(rs, "storage", lambda: store)
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    monkeypatch.delenv("NOTIFY_FUNCTION", raising=False)
    monkeypatch.setenv("NOTIFY_USE_AGENT", "0")
    return TestClient(app)


ANITA = {"X-Dev-Role": "operator", "X-Dev-School-Id": "osm-1"}
OTHER = {"X-Dev-Role": "operator", "X-Dev-School-Id": "osm-9"}


def test_registered_school_can_be_acted_for_by_its_registrar_only(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    # nobody registered osm-2 yet: neither operator may act for it
    assert c.post("/api/actors/osm-2/ack", json={"runId": "r1", "actions": ["pt_indoors"], "sentVia": "noted"}, headers=ANITA).status_code == 403
    r = c.post("/api/actors/register", json={"entityId": "osm-2"}, headers=ANITA)
    assert r.status_code == 200 and r.json()["existing"] is False and r.json()["record"]["kind"] == "enrol"
    # the registrar may read the card and act for it; another operator may not
    fc = c.get("/api/me/forecast?entity=osm-2", headers=ANITA)
    assert fc.status_code == 200 and fc.json()["school"]["id"] == "osm-2" and fc.json()["dayTier"] == "T2"
    ack = c.post("/api/actors/osm-2/ack", json={"runId": "r1", "actions": ["pt_indoors"], "sentVia": "noted"}, headers=ANITA)
    assert ack.status_code == 200 and ack.json()["record"]["kind"] == "act" and ack.json()["log"]["sentVia"] == "noted"
    assert c.post("/api/actors/osm-2/ack", json={"runId": "r1", "actions": ["pt_indoors"], "sentVia": "noted"}, headers=OTHER).status_code == 403
    assert c.get("/api/me/forecast?entity=osm-2", headers=OTHER).status_code == 403
    # a login with no entity and no ?entity= is told so, not served a 404 for "None"
    assert c.get("/api/me/forecast", headers={"X-Dev-Role": "operator"}).status_code == 400


def test_persona_comes_from_the_login_not_the_entity(tmp_path, monkeypatch):
    from protocol.actors import persona_for_email
    assert persona_for_email("anita.demo@example.com") == "Anita" and persona_for_email("ANITA.demo@example.com") == "Anita"
    assert persona_for_email("someone@school.in") is None and persona_for_email(None) is None
    c = _client(tmp_path, monkeypatch)
    # a header (dev) login carries no persona of its own, and the school it registers has none either
    r = c.post("/api/actors/register", json={"entityId": "osm-2"}, headers=ANITA)
    assert r.json()["record"]["by"] == {"role": "operator", "sub": "dev:operator:osm-1", "persona": None}


def test_public_card_for_any_mapped_school(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    import api.routes.public as pub
    import common.storage as storage_mod
    monkeypatch.setattr(pub, "storage", storage_mod.storage)
    r = c.get("/api/schools/osm-2/card")
    assert r.status_code == 200
    j = r.json()
    assert j["schoolId"] == "osm-2" and j["name"] == "Some School" and j["dayTier"] == "T2" and j["message"]["hi"].startswith(("🌫", "🌤"))
    assert "email" not in j and "phone" not in j
    assert c.get("/api/schools/nope/card").status_code == 404


def test_public_guidelines_are_served_and_never_build_a_card(tmp_path, monkeypatch):
    from protocol.actors import ACTOR_TYPES, PUBLIC_GUIDELINES
    assert set(PUBLIC_GUIDELINES) == {"T0", "T1", "T2", "T3", "T4"} and "PUBLIC" not in ACTOR_TYPES
    for tier, g in PUBLIC_GUIDELINES.items():
        assert {"title", "outdoor", "windows", "masks", "vulnerable", "grapAnchor"} <= set(g), tier
    c = _client(tmp_path, monkeypatch)
    r = c.get("/api/guidelines")
    assert r.status_code == 200 and r.json()["tiers"]["T4"]["title"] == "Stay indoors" and r.headers["cache-control"].startswith("public")


def test_hospital_actor_type_builds_a_card_and_a_message():
    from notify import fallback, validate
    from protocol import rules
    from protocol.actors import ACTOR_TYPES, actor_type
    assert actor_type("hospital")["kind"] == "exposure" and actor_type("hospital")["peopleField"] == "beds" and "hospital" in ACTOR_TYPES
    hourly = [{"t": f"2026-10-11T{h:02d}:30:00Z", "pm25Background": 80.0, "pm25Fire": 120.0, "pm25Total": 200.0, "aqi": 330, "tier": "T2"} for h in range(0, 24)]
    card = rules.build_card(hourly, school_hours=("06:00", "14:00"), dismissal=("14:00", "22:00"), actor="hospital")
    assert card["actorType"] == "hospital" and card["dayTier"] in ("T2", "T3") and "wards" in card["protocol"] and "alert_wards" in card["defaultActions"]
    assert "ward" in card["headline"].lower()
    m = fallback.render("District Hospital, Rohini", card["date"], card["dayTier"], card["windows"], card["peakAqi"], card["dismissalIst"], "hospital")
    ok, reasons = validate.check(m, "hospital")
    assert ok, reasons
    assert not validate.check(m)[0]   # the same words are still banned for parents
    assert "ward" in m["en"].lower() and "school" not in m["en"].lower()


def test_assessment_changes_with_the_actions_chosen():
    from protocol.assess import assess, fallback_text
    from records.accounting import impact
    card = {"actorType": "school", "kind": "exposure", "date": "2026-10-11", "dayTier": "T2", "peakAqi": 320, "outdoorHoursCancelled": 6.0, "windows": []}
    meta = {"type": "school", "students": 1200}
    none = assess(card, [], meta)
    some = assess(card, ["masks"], meta)
    full = assess(card, ["pt_indoors", "windows_shut", "masks", "assembly_indoor"], meta)
    assert none["coverage"] == 0 and none["protectedHours"] == 0 and none["value"] == 0 and none["missing"][0]["id"] == "pt_indoors"
    assert some["coverage"] == 0.2 and some["protectedHours"] == 1.2 and some["value"] == 1440.0 and some["exposedHours"] == 4.8
    assert full["coverage"] == 1.0 and full["protectedHours"] == 6.0 and full["value"] == 7200.0 and full["missing"] == []
    # the impact statement follows the same arithmetic
    assert impact(card, {"actions": ["masks"]}, {"outcome": "confirmed"}, meta)["value"] == 1440.0
    assert impact(card, {"actions": []}, {"outcome": "confirmed"}, meta)["status"] == "provisional"
    # a calm day protects nothing, and the words say so
    calm = assess({**card, "dayTier": "T0", "outdoorHoursCancelled": 0.0}, ["pt_indoors"], meta)
    assert calm["value"] == 0 and "protect nothing today" in fallback_text(calm, "KV")
    hosp = assess({"actorType": "hospital", "kind": "exposure", "dayTier": "T3", "outdoorHoursCancelled": 8.0}, ["alert_wards", "beds_ready"], {"beds": 40})
    assert hosp["coverage"] == 0.6 and hosp["unit"] == "ready bed-hours" and hosp["value"] == 192.0


def test_assess_route_returns_numbers_and_words(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    c.post("/api/actors/register", json={"entityId": "osm-2"}, headers=ANITA)
    r = c.post("/api/actors/osm-2/assess", json={"runId": "r1", "actions": ["pt_indoors"]}, headers=ANITA)
    assert r.status_code == 200
    j = r.json()
    assert j["coverage"] == 0.5 and j["unit"] == "protected student-hours" and j["narrative"]["source"] == "template" and "Some School" in j["narrative"]["en"]
    assert c.post("/api/actors/osm-2/assess", json={"runId": "r1", "actions": []}, headers=OTHER).status_code == 403
    ack = c.post("/api/actors/osm-2/ack", json={"runId": "r1", "actions": ["pt_indoors", "masks"], "sentVia": "noted"}, headers=ANITA).json()
    assert ack["record"]["payload"]["assessment"]["coverage"] == 0.7

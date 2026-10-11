from datetime import datetime, timezone

from common.storage import LocalStorage
from records import accounting, store


def test_append_orders_by_seq(tmp_path, monkeypatch):
    monkeypatch.delenv("TABLE_NAME", raising=False)
    s = LocalStorage(tmp_path)
    t0 = datetime(2026, 10, 5, 1, tzinfo=timezone.utc)
    a = store.append("forecast", "e1", {"date": "2026-10-05", "dayTier": "T2"}, "school", "r1", store=s, ts=t0)
    b = store.append("act", "e1", {"date": "2026-10-05", "actions": ["pt_indoors"]}, "school", "r1", store=s, ts=t0.replace(hour=2))
    assert (a["seq"], b["seq"]) == (1, 2) and a["id"] == "e1:1"
    recs = store.records_for("e1", s)
    assert [r["kind"] for r in recs] == ["forecast", "act"]
    assert [r["kind"] for r in store.records_for_date("2026-10-05", s)] == ["forecast", "act"]
    assert "hash" not in a and "prevHash" not in a


def test_accounting_credits_only_confirmed_days():
    card = {"actorType": "school", "kind": "exposure", "outdoorHoursCancelled": 4.0}
    meta = {"students": 1200}
    # coverage-weighted (protocol/assess.py): PT indoors alone addresses half the hours at risk, the full set all of them
    v = accounting.impact(card, {"actions": ["pt_indoors"]}, {"outcome": "confirmed"}, meta)
    assert v["value"] == 2400 and v["coverage"] == 0.5 and v["status"] == "verified" and v["unit"] == "protected student-hours"
    assert accounting.impact(card, {"actions": ["pt_indoors", "windows_shut", "masks", "assembly_indoor"]}, {"outcome": "confirmed"}, meta)["value"] == 4800
    assert accounting.impact(card, {"actions": ["pt_indoors"]}, {"outcome": "not_confirmed"}, meta)["status"] == "not_credited"
    assert accounting.impact(card, {"actions": ["pt_indoors"]}, {"outcome": "pending"}, meta)["status"] == "provisional"
    rwa = accounting.impact({"actorType": "rwa", "kind": "exposure", "outdoorHoursCancelled": 3.0}, {"actions": ["outdoor_off", "gensets_off", "elderly_notice", "masks"]}, {"outcome": "confirmed"}, {"residents": 2400})
    assert rwa["value"] == 7200 and rwa["unit"] == "protected resident-hours"
    assert accounting.impact({"actorType": "rwa", "kind": "exposure", "outdoorHoursCancelled": 3.0}, {"actions": ["outdoor_off"]}, {"outcome": "confirmed"}, {"residents": 2400})["value"] == 2880


def test_nearest_station_reads_the_index_through_storage(tmp_path, monkeypatch):
    # nearest_station() used to read a hardcoded relative path (data/openaq_stations.json),
    # which is not inside the Lambda package (CodeUri: ../services/) and left every outcome
    # check as no_station in AWS. It must go through storage(), as every other static lookup
    # does, so the index comes from S3 in AWS and .data/static/ locally (make seed-local).
    from common import storage as st
    from records.verification import nearest_station

    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("TABLE_NAME", raising=False)
    st.reset()
    assert nearest_station(28.7, 77.1) is None   # no index written yet: no crash, no match
    st.storage().put_json("static/openaq_stations.json", {"stations": [
        {"id": 1, "name": "Rohini", "lat": 28.70, "lon": 77.10},
        {"id": 2, "name": "Sangrur", "lat": 30.25, "lon": 75.85},
    ]})
    near = nearest_station(28.71, 77.11)
    assert near["id"] == 1 and near["name"] == "Rohini" and near["source"] == "openaq-archive"
    assert nearest_station(30.0, 70.0) is None   # nearest is Sangrur, > 25 km away
    st.reset()


def test_outcome_assess():
    from records.verification import assess

    windows = [["08:00", "14:00"], ["15:00", "16:00"]]
    hours = {f"2026-10-05T0{h}:30:00Z": v for h, v in [(2, 150.0), (3, 180.0), (4, 60.0), (9, 40.0)]}
    r = assess({"dayTier": "T2", "peakAqi": 320}, hours, windows)
    assert r["outcome"] == "confirmed" and r["observed"]["tier"] == "T2"
    assert assess({"dayTier": "T2"}, {"2026-10-05T03:30:00Z": 50.0}, windows)["outcome"] == "not_confirmed"
    assert assess({"dayTier": "T0"}, {"2026-10-05T03:30:00Z": 200.0}, windows)["outcome"] == "missed"
    assert assess({"dayTier": "T2"}, {}, windows)["outcome"] == "pending"

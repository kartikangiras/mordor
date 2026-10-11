from datetime import datetime, timezone

import pytest

from common import timeutil as t


def test_ist_label():
    dt = datetime(2026, 10, 9, 10, 30, tzinfo=timezone.utc)  # 16:00 IST
    assert t.ist_label(dt) == "Fri 9 Oct, 4 PM"
    assert t.ist_label(datetime(2026, 10, 9, 6, 45, tzinfo=timezone.utc)) == "Fri 9 Oct, 12:15 PM"
    assert t.ist_label(datetime(2026, 10, 9, 18, 30, tzinfo=timezone.utc)) == "Sat 10 Oct, 12 AM"


def test_run_id_roundtrip():
    dt = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)
    assert t.run_id(dt) == "20261009T0600Z"
    assert t.parse_run_id("20261009T0600Z") == dt
    with pytest.raises(ValueError):
        t.parse_run_id("2026-10-09")


def test_firms_time_zero_pads_three_char_acq_time():
    assert t.parse_firms_time("2026-10-09", "530") == datetime(2026, 10, 9, 5, 30, tzinfo=timezone.utc)
    assert t.parse_firms_time("2026-10-09", "0726") == datetime(2026, 10, 9, 7, 26, tzinfo=timezone.utc)


def test_cpcb_last_update_is_ist():
    assert t.parse_cpcb_last_update("09-10-2026 11:30:00") == datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)


def test_iso_formats():
    dt = datetime(2026, 10, 9, 6, 0, 0, 123, tzinfo=timezone.utc)
    assert t.iso_z(dt) == "2026-10-09T06:00:00Z"
    assert t.iso_ist(dt) == "2026-10-09T11:30:00+05:30"

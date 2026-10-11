from datetime import datetime, timedelta, timezone

from protocol import rules

UTC = timezone.utc


def _hourly(tiers_by_ist_hour: dict[int, str], date="2026-10-09"):
    """Rows for one IST date; 02:30 UTC = 08:00 IST."""
    base = datetime(2026, 10, 9, 2, 30, tzinfo=UTC) - timedelta(hours=8)  # 00:00 IST
    aqi = {"T0": 150, "T1": 250, "T2": 350, "T3": 420, "T4": 480}
    return [{"t": (base + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"), "tier": t, "aqi": aqi[t]}
            for h, t in sorted(tiers_by_ist_hour.items())]


def test_windows_merge_contiguous_spans():
    hourly = _hourly({7: "T0", 8: "T1", 9: "T1", 10: "T2", 11: "T2", 12: "T2", 13: "T2", 14: "T1", 15: "T1", 16: "T0"})
    w = rules.windows_for_day(hourly, "2026-10-09")
    assert [(x["fromIst"], x["toIst"], x["tier"]) for x in w] == [("08:00", "10:00", "T1"), ("10:00", "14:00", "T2"), ("14:00", "16:00", "T1")]
    assert rules.day_tier(w) == "T2"
    assert rules.headline(w, "T2") == "Cancel outdoor games after 10 am. Keep windows shut."
    assert rules.outdoor_hours_cancelled(w) == 4.0  # 10-14 at T2; 14-15 not a school hour, 15-16 is T1


def test_day_tier_ignores_the_gap_hour_and_counts_dismissal():
    hourly = _hourly({h: "T0" for h in range(8, 17)} | {14: "T4", 15: "T3"})
    w = rules.windows_for_day(hourly, "2026-10-09")
    assert rules.day_tier(w) == "T3"  # 14:00 T4 is outside both windows; 15:00 T3 is dismissal


def test_headlines_never_say_close():
    for t in rules.TIER_ORDER:
        text = rules.headline([{"fromIst": "08:00", "toIst": "16:00", "tier": t, "peakAqi": 1}], t).lower()
        assert "close" not in text.replace("closure", "") or t == "T4"
    assert "Directorate of Education" in rules.headline([], "T4")


def test_build_card_defaults_and_purifiers():
    hourly = _hourly({h: "T2" for h in range(8, 17)})
    card = rules.build_card(hourly, has_purifiers=False)
    assert card["dayTier"] == "T2" and card["protocol"]["windows"] == "Shut all day"
    assert set(card["defaultActions"]) == set(rules.ACTIONS) and card["outdoorHoursCancelled"] == 7.0
    card2 = rules.build_card(hourly, has_purifiers=True)
    assert "purifier" in card2["protocol"]["windows"]
    assert rules.build_card([{"t": "2026-10-09T02:30:00Z", "tier": None}])["dayTier"] is None


def test_pick_date_skips_days_with_too_few_school_hours_left():
    rows = _hourly({15: "T0", 16: "T0"}) + [{"t": f"2026-10-10T0{h}:30:00Z", "tier": "T1"} for h in range(2, 6)]  # tomorrow 08:00-11:00 IST
    assert rules.pick_date(rows) == "2026-10-10"
    assert rules.pick_date(_hourly({h: "T0" for h in range(8, 12)})) == "2026-10-09"

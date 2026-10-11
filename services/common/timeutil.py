"""UTC <-> IST and identifier formatting. The *only* place time conversion lives in the
backend; the web mirrors it in web/src/lib/time.ts."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from common.domain import IST_OFFSET_MIN

UTC = timezone.utc
IST = timezone(timedelta(minutes=IST_OFFSET_MIN), "IST")

_RUN_ID_RE = re.compile(r"^\d{8}T\d{4}Z$")


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso_z(dt: datetime) -> str:
    """2026-10-09T06:00:00Z"""
    return ensure_utc(dt).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ist(dt: datetime) -> str:
    """2026-10-09T11:30:00+05:30"""
    return ensure_utc(dt).astimezone(IST).replace(microsecond=0).isoformat()


def to_ist(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(IST)


def ist_label(dt: datetime) -> str:
    """'Tue 9 Oct, 4 PM' (or '4:30 PM' when minutes are non-zero)."""
    d = to_ist(dt)
    hour12 = d.hour % 12 or 12
    ampm = "AM" if d.hour < 12 else "PM"
    clock = f"{hour12} {ampm}" if d.minute == 0 else f"{hour12}:{d.minute:02d} {ampm}"
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}, {clock}"


def floor_hour(dt: datetime) -> datetime:
    return ensure_utc(dt).replace(minute=0, second=0, microsecond=0)


def run_id(dt: datetime) -> str:
    """YYYYMMDDTHHMMZ - lexicographically sortable, human readable."""
    return ensure_utc(dt).strftime("%Y%m%dT%H%MZ")


def parse_run_id(s: str) -> datetime:
    if not _RUN_ID_RE.match(s):
        raise ValueError(f"bad runId {s!r}")
    return datetime.strptime(s, "%Y%m%dT%H%MZ").replace(tzinfo=UTC)


def parse_firms_time(acq_date: str, acq_time: str) -> datetime:
    """FIRMS acq_time is UTC HHMM, sometimes only 3 characters ('530'). Zero-pad first."""
    hhmm = str(acq_time).strip().zfill(4)
    return datetime.strptime(f"{acq_date.strip()} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=UTC)


def parse_cpcb_last_update(s: str) -> datetime:
    """data.gov.in last_update is 'dd-mm-yyyy HH:MM:SS' in IST. Returns aware UTC."""
    return datetime.strptime(s.strip(), "%d-%m-%Y %H:%M:%S").replace(tzinfo=IST).astimezone(UTC)


def ttl_epoch(days: float, now: datetime | None = None) -> int:
    base = now or utc_now()
    return int((base + timedelta(days=days)).timestamp())


def utc_date_str(dt: datetime) -> str:
    return ensure_utc(dt).strftime("%Y-%m-%d")

"""The fitted scaling constant k and its fit metrics are *data*, written by the hindcast
(tools/hindcast.py) to validation/latest/calibration.json, never hardcoded (DESIGN.md §5.7).
Every run reads it at render time; when absent the run is published as 'uncalibrated'."""
from __future__ import annotations

from common.storage import Storage

CALIBRATION_KEY = "validation/latest/calibration.json"


def load_calibration(store: Storage) -> dict:
    cal = store.get_json(CALIBRATION_KEY) or {}
    k = cal.get("k")
    return {
        "k": float(k) if k is not None else None,
        "status": "calibrated" if k is not None else "uncalibrated",
        "r2": cal.get("r2"),
        "mae": cal.get("mae"),
        "bias": cal.get("bias"),
        "window": cal.get("window"),
        "stations": cal.get("stations"),
        "experimentId": cal.get("experimentId"),
        "windLevel": cal.get("windLevel"),
        "fittedAt": cal.get("fittedAt"),
        # Split-conformal half-widths in ug/m3 (tools/hindcast.py conformal()). Absent on an
        # uncalibrated run or a hindcast with too few held-out rows, in which case the card
        # shows a point value and says the interval is unavailable - never a made-up one.
        "conformal": cal.get("conformal") or None,
        "conformalByLead": cal.get("conformalByLead") or None,
    }

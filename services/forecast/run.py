"""The forecast run: fires + winds -> hourly raw surface fields (DESIGN.md §5.10).

Timebase: hour 0 of the output is `now` floored to the hour. Integration starts SPINUP_HOURS
earlier so particles from yesterday's detections are already downstream, and only hours
>= hour 0 are written out. Seeded RNG; the seed is part of the result so a run is reproducible.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np

from common import domain
from common.timeutil import floor_hour, iso_z, run_id
from forecast import grid, particles
from forecast.wind import WindField

log = logging.getLogger(__name__)


@dataclass
class Params:
    seed: int = 20261009
    k_h: float = domain.K_H_M2_S
    tau_h: float = domain.TAU_HOURS
    n_per_hour: int = domain.PARTICLES_PER_H
    burn_h: float = domain.BURN_WINDOW_H
    max_particles: int = domain.MAX_PARTICLES
    dt: float = domain.SUBSTEP_SECONDS
    spinup_h: int = domain.SPINUP_HOURS
    blend_925: float = domain.WIND_BLEND_925
    k: float | None = domain.K_SCALE   # None = uncalibrated


@dataclass
class RunResult:
    run_id: str
    t0: datetime
    hours: list[datetime]
    raw: np.ndarray            # (H+1, NLAT, NLON) mass/(area*BLH); k * raw = ug/m3
    blh: np.ndarray            # (H+1, NLAT, NLON) metres
    params: Params
    fires: list[dict]
    stats: dict = field(default_factory=dict)

    def meta(self) -> dict:
        return {
            "runId": self.run_id,
            "t0": iso_z(self.t0),
            "hours": [iso_z(h) for h in self.hours],
            "params": asdict(self.params),
            "stats": self.stats,
            "domain": domain.describe(),
        }


def run_forecast(now: datetime, fires: list[dict], wind: WindField, params: Params | None = None,
                 hours: int = domain.FORECAST_HOURS) -> RunResult:
    params = params or Params()
    t0 = floor_hour(now)
    t_start = t0 - timedelta(hours=params.spinup_h)
    t_end = t0 + timedelta(hours=hours)
    if not wind.covers(t_start) or not wind.covers(t_end):
        log.warning("wind field %s..%s does not fully cover %s..%s; edges are clamped",
                    wind.times[0], wind.times[-1], t_start, t_end)
    rng = np.random.default_rng(params.seed)
    p, emit_stats = particles.emit(fires, t_start, params.n_per_hour, params.burn_h, params.max_particles)

    steps_per_hour = int(round(3600 / params.dt))
    n_steps = (params.spinup_h + hours) * steps_per_hour
    raw = np.zeros((hours + 1, domain.NLAT, domain.NLON), dtype=np.float32)
    blh = np.zeros((hours + 1, domain.NLAT, domain.NLON), dtype=np.float32)
    out_hours: list[datetime] = [t0 + timedelta(hours=h) for h in range(hours + 1)]

    started = time.time()
    live_counts: list[int] = []
    for s in range(n_steps):
        t_sec = s * params.dt
        t = t_start + timedelta(seconds=t_sec)
        particles.step(p, wind, t, t_sec, params.dt, rng, params.k_h, params.tau_h)
        if (s + 1) % steps_per_hour == 0:
            h = (s + 1) // steps_per_hour - params.spinup_h
            if h >= 0:
                t_out = t_start + timedelta(seconds=(s + 1) * params.dt)
                live = p.live((s + 1) * params.dt)
                mass_grid = grid.bin_mass(p.lat[live], p.lon[live], p.mass[live])
                blh[h] = wind.blh_grid(t_out)
                raw[h] = grid.raw_surface(mass_grid, blh[h])
                live_counts.append(int(live.sum()))
    elapsed = time.time() - started
    stats = {**emit_stats, "steps": n_steps, "elapsedSeconds": round(elapsed, 2),
             "liveAtHour0": live_counts[0] if live_counts else 0,
             "liveAtEnd": live_counts[-1] if live_counts else 0,
             "rawMax": float(raw.max()) if raw.size else 0.0,
             "blhAvailable": wind.blh_available,
             "windSource": wind.source,
             "spinupFrom": iso_z(t_start)}
    log.info("forecast %s: %s", run_id(t0), stats)
    return RunResult(run_id(t0), t0, out_hours, raw, blh, params, fires, stats)

"""Lagrangian particles: emission, advection, turbulent diffusion, exponential loss
(DESIGN.md §5.3-§5.5). Everything is a flat numpy array; no per-particle Python."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from common import domain
from forecast.wind import WindField

log = logging.getLogger(__name__)


@dataclass
class Particles:
    lat: np.ndarray        # degrees
    lon: np.ndarray        # degrees
    mass: np.ndarray       # arbitrary units (FRP-weighted)
    t_release: np.ndarray  # seconds since run start
    alive: np.ndarray      # bool; False once outside the domain
    fire_index: np.ndarray # which fire emitted it (for diagnostics)

    def __len__(self) -> int:
        return int(self.lat.shape[0])

    def live(self, t_seconds: float) -> np.ndarray:
        return self.alive & (self.t_release <= t_seconds)


def emit(fires: list[dict], t_start: datetime, n_per_hour: int = domain.PARTICLES_PER_H,
         burn_h: float = domain.BURN_WINDOW_H, max_particles: int = domain.MAX_PARTICLES) -> tuple[Particles, dict]:
    """One source per detection; N particles per hour over the burn window, mass = FRP / N_total.
    Thins N uniformly if the cap would be exceeded and reports it (§5.3, R9)."""
    n_fires = len(fires)
    per_fire = int(round(n_per_hour * burn_h))
    thinned = False
    if n_fires * per_fire > max_particles and n_fires:
        per_fire = max(1, max_particles // n_fires)
        n_per_hour = per_fire / burn_h
        thinned = True
        log.warning("thinning particles: %d fires -> %d per fire (cap %d)", n_fires, per_fire, max_particles)
    if n_fires == 0:
        empty = np.zeros(0)
        return Particles(empty, empty, empty, empty, np.zeros(0, dtype=bool), np.zeros(0, dtype=np.int64)), \
            {"fires": 0, "particles": 0, "perFire": per_fire, "thinned": False}

    lat0 = np.array([f["lat"] for f in fires], dtype=np.float64)
    lon0 = np.array([f["lon"] for f in fires], dtype=np.float64)
    frp = np.array([float(f["frp"]) for f in fires], dtype=np.float64)
    t_det = np.array([(datetime.fromisoformat(f["acqUtc"].replace("Z", "+00:00")) - t_start).total_seconds()
                      for f in fires], dtype=np.float64)

    offsets = (np.arange(per_fire) + 0.5) * (burn_h * 3600.0 / per_fire)  # spread over the burn window
    lat = np.repeat(lat0, per_fire)
    lon = np.repeat(lon0, per_fire)
    mass = np.repeat(frp / per_fire, per_fire)
    t_release = np.repeat(t_det, per_fire) + np.tile(offsets, n_fires)
    idx = np.repeat(np.arange(n_fires), per_fire)
    p = Particles(lat, lon, mass, t_release, np.ones(lat.shape[0], dtype=bool), idx)
    return p, {"fires": n_fires, "particles": len(p), "perFire": per_fire, "thinned": thinned,
               "nPerHour": n_per_hour}


def step(p: Particles, wind: WindField, t: datetime, t_seconds: float, dt: float, rng: np.random.Generator,
         k_h: float = domain.K_H_M2_S, tau_h: float = domain.TAU_HOURS) -> int:
    """Advance every live particle by dt seconds using the wind at time t. Returns live count."""
    live = p.live(t_seconds)
    n = int(live.sum())
    if n == 0:
        return 0
    lat = p.lat[live]
    lon = p.lon[live]
    u, v = wind.sample_uv(lat, lon, t)
    # advection (§5.4)
    lat = lat + (v * dt) / domain.M_PER_DEG_LAT
    lon = lon + (u * dt) / (domain.M_PER_DEG_LAT * np.cos(np.radians(lat)))
    # turbulent random walk (§5.5)
    sigma = math.sqrt(2.0 * k_h * dt)
    lat = lat + rng.normal(0.0, sigma, n) / domain.M_PER_DEG_LAT
    lon = lon + rng.normal(0.0, sigma, n) / (domain.M_PER_DEG_LAT * np.cos(np.radians(lat)))
    p.lat[live] = lat
    p.lon[live] = lon
    # exponential loss (§5.5)
    p.mass[live] *= math.exp(-dt / (tau_h * 3600.0))
    # particles that leave the domain are gone for good
    gone = ~domain.in_domain(lat, lon)
    if gone.any():
        idx = np.flatnonzero(live)[gone]
        p.alive[idx] = False
    return n - int(gone.sum())

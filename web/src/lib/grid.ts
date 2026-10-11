// Client-side sampling of a run's fire grid and coarse background, mirroring
// services/common/domain.py cell conventions (i_lat from south, i_lon from west, row-major).
import type { Manifest } from './api'

export interface Domain { w: number; s: number; e: number; n: number; dlat: number; dlon: number; nlat: number; nlon: number }

export function domainOf(m: Manifest): Domain {
  const [w, s, e, n] = m.domain
  const dlat = 0.05, dlon = 0.05
  return { w, s, e, n, dlat, dlon, nlat: Math.round((n - s) / dlat), nlon: Math.round((e - w) / dlon) }
}

export function cellIndex(d: Domain, lat: number, lon: number): number | null {
  if (lat < d.s || lat >= d.n || lon < d.w || lon >= d.e) return null
  const iLat = Math.floor((lat - d.s) / d.dlat)
  const iLon = Math.floor((lon - d.w) / d.dlon)
  return iLat * d.nlon + iLon
}

/** Bilinear sample of a coarse [lat][lon] slice on a regular grid; clamps at the edges. */
export function bilinear(slice: number[][], lats: number[], lons: number[], lat: number, lon: number): number {
  const dlat = lats[1] - lats[0], dlon = lons[1] - lons[0]
  const fy = Math.min(Math.max((lat - lats[0]) / dlat, 0), lats.length - 1 - 1e-9)
  const fx = Math.min(Math.max((lon - lons[0]) / dlon, 0), lons.length - 1 - 1e-9)
  const iy = Math.floor(fy), ix = Math.floor(fx)
  const wy = fy - iy, wx = fx - ix
  const iy1 = Math.min(iy + 1, lats.length - 1), ix1 = Math.min(ix + 1, lons.length - 1)
  const v = (a: number, b: number) => slice[a]?.[b] ?? 0
  return (1 - wy) * (1 - wx) * v(iy, ix) + (1 - wy) * wx * v(iy, ix1) + wy * (1 - wx) * v(iy1, ix) + wy * wx * v(iy1, ix1)
}

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371, toRad = (x: number) => (x * Math.PI) / 180
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

export function centroidOfPolygon(ring: [number, number][]): [number, number] {
  const pts = ring.slice(0, 4)
  return [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length]
}

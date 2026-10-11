// Everything the experience shows is "within the selected area": fires, burn-risk cells, zones,
// actors, schools, the exposure series at the centroid, the wind at the slider hour.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useStore } from '@/lib/store'
import { getImpact, getEntityRecords, getRecordsIndex, type ActorProps, type BurnProps, type ImpactReport, type Zone } from '@/lib/api'
import type { EntityRecords, RecordsIndex } from '@/lib/protocol'
import { bilinear, cellIndex, domainOf, haversineKm, centroidOfPolygon } from '@/lib/grid'
import type { SeriesPoint } from '@/components/Detail/ExposureChart'
import type { Area } from '@/config/areas'

const IST_HOUR = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: 'numeric', hour12: false })

export function useAreaData(area: Area | null, extraIds: string[] = []) {
  const { manifest, fires, burning, zones, entities, schools, background, grids, wind, hour, ensureGrids } = useStore()
  const [records, setRecords] = useState<Record<string, EntityRecords>>({})
  const [index, setIndex] = useState<RecordsIndex | null>(null)
  const [impact, setImpact] = useState<ImpactReport | null>(null)

  useEffect(() => { if (manifest) void ensureGrids() }, [manifest, ensureGrids])

  const inArea = useMemo(() => {
    if (!area) return null
    const km = (lat: number, lon: number) => haversineKm(area.lat, area.lon, lat, lon)
    const f = (fires?.features ?? []).filter((x) => km(x.geometry.coordinates[1], x.geometry.coordinates[0]) <= area.radiusKm)
    const cells = (burning?.features ?? []).map((x) => { const [lon, lat] = centroidOfPolygon(x.geometry.coordinates[0] as [number, number][]); return { ...x.properties, lat, lon, km: km(lat, lon) } })
      .filter((c) => c.km <= area.radiusKm).sort((a, b) => b.score - a.score) as (BurnProps & { lat: number; lon: number; km: number })[]
    const z = (zones?.zones ?? []).filter((x) => km(x.lat, x.lon) <= area.radiusKm + x.radiusKm) as Zone[]
    const acts = (entities?.features ?? []).map((x) => ({ ...x.properties, lat: x.geometry.coordinates[1], lon: x.geometry.coordinates[0], km: km(x.geometry.coordinates[1], x.geometry.coordinates[0]) }))
      .filter((a) => a.km <= Math.max(area.radiusKm, (a.radiusKm ?? 0))) as (ActorProps & { lat: number; lon: number; km: number })[]
    const sch = (schools?.features ?? []).filter((x) => km(x.geometry.coordinates[1], x.geometry.coordinates[0]) <= area.radiusKm)
    const frp = f.reduce((a, x) => a + (x.properties.frp || 0), 0)
    const ndvi = cells.filter((c) => c.ndviChange !== null)
    return {
      fires: f, frpMw: frp, cells, zones: z, actors: acts, schools: sch,
      ndviMean: ndvi.length ? ndvi.reduce((a, c) => a + (c.ndviChange as number), 0) / ndvi.length : null,
      climMean: cells.length ? cells.reduce((a, c) => a + (c.climatologyPerDay ?? 0), 0) / cells.length : null,
      rain48: cells.length ? Math.max(...cells.map((c) => c.rain48mm ?? 0)) : null,
      burningNow: cells.filter((c) => c.fires24 > 0).length,
      byTier: sch.reduce<Record<string, number>>((m, x) => { const t = x.properties.dayTier ?? 'none'; m[t] = (m[t] ?? 0) + 1; return m }, {}),
    }
  }, [area, fires, burning, zones, entities, schools])

  const series = useMemo<SeriesPoint[]>(() => {
    if (!area || !manifest || !background) return []
    const cell = cellIndex(domainOf(manifest), area.lat, area.lon)
    const k = manifest.calibration.k
    return manifest.hours.map((t, h) => {
      const bg = background.pm25[h] ? bilinear(background.pm25[h], background.lats, background.lons, area.lat, area.lon) : 0
      const fire = k !== null && cell !== null && grids[h] ? grids[h].values[cell] : null
      const istHour = Number(IST_HOUR.format(new Date(t))) % 24
      return { t, hour: h, bg: Math.round(bg * 10) / 10, fire, total: fire !== null ? Math.round((bg + fire) * 10) / 10 : null, istHour, inSchool: istHour >= 8 && istHour < 14 }
    })
  }, [area, manifest, background, grids])

  const windNow = useMemo(() => {
    if (!area || !wind) return null
    const h = Math.min(hour, wind.hours.length - 1)
    const i = wind.lats.reduce((bi, v, idx) => (Math.abs(v - area.lat) < Math.abs(wind.lats[bi] - area.lat) ? idx : bi), 0)
    const j = wind.lons.reduce((bj, v, idx) => (Math.abs(v - area.lon) < Math.abs(wind.lons[bj] - area.lon) ? idx : bj), 0)
    const u = wind.u[h][i][j], v = wind.v[h][i][j]
    const speed = Math.hypot(u, v)
    const toward = (Math.atan2(u, v) * 180) / Math.PI
    return { speed, toward: (toward + 360) % 360, from: (toward + 180) % 360 }
  }, [area, wind, hour])

  const baseIds = inArea?.actors.length ? inArea.actors.map((a) => a.id) : (entities?.features ?? []).map((f) => f.properties.id)
  const actorIds = [...new Set([...baseIds, ...extraIds])].join(',')
  /** Re-read the decision records (the steps write new ones; step 8 reads the day back). */
  const reloadRecords = useCallback(() => {
    const ids = actorIds ? actorIds.split(',') : []
    Promise.all(ids.map((id) => getEntityRecords(id).then((l) => [id, l] as const).catch(() => null))).then((rs) => setRecords(Object.fromEntries(rs.filter((x): x is readonly [string, EntityRecords] => !!x))))
    getRecordsIndex().then(setIndex).catch(() => setIndex(null))
  }, [actorIds])
  useEffect(() => { reloadRecords() }, [reloadRecords])

  useEffect(() => { const d = index?.date; if (d) getImpact(d).then(setImpact).catch(() => setImpact(null)) }, [index?.date])

  return { manifest, inArea, series, windNow, records, index, impact, hour, reloadRecords }
}

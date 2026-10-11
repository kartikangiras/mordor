import type { ActorProps } from '@/lib/api'
import type { Area } from '@/config/areas'
import { haversineKm } from '@/lib/grid'
import type { useAreaData } from '../useAreaData'
import type { useStore } from '@/lib/store'

export type AreaData = ReturnType<typeof useAreaData>
export type ActorHit = ActorProps & { lat: number; lon: number; km: number }
export type StepProps = { area: Area; d: AreaData; headers: Record<string, string>; onComplete: () => void; colour: string; school?: import('@/lib/experience').SchoolPick | null; onSchool?: (s: import('@/lib/experience').SchoolPick) => void }

/** The actor a step works with: in the area if possible, else the nearest registered one. */
export function pickActor(d: AreaData, entities: ReturnType<typeof useStore.getState>['entities'], area: Area,
                          want: { kind?: 'exposure' | 'source'; type?: string }): ActorHit | null {
  const all: ActorHit[] = (entities?.features ?? []).map((f) => ({ ...f.properties, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0], km: haversineKm(area.lat, area.lon, f.geometry.coordinates[1], f.geometry.coordinates[0]) }))
  const inArea = d.inArea?.actors ?? []
  const score = (a: ActorHit) => (want.type && a.type === want.type ? 0 : want.kind && a.kind === want.kind ? 1 : 2) * 1000 + a.km
  const pool = inArea.length ? inArea : all
  return pool.slice().sort((x, y) => score(x) - score(y))[0] ?? null
}


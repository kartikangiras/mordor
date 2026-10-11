import { create } from 'zustand'
import type { Feature, FeatureCollection, Point } from 'geojson'
import { setPalette } from './aqi'
import { getBackground, getBurning, getEntities, getFires, getGridHour, getGuidelines, getLatest, getSchools, getStations, getWind, getZones, type Background, type BurningFile, type EntitiesFile, type FireProps, type GridHour, type Manifest, type SchoolProps, type SchoolsLayer, type StationSnapshot, type WindSeries, type ZonesFile } from './api'
import { INITIAL_VIEW, type LayerId } from '@/config/layers'
import { chapters } from '@/config/chapters'
import { AREAS, type Area } from '@/config/areas'
import { EXP_STEPS, zoomForRadius } from '@/lib/experience'

export type Selected = { kind: 'school'; feature: Feature<Point, SchoolProps> } | null

/** What the free map opens with. Chapters and steps overwrite layers; resetView() restores these. */
export const DEFAULT_LAYERS: Record<LayerId, boolean> = { plume: true, fires: true, wind: false, stations: false, schools: true, zones: false, burnrisk: false, ndvi: false, actors: true }

/** One in-flight load at a time: MapRoot, the landing and the map page all used to call load()
 *  on mount, which fetched the manifest and eight files twice on a fresh visit. */
let inflight: Promise<void> | null = null

/** Restore the palette choice before the first render so nothing flashes in the wrong ramp. */
const INITIAL_CVD = (() => {
  try {
    return localStorage.getItem('mordor.cvd') === '1'
  } catch {
    return false
  }
})()
if (INITIAL_CVD) setPalette('cvd')

interface State {
  manifest: Manifest | null
  fires: FeatureCollection<Point, FireProps> | null
  schools: SchoolsLayer | null
  background: Background | null
  wind: WindSeries | null
  stations: StationSnapshot | null
  guidelines: import('@/config/publicGuidelines').Guidelines | null
  zones: ZonesFile | null
  burning: BurningFile | null
  entities: EntitiesFile | null
  grids: Record<number, GridHour>
  error: string | null
  hour: number
  playing: boolean
  layers: Record<LayerId, boolean>
  /** Colour-vision-deficiency palette. Bumping paletteRev is what re-renders the map. */
  cvd: boolean
  paletteRev: number
  toggleCvd: () => void
  selected: Selected
  chapter: number | null            // null = free explore
  area: Area | null
  expStep: number | null            // guided experience step index, null = not in the experience
  /** cinematic = the landing's slow camera path, non-interactive; interactive = everything else. */
  mapMode: 'cinematic' | 'interactive'
  setMapMode: (m: 'cinematic' | 'interactive') => void
  /** Back to the free map's opening state: default layers, hour 0, domain camera, nothing selected. */
  resetView: () => void
  /** Fly the shared map somewhere (a chapter's chosen school, a picked zone). */
  flyTo: (center: [number, number], zoom: number, pitch?: number) => void
  cameraRequest: { center: [number, number]; zoom: number; pitch?: number; bearing?: number; seq: number } | null
  load: () => Promise<void>
  ensureGrids: () => Promise<void>
  setHour: (h: number) => void
  setPlaying: (p: boolean) => void
  toggleLayer: (id: LayerId) => void
  setLayers: (visible: LayerId[]) => void
  select: (s: Selected) => void
  setChapter: (i: number | null) => void
  setArea: (area: Area | null) => void
  setExpStep: (i: number | null) => void
}

export const useStore = create<State>((set, get) => ({
  manifest: null, fires: null, schools: null, background: null, wind: null, stations: null, guidelines: null, zones: null, burning: null, entities: null, grids: {},
  error: null, hour: 0, playing: false,
  cvd: INITIAL_CVD,
  paletteRev: 0,
  layers: { ...DEFAULT_LAYERS },
  selected: null, chapter: null, cameraRequest: null, area: null, expStep: null,
  mapMode: 'interactive',
  setMapMode: (mapMode) => set({ mapMode }),
  flyTo: (center, zoom, pitch = 0) => set({ cameraRequest: { center, zoom, pitch, bearing: 0, seq: Date.now() } }),
  resetView: () => set({
    layers: { ...DEFAULT_LAYERS }, hour: 0, playing: false, selected: null, chapter: null, expStep: null,
    cameraRequest: { center: INITIAL_VIEW.center, zoom: INITIAL_VIEW.zoom, pitch: 0, bearing: 0, seq: Date.now() },
  }),
  load: () => {
    if (get().manifest) return Promise.resolve()
    if (inflight) return inflight
    inflight = (async () => {
      try {
        const manifest = await getLatest()
        set({ manifest, error: null })
        const [fires, schools, background, wind, stations, zones, burning, entities, guidelines] = await Promise.all([getFires(manifest), getSchools(manifest), getBackground(manifest), getWind(manifest), getStations(), getZones(manifest), getBurning(manifest), getEntities(manifest), getGuidelines()])
        set({ fires, schools, background, wind, stations, zones, burning, entities, guidelines })
        const c = get().chapter
        if (c !== null) get().setChapter(c)
      } catch (e) {
        set({ error: (e as Error).message })
      } finally {
        inflight = null
      }
    })()
    return inflight
  },
  ensureGrids: async () => {
    const m = get().manifest
    if (!m) return
    const missing = m.hours.map((_, h) => h).filter((h) => !get().grids[h])
    if (!missing.length) return
    const loaded = await Promise.all(missing.map((h) => getGridHour(m, h)))
    set((s) => ({ grids: { ...s.grids, ...Object.fromEntries(loaded.map((g, i) => [missing[i], g])) } }))
  },
  setHour: (h) => { const n = get().manifest?.hours.length ?? 1; set({ hour: Math.max(0, Math.min(n - 1, h)) }) },
  setPlaying: (playing) => set({ playing }),
  toggleLayer: (id) => set((s) => ({ layers: { ...s.layers, [id]: !s.layers[id] } })),
  toggleCvd: () => set((s) => {
    const cvd = !s.cvd
    setPalette(cvd ? 'cvd' : 'cpcb')
    try { localStorage.setItem('mordor.cvd', cvd ? '1' : '0') } catch { /* private mode */ }
    return { cvd, paletteRev: s.paletteRev + 1 }
  }),
  setLayers: (visible) => set((s) => ({ layers: Object.fromEntries(Object.keys(s.layers).map((k) => [k, visible.includes(k as LayerId)])) as State['layers'] })),
  select: (selected) => set({ selected }),
  setArea: (area) => {
    set({ area })
    const step = get().expStep
    if (area && step !== null) get().setExpStep(step)
  },
  setExpStep: (i) => {
    if (i === null) { set({ expStep: null, playing: false }); return }
    const st = EXP_STEPS[Math.max(0, Math.min(EXP_STEPS.length - 1, i))]
    const area = get().area ?? AREAS[0]
    const n = get().manifest?.hours.length ?? 1
    set({ expStep: i, chapter: null, selected: null, playing: false, hour: st.hour !== undefined ? Math.min(st.hour, n - 1) : get().hour,
          cameraRequest: { center: [area.lon, area.lat], zoom: zoomForRadius(area.radiusKm) + st.zoomDelta, pitch: st.pitch, bearing: st.bearing, seq: Date.now() } })
    get().setLayers(st.layers)
  },
  setChapter: (i) => {
    if (i === null) { set({ chapter: null, playing: false }); return }
    const ch = chapters[Math.max(0, Math.min(chapters.length - 1, i))]
    const n = get().manifest?.hours.length ?? 1
    set({ chapter: i, hour: Math.min(ch.hour, n - 1), playing: !!ch.autoplay, selected: null,
          cameraRequest: { ...ch.camera, seq: Date.now() } })
    get().setLayers(ch.layers)
  },
}))

if (import.meta.env.DEV) (window as unknown as { __vdStore?: typeof useStore }).__vdStore = useStore   // headless checks read the state

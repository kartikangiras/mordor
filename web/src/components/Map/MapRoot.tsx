// The one MapLibre instance. Created once per MapShell mount; routes switch its mode (the landing's
// cinematic loop vs. interactive) and their overlays instead of tearing it down, so moving between
// /, /map and /story keeps the map, its tiles and the loaded run.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import maplibregl from 'maplibre-gl'
import { basemapStyle, INITIAL_VIEW, LANDING_WAYPOINTS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { installClickDispatcher } from '@/lib/mapclicks'
import { useStore } from '@/lib/store'
import PlumeLayer from './PlumeLayer'
import FireLayer from './FireLayer'
import SchoolLayer from './SchoolLayer'
import WindLayer from './WindLayer'
import StationLayer from './StationLayer'
import NdviLayer from './NdviLayer'
import BurnRiskLayer from './BurnRiskLayer'
import ZoneLayer from './ZoneLayer'
import ActorLayer from './ActorLayer'

export default function MapRoot() {
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<maplibregl.Map | null>(null)
  const load = useStore((s) => s.load)
  const cameraRequest = useStore((s) => s.cameraRequest)
  const mode = useStore((s) => s.mapMode)
  const navigate = useNavigate()
  const navRef = useRef(navigate)
  useEffect(() => { navRef.current = navigate }, [navigate])
  const firstMode = useRef(true)

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    const el = container.current
    if (!el) return
    const m = new maplibregl.Map({
      container: el, style: basemapStyle(), center: INITIAL_VIEW.center, zoom: INITIAL_VIEW.zoom, pitch: 0, bearing: 0,
      attributionControl: { compact: true }, maxBounds: [[60, 15], [95, 40]], fadeDuration: 0, maxPitch: 70,
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), 'top-right')
    const offDispatch = installClickDispatcher(m)
    // 'style.load', not 'load': 'load' waits for every imagery, label and DEM tile of the first view, which on a
    // fresh visit to the domain-wide map can take tens of seconds or never settle; the data layers only need the style.
    m.once('style.load', () => setMap(m))
    if (import.meta.env.DEV) { const w = window as unknown as { __vdMaps?: maplibregl.Map[] }; (w.__vdMaps ??= []).push(m) }   // headless checks query the live map
    // Popups are raw HTML, so their links used to be full reloads. One delegate turns every
    // <a data-nav href> inside the map into a router navigation; modified clicks keep browser behaviour.
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement | null)?.closest?.('a[data-nav]') as HTMLAnchorElement | null
      if (!a || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
      e.preventDefault()
      navRef.current(a.getAttribute('href') ?? '/')
    }
    el.addEventListener('click', onClick)
    return () => { el.removeEventListener('click', onClick); offDispatch(); setMap(null); try { m.remove() } catch { /* already gone */ } }
  }, [])

  // Mode. cinematic = the landing: input handlers off and a slow loop over the waypoints.
  // interactive = everything else: handlers on, the camera left wherever the route's request put it.
  // Declared before the camera effect so a mode change settles before a camera request lands.
  useEffect(() => {
    if (!map) return
    const handlers = [map.scrollZoom, map.boxZoom, map.dragRotate, map.dragPan, map.keyboard, map.doubleClickZoom, map.touchZoomRotate, map.touchPitch]
    const first = firstMode.current
    firstMode.current = false
    if (mode !== 'cinematic') { handlers.forEach((h) => h.enable()); return }
    handlers.forEach((h) => h.disable())
    let idx = 0
    const w0 = LANDING_WAYPOINTS[0]
    if (first) map.jumpTo(w0)
    else map.flyTo({ ...w0, duration: 2500, essential: true })
    const next = () => { idx = (idx + 1) % LANDING_WAYPOINTS.length; const w = LANDING_WAYPOINTS[idx]; map.flyTo({ ...w, duration: 16000, essential: true, curve: 1.2 }); timer = window.setTimeout(next, 17000) }
    let timer = window.setTimeout(next, 3500)
    return () => {
      window.clearTimeout(timer)
      if (!mapAlive(map)) return
      map.stop()
      handlers.forEach((h) => h.enable())
    }
  }, [map, mode])

  useEffect(() => {
    if (!map || !cameraRequest || mode === 'cinematic') return
    map.flyTo({ center: cameraRequest.center, zoom: cameraRequest.zoom, pitch: cameraRequest.pitch ?? 0, bearing: cameraRequest.bearing ?? 0, duration: 1600, essential: true })
  }, [map, cameraRequest, mode])

  return (
    <div className={`absolute inset-0 ${mode === 'cinematic' ? 'map-cinematic' : ''}`}>
      <div ref={container} className="h-full w-full" />
      {map && (
        <>
          <NdviLayer map={map} />
          <PlumeLayer map={map} />
          <BurnRiskLayer map={map} />
          <ZoneLayer map={map} />
          <WindLayer map={map} />
          <StationLayer map={map} />
          <SchoolLayer map={map} />
          <FireLayer map={map} />
          <ActorLayer map={map} />
        </>
      )}
    </div>
  )
}

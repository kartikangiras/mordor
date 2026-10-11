// Layer 3: VIIRS detections, radius by FRP (4-14 px), warm fill (DESIGN.md §9.2).
import { useEffect } from 'react'
import maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { useStore } from '@/lib/store'
import { istLabel } from '@/lib/time'

const ID = LAYER_IDS.fires
const GLOW = `${ID}-glow`
const COLUMNS = `${ID}-columns`

function circle(lat: number, lon: number, km: number, n = 12): [number, number][] {
  const ring: [number, number][] = []
  for (let k = 0; k <= n; k++) { const a = (k / n) * 2 * Math.PI; ring.push([lon + (km * Math.sin(a)) / (111.32 * Math.cos((lat * Math.PI) / 180)), lat + (km * Math.cos(a)) / 111.32]) }
  return ring
}

export default function FireLayer({ map }: { map: maplibregl.Map }) {
  const fires = useStore((s) => s.fires)
  const visible = useStore((s) => s.layers.fires)

  useEffect(() => {
    if (!fires) return
    const columns = { type: 'FeatureCollection' as const, features: fires.features.map((f) => ({ type: 'Feature' as const, properties: { frp: f.properties.frp, height: Math.max(600, (f.properties.frp || 1) * 180) }, geometry: { type: 'Polygon' as const, coordinates: [circle(f.geometry.coordinates[1], f.geometry.coordinates[0], 0.45)] } })) }
    if (!mapAlive(map)) return
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(fires)
      ;(map.getSource(COLUMNS) as GeoJSONSource | undefined)?.setData(columns)
    } else {
      map.addSource(ID, { type: 'geojson', data: fires })
      map.addSource(COLUMNS, { type: 'geojson', data: columns })
      map.addLayer({ id: COLUMNS, type: 'fill-extrusion', source: COLUMNS, paint: { 'fill-extrusion-color': ['interpolate', ['linear'], ['get', 'frp'], 0, '#ffb347', 20, '#ff6a2b', 60, '#d7263d'], 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-base': 0, 'fill-extrusion-opacity': 0.75 } })
      map.addLayer({ id: GLOW, type: 'circle', source: ID, paint: { 'circle-radius': ['interpolate', ['linear'], ['coalesce', ['get', 'frp'], 1], 0, 10, 50, 26], 'circle-color': '#ff6a2b', 'circle-blur': 0.9, 'circle-opacity': 0.35 } })
      map.addLayer({
        id: ID,
        type: 'circle',
        source: ID,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['coalesce', ['get', 'frp'], 1], 0, 4, 10, 8, 50, 14],
          'circle-color': '#FFB347',
          'circle-opacity': 0.8,
          'circle-stroke-color': '#7C2B3F',
          'circle-stroke-width': 1,
        },
      })
    }
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: true, className: 'fire-popup' })
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const p = f.properties as Record<string, string | number>
      popup
        .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
        .setHTML(
          `<div style="font:12px/1.4 ui-monospace,monospace;color:#e8ebef;background:#14181d;padding:6px 8px;border:1px solid #262c34">` +
            `<b>VIIRS fire</b><br/>FRP ${Number(p.frp).toFixed(1)} MW · ${p.confidence}<br/>${p.satellite} · ${istLabel(String(p.acqUtc))} IST</div>`,
        )
        .addTo(map)
    }
    const cursor = (on: boolean) => () => { map.getCanvas().style.cursor = on ? 'pointer' : '' }
    const offClick = registerClick(ID, (_f, e) => onClick(e))
    map.on('mouseenter', ID, cursor(true))
    map.on('mouseleave', ID, cursor(false))
    return () => {
      if (!mapAlive(map)) return
      popup.remove()
      offClick()
      map.off('mouseenter', ID, cursor(true))
      map.off('mouseleave', ID, cursor(false))
      for (const l of [ID, GLOW, COLUMNS]) if (map.getLayer(l)) map.removeLayer(l)
      for (const src of [ID, COLUMNS]) if (map.getSource(src)) map.removeSource(src)
    }
  }, [map, fires])

  useEffect(() => {
    if (mapAlive(map)) for (const l of [ID, GLOW, COLUMNS]) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, fires])

  return null
}

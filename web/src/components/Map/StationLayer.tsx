// Layer 4: observing stations, fill = observed PM2.5 on the same ramp; stale ones hollow
// (DESIGN.md §9.2, §13.4 rule 4). Reference monitors (CPCB / DPCC / IMD) draw larger than
// low-cost sensor networks and the popup names the actual provider: as of 2026-10-07 the live
// layer is almost entirely AirGradient / Hawanama, because CPCB's own feeds are either
// unreachable (api.data.gov.in) or ~4.5 days stale (OpenAQ). Never label these "CPCB".
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { PM25_RAMP } from '@/lib/aqi'
import { useStore } from '@/lib/store'
import { istLabel } from '@/lib/time'

const ID = LAYER_IDS.stations

/** Name the real source of a reading. Never assert a network the data did not come from. */
function provenance(p: Record<string, string | number>): string {
  const provider = p.provider ? String(p.provider) : 'unknown provider'
  const via = p.source === 'data.gov.in' ? 'via data.gov.in' : 'via OpenAQ v3'
  const kind = Number(p.ref) ? 'reference monitor' : 'low-cost sensor'
  return `${provider} · ${kind} · ${via}`
}

export default function StationLayer({ map }: { map: maplibregl.Map }) {
  const stations = useStore((s) => s.stations)
  const paletteRev = useStore((s) => s.paletteRev)   // repaint on a palette swap
  const repaintRef = useRef(paletteRev)
  const visible = useStore((s) => s.layers.stations)

  useEffect(() => {
    if (!stations) return
    const fc: FeatureCollection<Point, Record<string, unknown>> = {
      type: 'FeatureCollection',
      features: stations.stations.map((s) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [s.lon, s.lat] }, properties: { ...s, stale: s.isStale ? 1 : 0, ref: s.tier === 'reference' ? 1 : 0 } })),
    }
    const ramp: maplibregl.ExpressionSpecification = ['step', ['get', 'pm25'], '#6b7480', ...PM25_RAMP.flatMap((r) => [r.from, r.colour])] as maplibregl.ExpressionSpecification
    if (!mapAlive(map)) return
    if (repaintRef.current !== paletteRev) {   // colours live in paint, so rebuild
      repaintRef.current = paletteRev
      if (map.getLayer(ID)) map.removeLayer(ID)
      if (map.getSource(ID)) map.removeSource(ID)
    }
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(fc)
    } else {
      map.addSource(ID, { type: 'geojson', data: fc })
      map.addLayer({
        id: ID, type: 'circle', source: ID,
        paint: {
          // reference monitors read as the authoritative dot; sensors are visibly smaller
          'circle-radius': ['case', ['==', ['get', 'ref'], 1], 7, 4.5],
          'circle-color': ramp,
          'circle-opacity': ['case', ['==', ['get', 'stale'], 1], 0, 0.95],
          'circle-stroke-color': ramp,
          'circle-stroke-width': ['case', ['==', ['get', 'ref'], 1], 2, 1],
        },
      })
      map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
    }
    const popup = new maplibregl.Popup({ closeButton: false })
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const p = f.properties as Record<string, string | number>
      popup.setLngLat((f.geometry as Point).coordinates as [number, number])
        .setHTML(`<div style="font:12px/1.4 ui-monospace,monospace;color:#e8ebef;background:#14181d;padding:6px 8px;border:1px solid #262c34"><b>${p.name}</b><br/>observed PM2.5 ${p.pm25} µg/m³<br/>${istLabel(String(p.observedAt))} IST${Number(p.stale) ? ' · stale' : ''}<br/>${provenance(p)}</div>`)
        .addTo(map)
    }
    const offClick = registerClick(ID, (_f, e) => onClick(e))
    return () => { popup.remove(); offClick() }
  }, [map, stations, paletteRev])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map) && map.getLayer(ID)) map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, stations, paletteRev])

  useEffect(() => () => {
    if (!mapAlive(map)) return
    if (map.getLayer(ID)) map.removeLayer(ID)
    if (map.getSource(ID)) map.removeSource(ID)
  }, [map])   // unmount only: a palette swap must not tear the layer down

  return null
}

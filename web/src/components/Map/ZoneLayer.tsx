// Exposure zones: a circle per city, filled by the tier at the slider hour (background + our
// fire increment), labelled with the total. Drag the slider and the colours follow the plume.
import { useEffect, useMemo, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import type { Feature, FeatureCollection, Polygon } from 'geojson'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { TIERS, pm25Subindex, tierForAqi } from '@/lib/aqi'
import { useStore } from '@/lib/store'
import type { Zone } from '@/lib/api'

const ID = LAYER_IDS.zones
const LABEL = `${ID}-label`

function circle(lat: number, lon: number, km: number, n = 36): Polygon {
  const ring: [number, number][] = []
  for (let k = 0; k <= n; k++) {
    const a = (k / n) * 2 * Math.PI
    ring.push([lon + (km * Math.sin(a)) / (111.32 * Math.cos((lat * Math.PI) / 180)), lat + (km * Math.cos(a)) / 111.32])
  }
  return { type: 'Polygon', coordinates: [ring] }
}

export function zoneAtHour(z: Zone, h: number) {
  const bg = z.hourly.pm25Background[h] ?? z.now.pm25Background
  const fire = z.hourly.pm25Fire ? z.hourly.pm25Fire[h] ?? 0 : null
  const total = fire !== null ? bg + fire : bg
  const aqi = pm25Subindex(total)
  return { bg, fire, total, aqi, tier: tierForAqi(aqi), no2: z.hourly.no2 ? z.hourly.no2[h] : null }
}

export default function ZoneLayer({ map }: { map: maplibregl.Map }) {
  const zones = useStore((s) => s.zones)
  const paletteRev = useStore((s) => s.paletteRev)   // repaint on a palette swap
  const repaintRef = useRef(paletteRev)
  const hour = useStore((s) => s.hour)
  const visible = useStore((s) => s.layers.zones)

  const fc = useMemo<FeatureCollection<Polygon, Record<string, unknown>> | null>(() => {
    if (!zones) return null
    const features: Feature<Polygon, Record<string, unknown>>[] = zones.zones.map((z) => {
      const v = zoneAtHour(z, hour)
      return { type: 'Feature', geometry: circle(z.lat, z.lon, z.radiusKm), properties: { id: z.id, name: z.name, tier: v.tier, colour: TIERS[v.tier].colour, total: Math.round(v.total), bg: Math.round(v.bg), fire: v.fire === null ? null : Math.round(v.fire), aqi: v.aqi, no2: v.no2 === null ? null : Math.round(v.no2), label: `${z.name} ${Math.round(v.total)}` } }
    })
    return { type: 'FeatureCollection', features }
  }, [zones, hour])

  useEffect(() => {
    if (!fc) return
    if (!mapAlive(map)) return
    if (repaintRef.current !== paletteRev) {   // colours live in paint, so rebuild
      repaintRef.current = paletteRev
      if (map.getLayer(ID)) map.removeLayer(ID)
      if (map.getSource(ID)) map.removeSource(ID)
    }
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(fc)
      return
    }
    map.addSource(ID, { type: 'geojson', data: fc })
    const before = map.getLayer(LAYER_IDS.fires) ? LAYER_IDS.fires : undefined
    map.addLayer({ id: ID, type: 'fill', source: ID, paint: { 'fill-color': ['get', 'colour'], 'fill-opacity': 0.35, 'fill-outline-color': '#e8ebef' }, layout: { visibility: visible ? 'visible' : 'none' } }, before)
    map.addLayer({
      id: LABEL, type: 'symbol', source: ID,
      layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-font': ['Noto Sans Regular'], 'text-allow-overlap': false, 'text-optional': true, 'text-padding': 4, visibility: visible ? 'visible' : 'none' },
      paint: { 'text-color': '#e8ebef', 'text-halo-color': '#0b0d10', 'text-halo-width': 1.2 },
    })
    const popup = new maplibregl.Popup({ closeButton: false })
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const p = f.properties as Record<string, string | number | null>
      popup.setLngLat(e.lngLat).setHTML(
        `<div style="font:12px/1.4 ui-monospace,monospace;color:#e8ebef;background:#14181d;padding:6px 8px;border:1px solid #262c34"><b>${p.name}</b> · ${p.tier} ${TIERS[p.tier as keyof typeof TIERS].label}<br/>` +
        `PM2.5 ${p.total} µg/m³ = background ${p.bg} + fire ${p.fire ?? '—'} · AQI ${p.aqi}<br/>NO2 traffic tracer ${p.no2 ?? '—'} µg/m³ · <a data-nav href="/zones" style="color:#b8c0cb">all zones</a></div>`,
      ).addTo(map)
    }
    const offClick = registerClick(ID, (_f, e) => onClick(e))
    return () => {
      if (!mapAlive(map)) return
      popup.remove(); offClick()
      for (const l of [LABEL, ID]) if (map.getLayer(l)) map.removeLayer(l)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, fc, paletteRev])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map)) for (const l of [ID, LABEL]) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, fc, paletteRev])

  return null
}

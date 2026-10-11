// 48-hour burning-risk cells (0.25°), coloured by category; click shows the score components.
import { useEffect } from 'react'
import maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { BURN_CATS } from '@/lib/aqi'
import { useStore } from '@/lib/store'
import type { BurnProps } from '@/lib/api'

const ID = LAYER_IDS.burnrisk
const OUTLINE = `${ID}-outline`

export default function BurnRiskLayer({ map }: { map: maplibregl.Map }) {
  const burning = useStore((s) => s.burning)
  const visible = useStore((s) => s.layers.burnrisk)

  useEffect(() => {
    if (!burning) return
    const fc = { type: 'FeatureCollection' as const, features: burning.features }
    const colour: maplibregl.ExpressionSpecification = ['step', ['get', 'score'], BURN_CATS[0].colour, 26, BURN_CATS[1].colour, 51, BURN_CATS[2].colour, 76, BURN_CATS[3].colour]
    if (!mapAlive(map)) return
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(fc)
    } else {
      map.addSource(ID, { type: 'geojson', data: fc })
      const before = map.getLayer(LAYER_IDS.fires) ? LAYER_IDS.fires : undefined
      map.addLayer({ id: ID, type: 'fill', source: ID, paint: { 'fill-color': colour, 'fill-opacity': ['interpolate', ['linear'], ['get', 'score'], 0, 0.15, 100, 0.6] }, layout: { visibility: visible ? 'visible' : 'none' } }, before)
      map.addLayer({ id: OUTLINE, type: 'line', source: ID, paint: { 'line-color': '#0b0d10', 'line-width': 0.5, 'line-opacity': 0.5 }, layout: { visibility: visible ? 'visible' : 'none' } }, before)
    }
    const popup = new maplibregl.Popup({ closeButton: false, maxWidth: '260px' })
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const p = f.properties as unknown as BurnProps & { components: string | BurnProps['components'] }
      const c = typeof p.components === 'string' ? (JSON.parse(p.components) as BurnProps['components']) : p.components
      popup.setLngLat(e.lngLat).setHTML(
        `<div style="font:12px/1.4 ui-monospace,monospace;color:#e8ebef;background:#14181d;padding:6px 8px;border:1px solid #262c34">` +
        `<b>${p.name}</b> · burn risk <b>${p.score}</b> ${p.category}<br/>fires 24 h ${p.fires24} (48 h ${p.fires48}, trend ${p.trend >= 0 ? '+' : ''}${p.trend}) · FRP ${p.frp24} MW<br/>` +
        `recent ${c.recent} · trend ${c.trend} · 2024 season ${c.season} · NDVI drop ${c.vegetation} · rain ${c.rain}<br/>` +
        `NDVI change ${p.ndviChange ?? '—'} · rain 48 h ${p.rain48mm ?? '—'} mm · 2024 avg ${p.climatologyPerDay ?? '—'}/day</div>`,
      ).addTo(map)
    }
    const offClick = registerClick(ID, (_f, e) => onClick(e))
    return () => {
      if (!mapAlive(map)) return
      popup.remove(); offClick()
      for (const l of [OUTLINE, ID]) if (map.getLayer(l)) map.removeLayer(l)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, burning])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map)) for (const l of [ID, OUTLINE]) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, burning])

  return null
}

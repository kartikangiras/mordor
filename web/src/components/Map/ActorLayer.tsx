// Layer 7: the onboarded and demo actors of every type, labelled with who holds the card.
// School = circle, RWA = diamond, agriculture office = triangle; colour = today's tier / risk.
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import type { Point } from 'geojson'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { BURN_CATS, TIERS, type TierId } from '@/lib/aqi'
import { useStore } from '@/lib/store'
import type { ActorProps } from '@/lib/api'

const ID = LAYER_IDS.actors
const LABEL = `${ID}-label`
const SHAPES: Record<string, string> = { school: 'actor-school', rwa: 'actor-rwa', agri_officer: 'actor-office', hospital: 'actor-hospital' }

function icon(kind: 'school' | 'rwa' | 'agri_officer' | 'hospital'): ImageData {
  const s = 36, c = document.createElement('canvas'); c.width = c.height = s
  const g = c.getContext('2d')!
  g.fillStyle = 'rgba(232,235,239,1)'; g.strokeStyle = 'rgba(11,13,16,1)'; g.lineWidth = 2
  g.beginPath()
  if (kind === 'school') g.arc(s / 2, s / 2, s * 0.36, 0, Math.PI * 2)
  else if (kind === 'rwa') { g.moveTo(s / 2, 3); g.lineTo(s - 3, s / 2); g.lineTo(s / 2, s - 3); g.lineTo(3, s / 2); g.closePath() }
  else if (kind === 'hospital') { const a = s * 0.18, b = s * 0.5; g.moveTo(b - a, 3); g.lineTo(b + a, 3); g.lineTo(b + a, b - a); g.lineTo(s - 3, b - a); g.lineTo(s - 3, b + a); g.lineTo(b + a, b + a); g.lineTo(b + a, s - 3); g.lineTo(b - a, s - 3); g.lineTo(b - a, b + a); g.lineTo(3, b + a); g.lineTo(3, b - a); g.lineTo(b - a, b - a); g.closePath() }
  else { g.moveTo(s / 2, 3); g.lineTo(s - 3, s - 4); g.lineTo(3, s - 4); g.closePath() }
  g.fill(); g.stroke()
  return g.getImageData(0, 0, s, s)
}

function colourOf(p: ActorProps): string {
  if (p.kind === 'source') return (BURN_CATS.find((c) => c.label === p.dayTier) ?? BURN_CATS[0]).colour
  return p.dayTier ? TIERS[p.dayTier as TierId].colour : '#6b7480'
}

export default function ActorLayer({ map }: { map: maplibregl.Map }) {
  const entities = useStore((s) => s.entities)
  const paletteRev = useStore((s) => s.paletteRev)   // repaint on a palette swap
  const repaintRef = useRef(paletteRev)
  const visible = useStore((s) => s.layers.actors)

  useEffect(() => {
    if (!entities) return
    // schools are drawn by the school layer (ringed when they hold a card); people markers are the others
    const fc = { type: 'FeatureCollection' as const, features: entities.features.filter((f) => f.properties.type !== 'school').map((f) => ({ ...f, properties: { ...f.properties, icon: SHAPES[f.properties.type] ?? 'actor-school', colour: colourOf(f.properties), label: `${f.properties.persona ? f.properties.persona + ' · ' : ''}${f.properties.personTitle}` } })) }
    if (!mapAlive(map)) return
    if (repaintRef.current !== paletteRev) {   // colours live in paint, so rebuild
      repaintRef.current = paletteRev
      if (map.getLayer(ID)) map.removeLayer(ID)
      if (map.getSource(ID)) map.removeSource(ID)
    }
    if (map.getSource(ID)) { (map.getSource(ID) as GeoJSONSource).setData(fc); return }
    for (const k of ['school', 'rwa', 'agri_officer', 'hospital'] as const) if (!map.hasImage(SHAPES[k])) map.addImage(SHAPES[k], icon(k), { pixelRatio: 2, sdf: true })
    map.addSource(ID, { type: 'geojson', data: fc })
    map.addLayer({ id: ID, type: 'symbol', source: ID, layout: { 'icon-image': ['get', 'icon'], 'icon-size': 1, 'icon-allow-overlap': true, visibility: visible ? 'visible' : 'none' }, paint: { 'icon-color': ['get', 'colour'], 'icon-halo-color': '#0b0d10', 'icon-halo-width': 1 } })
    map.addLayer({ id: LABEL, type: 'symbol', source: ID, layout: { 'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.4], 'text-anchor': 'top', 'text-allow-overlap': false, 'text-optional': true, visibility: visible ? 'visible' : 'none' }, paint: { 'text-color': '#e8ebef', 'text-halo-color': '#0b0d10', 'text-halo-width': 1.4 } })
    const popup = new maplibregl.Popup({ closeButton: false, maxWidth: '280px' })
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const p = f.properties as unknown as ActorProps & { colour: string }
      popup.setLngLat((f.geometry as Point).coordinates as [number, number]).setHTML(
        `<div style="font:12px/1.45 ui-monospace,monospace;color:#e8ebef;background:#14181d;padding:8px 10px;border:1px solid #262c34">` +
        `<b>${p.name}</b><br/>${p.typeLabel} · ${p.persona ? p.persona + ', ' : ''}${p.personTitle}<br/>` +
        `<span style="background:${p.colour};color:#0b0d10;padding:0 4px;border-radius:2px">${p.dayTier ?? '—'}</span> ${p.date ?? ''}<br/>${p.headline}<br/>` +
        `<a data-nav href="/records/${encodeURIComponent(p.id)}" style="color:#b8c0cb">decisions</a></div>`,
      ).addTo(map)
    }
    const cursor = (on: boolean) => () => { map.getCanvas().style.cursor = on ? 'pointer' : '' }
    const offClick = registerClick(ID, (_f, e) => onClick(e)); map.on('mouseenter', ID, cursor(true)); map.on('mouseleave', ID, cursor(false))
    return () => {
      if (!mapAlive(map)) return
      popup.remove(); offClick(); map.off('mouseenter', ID, cursor(true)); map.off('mouseleave', ID, cursor(false))
      for (const l of [LABEL, ID]) if (map.getLayer(l)) map.removeLayer(l)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, entities, paletteRev])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map)) for (const l of [ID, LABEL]) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, entities, paletteRev])

  return null
}

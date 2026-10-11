// Layer 5: every school, coloured by day tier; clustered below z10 (DESIGN.md §9.2).
// Tier is never colour alone: the detail panel and popups carry the label.
import { useEffect, useRef } from 'react'
import type maplibregl from 'maplibre-gl'
import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import type { Feature, Point } from 'geojson'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { registerClick } from '@/lib/mapclicks'
import { TIERS } from '@/lib/aqi'
import { useStore } from '@/lib/store'
import type { SchoolProps } from '@/lib/api'

const ID = LAYER_IDS.schools
const CLUSTERS = `${ID}-clusters`
const RING = `${ID}-ring`      // a school with a card: ringed and named
const NAME = `${ID}-name`
const UNCAL = '#6b7480'

const tierColour: maplibregl.ExpressionSpecification = [
  'match', ['coalesce', ['get', 'dayTier'], 'none'],
  'T0', TIERS.T0.colour, 'T1', TIERS.T1.colour, 'T2', TIERS.T2.colour, 'T3', TIERS.T3.colour, 'T4', TIERS.T4.colour,
  UNCAL,
]

export default function SchoolLayer({ map }: { map: maplibregl.Map }) {
  const schools = useStore((s) => s.schools)
  const paletteRev = useStore((s) => s.paletteRev)   // repaint on a palette swap
  const repaintRef = useRef(paletteRev)
  const visible = useStore((s) => s.layers.schools)
  const select = useStore((s) => s.select)

  useEffect(() => {
    if (!schools) return
    if (!mapAlive(map)) return
    if (repaintRef.current !== paletteRev) {   // colours live in paint, so rebuild
      repaintRef.current = paletteRev
      for (const l of [NAME, RING, ID]) if (map.getLayer(l)) map.removeLayer(l)
      if (map.getSource(ID)) map.removeSource(ID)
    }
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(schools)
    } else {
      map.addSource(ID, { type: 'geojson', data: schools, cluster: true, clusterRadius: 36, clusterMaxZoom: 10 })
      map.addLayer({
        id: CLUSTERS, type: 'circle', source: ID, filter: ['has', 'point_count'],
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'point_count'], 2, 8, 50, 14, 500, 22],
          'circle-color': '#b8c0cb', 'circle-opacity': 0.55, 'circle-stroke-color': '#0b0d10', 'circle-stroke-width': 1,
        },
      })
      map.addLayer({
        id: ID, type: 'circle', source: ID, filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 3, 12, 6, 15, 9],
          'circle-color': tierColour, 'circle-opacity': 0.9, 'circle-stroke-color': '#0b0d10', 'circle-stroke-width': 1,
        },
      })
      const withCard: maplibregl.FilterSpecification = ['all', ['!', ['has', 'point_count']], ['any', ['==', ['get', 'demo'], true], ['==', ['get', 'onboarded'], true]]]
      map.addLayer({ id: RING, type: 'circle', source: ID, filter: withCard, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 7, 12, 11, 15, 15], 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#e8ebef', 'circle-stroke-width': 2 } })
      map.addLayer({ id: NAME, type: 'symbol', source: ID, filter: withCard, minzoom: 10, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.6], 'text-anchor': 'top', 'text-optional': true }, paint: { 'text-color': '#e8ebef', 'text-halo-color': '#0b0d10', 'text-halo-width': 1.4 } })
    }
    const onClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [ID] })[0]
      if (!f) return
      const props = { ...(f.properties as Record<string, unknown>) } as unknown as SchoolProps
      if (typeof (props.days as unknown) === 'string') props.days = JSON.parse(props.days as unknown as string)
      const feature: Feature<Point, SchoolProps> = { type: 'Feature', geometry: f.geometry as Point, properties: props }
      select({ kind: 'school', feature })
    }
    const onClusterClick = (e: MapMouseEvent) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [CLUSTERS] })[0]
      if (!f) return
      const src = map.getSource(ID) as GeoJSONSource
      src.getClusterExpansionZoom(f.properties!.cluster_id as number).then((z) => {
        map.easeTo({ center: (f.geometry as Point).coordinates as [number, number], zoom: z })
      })
    }
    const cursor = (on: boolean) => () => { map.getCanvas().style.cursor = on ? 'pointer' : '' }
    const offClick = registerClick(ID, (_f, e) => onClick(e))
    const offCluster = registerClick(CLUSTERS, (_f, e) => onClusterClick(e))
    for (const l of [ID, CLUSTERS]) { map.on('mouseenter', l, cursor(true)); map.on('mouseleave', l, cursor(false)) }
    return () => {
      if (!mapAlive(map)) return
      offClick()
      offCluster()
      for (const l of [ID, CLUSTERS]) { map.off('mouseenter', l, cursor(true)); map.off('mouseleave', l, cursor(false)) }
      for (const l of [NAME, RING, ID, CLUSTERS]) if (map.getLayer(l)) map.removeLayer(l)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, schools, select, paletteRev])

  useEffect(() => {
    if (mapAlive(map)) for (const l of [ID, CLUSTERS, RING, NAME]) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, schools, paletteRev])

  return null
}

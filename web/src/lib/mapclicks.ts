// One map-level click (PIVOT_PLAN.md P17): layers register a handler for their layer id; a click
// queries the visible interactive layers once and hands the topmost hit, in priority order, to
// exactly one handler. Overlapping geometries no longer open two popups, and the cursor logic
// lives in one place.
import type maplibregl from 'maplibre-gl'
import { LAYER_IDS } from '@/config/layers'

export type ClickHandler = (feature: maplibregl.MapGeoJSONFeature, e: maplibregl.MapMouseEvent, map: maplibregl.Map) => void

/** Topmost first: a person's marker beats the school dot beneath it, points beat areas. */
const PRIORITY: string[] = [LAYER_IDS.actors, LAYER_IDS.schools, `${LAYER_IDS.schools}-clusters`, LAYER_IDS.stations, LAYER_IDS.fires, LAYER_IDS.burnrisk, LAYER_IDS.zones]
const handlers = new Map<string, ClickHandler>()

export function registerClick(layerId: string, handler: ClickHandler): () => void {
  handlers.set(layerId, handler)
  return () => { if (handlers.get(layerId) === handler) handlers.delete(layerId) }
}

function activeLayers(map: maplibregl.Map): string[] {
  return PRIORITY.filter((id) => handlers.has(id) && map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none')
}

export function installClickDispatcher(map: maplibregl.Map): () => void {
  const onClick = (e: maplibregl.MapMouseEvent) => {
    const ids = activeLayers(map)
    if (!ids.length) return
    const hits = map.queryRenderedFeatures(e.point, { layers: ids })
    for (const id of ids) {
      const f = hits.find((h) => h.layer.id === id)
      if (f) { handlers.get(id)?.(f, e, map); return }
    }
  }
  const onMove = (e: maplibregl.MapMouseEvent) => {
    const ids = activeLayers(map)
    map.getCanvas().style.cursor = ids.length && map.queryRenderedFeatures(e.point, { layers: ids }).length ? 'pointer' : ''
  }
  map.on('click', onClick); map.on('mousemove', onMove)
  return () => { map.off('click', onClick); map.off('mousemove', onMove) }
}

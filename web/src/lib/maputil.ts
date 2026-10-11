import type maplibregl from 'maplibre-gl'

/** False once map.remove() has run: MapLibre drops `style`, and any getLayer/getSource then throws. */
export function mapAlive(map: maplibregl.Map | null | undefined): map is maplibregl.Map {
  if (!map) return false
  const m = map as unknown as { style?: unknown; _removed?: boolean }
  return !!m.style && !m._removed
}

export function setVisible(map: maplibregl.Map, ids: string[], visible: boolean): void {
  if (!mapAlive(map)) return
  for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
}

export function removeLayers(map: maplibregl.Map, layers: string[], sources: string[]): void {
  if (!mapAlive(map)) return
  try {
    for (const l of layers) if (map.getLayer(l)) map.removeLayer(l)
    for (const s of sources) if (map.getSource(s)) map.removeSource(s)
  } catch { /* the map is going away */ }
}

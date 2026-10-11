// NASA GIBS NDVI 8-day composite (VIIRS NOAA-20), keyless WMTS raster. Sits under the plume so
// the vegetation state reads as context: green = standing crop, pale = harvested or bare.
import { useEffect } from 'react'
import type maplibregl from 'maplibre-gl'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { useStore } from '@/lib/store'

const ID = LAYER_IDS.ndvi

export default function NdviLayer({ map }: { map: maplibregl.Map }) {
  const ndvi = useStore((s) => s.manifest?.ndvi ?? null)
  const visible = useStore((s) => s.layers.ndvi)

  useEffect(() => {
    if (!ndvi) return
    if (!map.getSource(ID)) {
      map.addSource(ID, { type: 'raster', tiles: [ndvi.tileTemplate], tileSize: 256, maxzoom: 8, attribution: 'NDVI: NASA GIBS, VIIRS NOAA-20' })
      const before = map.getLayer(LAYER_IDS.plume) ? LAYER_IDS.plume : undefined
      map.addLayer({ id: ID, type: 'raster', source: ID, paint: { 'raster-opacity': 0.75, 'raster-fade-duration': 0 }, layout: { visibility: visible ? 'visible' : 'none' } }, before)
    }
    return () => {
      if (!mapAlive(map)) return
      if (map.getLayer(ID)) map.removeLayer(ID)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, ndvi])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map) && map.getLayer(ID)) map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, ndvi])

  return null
}

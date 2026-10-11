// Layer 1, the hero: one PNG per hour as a MapLibre image source with the domain corners from
// the manifest (DESIGN.md §5.8, §9.2). All hours are preloaded; the slider only swaps the URL.
import { useEffect } from 'react'
import type maplibregl from 'maplibre-gl'
import type { ImageSource } from 'maplibre-gl'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { overlayUrl } from '@/lib/api'
import { useStore } from '@/lib/store'

const ID = LAYER_IDS.plume

function firstSymbolLayer(map: maplibregl.Map): string | undefined {
  if (map.getLayer(LAYER_IDS.fires)) return LAYER_IDS.fires
  return map.getStyle().layers?.find((l) => l.type === 'symbol')?.id
}

export default function PlumeLayer({ map }: { map: maplibregl.Map }) {
  const manifest = useStore((s) => s.manifest)
  const hour = useStore((s) => s.hour)
  const visible = useStore((s) => s.layers.plume)

  useEffect(() => {
    if (!manifest) return
    const url = overlayUrl(manifest, 0)
    if (!map.getSource(ID)) {
      map.addSource(ID, { type: 'image', url, coordinates: manifest.imageCorners })
      map.addLayer(
        { id: ID, type: 'raster', source: ID, paint: { 'raster-opacity': 0.85, 'raster-resampling': 'linear', 'raster-fade-duration': 0 } },
        firstSymbolLayer(map),
      )
    } else {
      (map.getSource(ID) as ImageSource).updateImage({ url, coordinates: manifest.imageCorners })
    }
    // Preload every hour so the slider never waits on the network.
    for (let h = 0; h < manifest.hours.length; h++) {
      const img = new Image()
      img.src = overlayUrl(manifest, h)
    }
    return () => {
      if (!mapAlive(map)) return
      if (map.getLayer(ID)) map.removeLayer(ID)
      if (map.getSource(ID)) map.removeSource(ID)
    }
  }, [map, manifest])

  useEffect(() => {
    if (!manifest) return
    const src = map.getSource(ID) as ImageSource | undefined
    src?.updateImage({ url: overlayUrl(manifest, hour) })
  }, [map, manifest, hour])

  useEffect(() => {
    if (mapAlive(map) && map.getLayer(ID)) map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, manifest])

  return null
}
